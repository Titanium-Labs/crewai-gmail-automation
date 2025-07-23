#!/usr/bin/env python
import sys
import os
import json
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Any, Optional

from dotenv import load_dotenv
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, before_kickoff, crew, task

# OAuth2 Gmail Tools
try:
    from .tools.gmail_oauth_tools import (
        OAuth2GetUnreadEmailsTool,
        OAuth2GmailOrganizeTool, 
        OAuth2GmailDeleteTool,
        OAuth2SaveDraftTool,
        OAuth2EmptyTrashTool
    )
    from .auth.oauth2_manager import OAuth2Manager
    OAUTH2_AVAILABLE = True
except ImportError:
    print("⚠️ OAuth2 tools not available. Please check your setup.")
    # Set dummy classes to None to avoid unbound variable errors
    OAuth2GetUnreadEmailsTool = None  # type: ignore
    OAuth2GmailOrganizeTool = None  # type: ignore
    OAuth2GmailDeleteTool = None  # type: ignore
    OAuth2SaveDraftTool = None  # type: ignore
    OAuth2EmptyTrashTool = None  # type: ignore
    OAuth2Manager = None  # type: ignore
    OAUTH2_AVAILABLE = False

from crewai import LLM
from .tools.date_tools import (
    DateCalculationTool
)
from .tools.file_tools import FileReadTool, JsonFileReadTool, JsonFileSaveTool
from .models import EmailDetails


@CrewBase
class OAuth2GmailCrewAi:
    """OAuth2-enabled CrewAI for Gmail automation with multi-user support."""

    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'

    def __init__(self, user_id=None, oauth_manager=None):
        """Initialize crew with OAuth2 authentication."""
        # Use provided parameters or fall back to environment variable
        self.user_id = user_id or os.environ.get("CURRENT_USER_ID")
        self.oauth_manager = oauth_manager
        
        if not self.user_id:
            raise ValueError("User ID must be provided either as parameter or CURRENT_USER_ID environment variable")
            
        print(f"🔐 Using OAuth2 authentication for user: {self.user_id}")
        
        if not OAUTH2_AVAILABLE:
            raise ImportError("OAuth2Manager not available. Please check your OAuth2 setup.")
            
        # Initialize OAuth2Manager if not provided
        if not self.oauth_manager:
            self.oauth_manager = OAuth2Manager()

    def _get_gmail_tools(self):
        """Get OAuth2 Gmail tools."""
        if not OAUTH2_AVAILABLE:
            raise ImportError("OAuth2 Gmail tools not available. Please check your setup.")
            
        return [
            OAuth2GetUnreadEmailsTool(user_id=self.user_id, oauth_manager=self.oauth_manager),
            OAuth2GmailOrganizeTool(user_id=self.user_id, oauth_manager=self.oauth_manager),
            OAuth2GmailDeleteTool(user_id=self.user_id, oauth_manager=self.oauth_manager),
            OAuth2SaveDraftTool(user_id=self.user_id, oauth_manager=self.oauth_manager),
            OAuth2EmptyTrashTool(user_id=self.user_id, oauth_manager=self.oauth_manager)
        ]

    @before_kickoff
    def prepare_emails(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch emails using OAuth2 authentication."""
        print("📧 Fetching emails using OAuth2...")
        
        # Ensure output directory exists
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        
        # Get email limit from inputs (default to 10 for OAuth2)
        email_limit = inputs.get('email_limit', 10)
        print(f"Processing up to {email_limit} emails...")

        try:
            # Get OAuth2 email tool
            if not OAUTH2_AVAILABLE:
                raise ImportError("OAuth2GetUnreadEmailsTool not available")
                
            tool = OAuth2GetUnreadEmailsTool(user_id=self.user_id, oauth_manager=self.oauth_manager)

            # Fetch emails
            raw_emails = tool._run(max_emails=email_limit)
            
            if not raw_emails:
                print("📭 No unread emails found.")
                return inputs

            # Process emails into EmailDetails format
            emails = []
            for subject, sender, body, email_id, thread_info in raw_emails:
                # Limit body content to prevent context overflow when agents process the file
                # Keep only first 300 characters which should contain the most important content
                limited_body = body[:300] + "... [Body limited for processing efficiency]" if len(body) > 300 else body
                
                email_detail = EmailDetails(
                    email_id=email_id,
                    subject=subject,
                    sender=sender,
                    body=f"EMAIL DATE: {thread_info.get('date', '')}\n\n{limited_body}",
                    date=thread_info.get('date', ''),
                    thread_info=thread_info,
                    age_days=None,
                    is_part_of_thread=thread_info.get('is_part_of_thread', False),
                    thread_size=thread_info.get('thread_size', 1),
                    thread_position=thread_info.get('thread_position', 1)
                )

                # Calculate age
                try:
                    if email_detail.date:
                        email_date = datetime.strptime(email_detail.date, "%Y-%m-%d")
                        today = datetime.now()
                        email_detail.age_days = (today - email_date).days
                except Exception as e:
                    print(f"Error calculating age for email date {email_detail.date}: {e}")
                    email_detail.age_days = None

                emails.append(email_detail.dict())

            # Save emails to file with UTF-8 encoding
            with open('output/fetched_emails.json', 'w', encoding='utf-8') as f:
                json.dump(emails, f, indent=2, ensure_ascii=False)

            print(f"📧 Fetched and saved {len(emails)} emails to output/fetched_emails.json")
            return inputs

        except Exception as e:
            print(f"❌ Error fetching emails: {e}")
            return inputs

    llm = LLM(
        model="openai/gpt-4o-mini",
        api_key=os.getenv("OPENAI_API_KEY"),
    )

    @agent
    def categorizer(self) -> Agent:
        """The email categorizer agent."""
        return Agent(
            **self.agents_config['categorizer'],
            tools=[FileReadTool()],
            verbose=True,
            llm=self.llm
        )

    @agent
    def organizer(self) -> Agent:
        """The email organizer agent."""
        gmail_tools = self._get_gmail_tools()
        return Agent(
            **self.agents_config['organizer'],
            tools=[*gmail_tools, FileReadTool()],
            verbose=True,
            llm=self.llm
        )

    @agent
    def response_generator(self) -> Agent:
        """The email response generator agent."""
        gmail_tools = self._get_gmail_tools()
        return Agent(
            **self.agents_config['response_generator'],
            tools=[*gmail_tools, FileReadTool()],
            verbose=True,
            llm=self.llm
        )

    @agent
    def cleaner(self) -> Agent:
        """The email cleanup specialist agent."""
        gmail_tools = self._get_gmail_tools()
        return Agent(
            **self.agents_config['cleaner'],
            tools=[*gmail_tools, DateCalculationTool(), FileReadTool()],
            verbose=True,
            llm=self.llm
        )

    @task
    def categorization_task(self) -> Task:
        """The email categorization task."""
        return Task(
            config=self.tasks_config['categorization_task'],
            output_file="output/categorization_report.json"
        )

    @task
    def organization_task(self) -> Task:
        """The email organization task."""
        return Task(
            config=self.tasks_config['organization_task'],
            output_file="output/organization_report.json"
        )

    @task
    def response_task(self) -> Task:
        """The email response task."""
        return Task(
            config=self.tasks_config['response_task'],
            output_file="output/response_report.json"
        )

    @task
    def cleanup_task(self) -> Task:
        """The email cleanup task."""
        return Task(
            config=self.tasks_config['cleanup_task'],
            output_file="output/cleanup_report.json"
        )

    @crew
    def crew(self) -> Crew:
        """Creates the OAuth2 email processing crew without Slack notifications."""
        return Crew(
            agents=[
                self.categorizer(), 
                self.organizer(), 
                self.response_generator(),
                self.cleaner()
            ],
            tasks=[
                self.categorization_task(), 
                self.organization_task(), 
                self.response_task(),
                self.cleanup_task()
            ],
            process=Process.sequential,
            verbose=True
        )

    def get_user_email(self) -> str:
        """Get user email from OAuth2 manager."""
        if not OAUTH2_AVAILABLE or not self.oauth_manager:
            return "unknown@user.com"
            
        try:
            return self.oauth_manager.get_user_email()
        except Exception as e:
            print(f"⚠️ Error getting user email: {e}")
            return "unknown@user.com"


def create_crew_for_user(user_id: str, oauth_manager) -> OAuth2GmailCrewAi:
    """Create and configure a crew for a specific user with OAuth2 authentication.
    
    Args:
        user_id: The unique identifier for the user
        oauth_manager: The OAuth2Manager instance for the user
        
    Returns:
        OAuth2GmailCrewAi: Configured crew instance for the user
    """
    # Create a new crew instance with the user_id and oauth_manager
    crew_instance = OAuth2GmailCrewAi(user_id=user_id, oauth_manager=oauth_manager)
    
    return crew_instance 