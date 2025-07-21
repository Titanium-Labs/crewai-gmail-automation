"""OAuth2-enabled version of Gmail CrewAI that supports both OAuth2 and IMAP authentication."""

import os
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task, before_kickoff

# Import both OAuth2 and IMAP tools
try:
    from .tools.gmail_oauth_tools import (
        OAuth2GetUnreadEmailsTool, 
        OAuth2GmailOrganizeTool, 
        OAuth2GmailDeleteTool, 
        OAuth2SaveDraftTool, 
        OAuth2EmptyTrashTool,
        OAuth2GetSentEmailsTool,
        OAuth2UserPersonaAnalyzerTool
    )
    from .auth import OAuth2Manager
except ImportError:
    # Fallback if OAuth2 dependencies not available
    OAuth2GetUnreadEmailsTool = None
    OAuth2GmailOrganizeTool = None
    OAuth2GmailDeleteTool = None
    OAuth2SaveDraftTool = None
    OAuth2EmptyTrashTool = None
    OAuth2GetSentEmailsTool = None
    OAuth2UserPersonaAnalyzerTool = None
    OAuth2Manager = None

from .tools import (
    GetUnreadEmailsTool, 
    GmailOrganizeTool, 
    GmailDeleteTool, 
    SaveDraftTool, 
    EmptyTrashTool,
    SlackNotificationTool,
    DateCalculationTool
)
from .tools.file_tools import FileReadTool, JsonFileReadTool, JsonFileSaveTool
from .models import EmailDetails


@CrewBase
class OAuth2GmailCrewAi:
    """OAuth2-enabled CrewAI for Gmail automation with multi-user support."""

    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'

    def __init__(self):
        """Initialize crew with appropriate authentication method."""
        self.use_oauth2 = bool(os.environ.get("CURRENT_USER_ID"))
        self.user_id = os.environ.get("CURRENT_USER_ID") if self.use_oauth2 else None
        
        if self.use_oauth2:
            print(f"🔐 Using OAuth2 authentication for user: {self.user_id}")
            self.oauth_manager = OAuth2Manager() if OAuth2Manager else None
        else:
            print("📧 Using IMAP authentication (EMAIL_ADDRESS/APP_PASSWORD)")
            self.oauth_manager = None

    def _get_gmail_tools(self):
        """Get appropriate Gmail tools based on authentication method."""
        if self.use_oauth2 and OAuth2GetUnreadEmailsTool:
            return [
                OAuth2GetUnreadEmailsTool(user_id=self.user_id, oauth_manager=self.oauth_manager),
                OAuth2GmailOrganizeTool(user_id=self.user_id, oauth_manager=self.oauth_manager),
                OAuth2GmailDeleteTool(user_id=self.user_id, oauth_manager=self.oauth_manager),
                OAuth2SaveDraftTool(user_id=self.user_id, oauth_manager=self.oauth_manager),
                OAuth2EmptyTrashTool(user_id=self.user_id, oauth_manager=self.oauth_manager)
            ]
        else:
            # Fallback to IMAP tools
            return [
                GetUnreadEmailsTool(),
                GmailOrganizeTool(),
                GmailDeleteTool(),
                SaveDraftTool(),
                EmptyTrashTool()
            ]

    def check_and_create_user_persona(self):
        """Check if user_facts.txt is blank and create user persona if needed."""
        facts_file = "knowledge/user_facts.txt"
        
        # Check if file exists and is empty or very small
        try:
            if not os.path.exists(facts_file) or os.path.getsize(facts_file) < 50:
                print("📋 User facts file is empty or missing. Creating user persona from sent emails...")
                
                if self.use_oauth2 and OAuth2GetSentEmailsTool and OAuth2UserPersonaAnalyzerTool:
                    # Fetch sent emails
                    sent_email_tool = OAuth2GetSentEmailsTool(user_id=self.user_id, oauth_manager=self.oauth_manager)
                    sent_emails = sent_email_tool._run(max_emails=100)
                    
                    if sent_emails:
                        # Analyze emails and create persona
                        analyzer_tool = OAuth2UserPersonaAnalyzerTool(user_id=self.user_id, oauth_manager=self.oauth_manager)
                        result = analyzer_tool._run(sent_emails=sent_emails)
                        print(f"✅ {result}")
                        return True
                    else:
                        print("⚠️ No sent emails found for persona analysis")
                        return False
                else:
                    print("⚠️ OAuth2 tools not available for persona analysis")
                    return False
            else:
                print("✅ User facts file already exists and has content")
                return True
        except Exception as e:
            print(f"❌ Error checking/creating user persona: {e}")
            return False

    @before_kickoff
    def fetch_emails(self, inputs):
        """Fetch emails using appropriate authentication method."""
        print(f"🔍 Fetching emails using {'OAuth2' if self.use_oauth2 else 'IMAP'} authentication...")
        
        # Check and create user persona if needed
        self.check_and_create_user_persona()

        try:
            # Get appropriate tool
            if self.use_oauth2 and OAuth2GetUnreadEmailsTool:
                tool = OAuth2GetUnreadEmailsTool(user_id=self.user_id, oauth_manager=self.oauth_manager)
            else:
                tool = GetUnreadEmailsTool()

            # Fetch emails
            raw_emails = tool._run(max_emails=50)
            
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
                    thread_info=thread_info
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

            # Ensure output directory exists
            os.makedirs('output', exist_ok=True)

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
            config=self.agents_config['categorizer'],
            tools=[FileReadTool()],
            verbose=True,
            llm=self.llm
        )

    @agent
    def organizer(self) -> Agent:
        """The email organizer agent."""
        gmail_tools = self._get_gmail_tools()
        return Agent(
            config=self.agents_config['organizer'],
            tools=[*gmail_tools, FileReadTool()],
            verbose=True,
            llm=self.llm
        )

    @agent
    def response_generator(self) -> Agent:
        """The email response generator agent."""
        gmail_tools = self._get_gmail_tools()
        return Agent(
            config=self.agents_config['response_generator'],
            tools=[*gmail_tools, FileReadTool()],
            verbose=True,
            llm=self.llm
        )

    @agent
    def notifier(self) -> Agent:
        """The email notifier agent."""
        return Agent(
            config=self.agents_config['notifier'],
            tools=[SlackNotificationTool(), FileReadTool()],
            verbose=True,
            llm=self.llm
        )

    @agent
    def cleaner(self) -> Agent:
        """The email cleanup specialist agent."""
        gmail_tools = self._get_gmail_tools()
        return Agent(
            config=self.agents_config['cleaner'],
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
    def notification_task(self) -> Task:
        """The email notification task."""
        return Task(
            config=self.tasks_config['notification_task'],
            output_file="output/notification_report.json"
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
        """Creates the Gmail CrewAI crew."""
        auth_method = "OAuth2" if self.use_oauth2 else "IMAP"
        user_info = f" (User: {self.user_id})" if self.use_oauth2 else ""
        
        print(f"🤖 Initializing Gmail CrewAI with {auth_method} authentication{user_info}")
        
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )

    def get_user_email(self) -> str:
        """Get the current user's email address."""
        if self.use_oauth2 and self.oauth_manager:
            return self.oauth_manager.get_user_email(self.user_id)
        else:
            return os.environ.get("EMAIL_ADDRESS", "unknown@example.com")

    def is_authenticated(self) -> bool:
        """Check if current user is authenticated."""
        if self.use_oauth2 and self.oauth_manager:
            return self.oauth_manager.is_authenticated(self.user_id)
        else:
            return bool(os.environ.get("EMAIL_ADDRESS") and os.environ.get("APP_PASSWORD"))


def create_crew_for_user(user_id: str, oauth_manager: Any = None) -> OAuth2GmailCrewAi:
    """Factory function to create a crew for a specific user."""
    # Set environment variables for this user
    original_user_id = os.environ.get("CURRENT_USER_ID")
    
    try:
        os.environ["CURRENT_USER_ID"] = user_id
        
        crew = OAuth2GmailCrewAi()
        
        # If OAuth2 manager provided, use it
        if oauth_manager:
            crew.oauth_manager = oauth_manager
        
        return crew
        
    finally:
        # Restore original environment
        if original_user_id:
            os.environ["CURRENT_USER_ID"] = original_user_id
        elif "CURRENT_USER_ID" in os.environ:
            del os.environ["CURRENT_USER_ID"] 