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

    def __init__(self, user_id=None, oauth_manager=None, user_api_keys=None):
        """Initialize crew with OAuth2 authentication."""
        # Use provided parameters or fall back to environment variable
        self.user_id = user_id or os.environ.get("CURRENT_USER_ID")
        self.oauth_manager = oauth_manager
        self.user_api_keys = user_api_keys or {}
        
        if not self.user_id:
            raise ValueError("User ID must be provided either as parameter or CURRENT_USER_ID environment variable")
            
        print(f"🔐 Using OAuth2 authentication for user: {self.user_id}")
        if self.user_api_keys:
            api_types = list(self.user_api_keys.keys())
            print(f"🔑 User has personal API keys for: {', '.join(api_types)}")
        
        if not OAUTH2_AVAILABLE:
            raise ImportError("OAuth2Manager not available. Please check your OAuth2 setup.")
        
        # Setup LLM with user-specific API keys
        try:
            self.llm = self._setup_llm()
            print(f"✅ CrewAI LLM setup completed for user: {self.user_id}")
        except Exception as e:
            print(f"❌ CrewAI LLM setup failed for user {self.user_id}: {e}")
            raise
            
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

    def _setup_llm(self):
        """Setup LLM with user-specific API keys and environment fallback."""
        # Ensure environment variables are loaded with override
        load_dotenv(override=True)
        
        # Get model from environment with smart fallback
        model = os.getenv("MODEL", "anthropic/claude-4-sonnet")
        
        # Helper function to get API key with user preference and environment fallback
        def get_api_key_with_fallback(key_type: str) -> str:
            # Try user-specific key first
            if self.user_api_keys and key_type in self.user_api_keys and self.user_api_keys[key_type]:
                print(f"🔑 Using user's {key_type} API key")
                return self.user_api_keys[key_type]
            
            # Fallback to environment key
            env_key = os.getenv(f"{key_type.upper()}_API_KEY")
            if env_key:
                print(f"🌐 Using default {key_type} API key from environment")
                return env_key
            
            return None
        
        # Determine which API key to use based on model
        if "anthropic" in model.lower():
            api_key = get_api_key_with_fallback("anthropic")
            if not api_key:
                print("⚠️  No Anthropic API key available, falling back to OpenAI")
                model = "openai/gpt-4o-mini"
                api_key = get_api_key_with_fallback("openai")
            else:
                # Validate Anthropic API key format
                if not api_key.startswith("sk-ant-"):
                    print(f"⚠️  Invalid Anthropic API key format (should start with 'sk-ant-'), falling back to OpenAI")
                    model = "openai/gpt-4o-mini"
                    api_key = get_api_key_with_fallback("openai")
        else:
            api_key = get_api_key_with_fallback("openai")
            if not api_key:
                print("⚠️  No OpenAI API key available, falling back to Claude")
                model = "anthropic/claude-4-sonnet"
                api_key = get_api_key_with_fallback("anthropic")
            else:
                # Validate OpenAI API key format
                if not api_key.startswith("sk-"):
                    print(f"⚠️  Invalid OpenAI API key format (should start with 'sk-'), falling back to Claude")
                    model = "anthropic/claude-4-sonnet"
                    api_key = get_api_key_with_fallback("anthropic")
        
        if not api_key:
            error_msg = "No valid API key found. Please configure API keys in settings or set OPENAI_API_KEY or ANTHROPIC_API_KEY in your .env file."
            print(f"❌ {error_msg}")
            raise ValueError(error_msg)
        
        # Validate API key format more thoroughly
        is_valid_format = False
        if "anthropic" in model.lower() and api_key.startswith("sk-ant-"):
            is_valid_format = True
        elif "openai" in model.lower() and api_key.startswith("sk-"):
            is_valid_format = True
            
        if not is_valid_format:
            error_msg = f"Invalid API key format for {model}. Anthropic keys should start with 'sk-ant-', OpenAI keys should start with 'sk-'."
            print(f"❌ {error_msg}")
            raise ValueError(error_msg)
        
        print(f"🤖 Using model: {model}")
        print(f"🔑 Using API key type: {'Anthropic' if 'anthropic' in model.lower() else 'OpenAI'}")
        print(f"🔍 API key validation: {'✅ Valid format' if is_valid_format else '❌ Invalid format'}")
        
        try:
            llm_instance = LLM(model=model, api_key=api_key)
            print(f"✅ LLM instance created successfully")
            return llm_instance
        except Exception as e:
            error_msg = f"Failed to create LLM instance: {e}"
            print(f"❌ {error_msg}")
            raise ValueError(error_msg)

    @agent
    def categorizer(self) -> Agent:
        """The email categorizer agent."""
        config = self.agents_config['categorizer']
        return Agent(
            role=config['role'],
            goal=config['goal'],
            backstory=config['backstory'],
            memory=config.get('memory', True),
            tools=[FileReadTool()],
            llm=self.llm
        )

    @agent
    def organizer(self) -> Agent:
        """The email organizer agent."""
        gmail_tools = self._get_gmail_tools()
        config = self.agents_config['organizer']
        return Agent(
            role=config['role'],
            goal=config['goal'],
            backstory=config['backstory'],
            memory=config.get('memory', True),
            tools=[*gmail_tools, FileReadTool()],
            llm=self.llm
        )

    @agent
    def response_generator(self) -> Agent:
        """The email response generator agent."""
        gmail_tools = self._get_gmail_tools()
        config = self.agents_config['response_generator']
        return Agent(
            role=config['role'],
            goal=config['goal'], 
            backstory=config['backstory'],
            memory=config.get('memory', True),
            tools=[*gmail_tools, FileReadTool()],
            llm=self.llm
        )

    @agent
    def cleaner(self) -> Agent:
        """The email cleanup specialist agent."""
        gmail_tools = self._get_gmail_tools()
        config = self.agents_config['cleaner']
        return Agent(
            role=config['role'],
            goal=config['goal'],
            backstory=config['backstory'],
            memory=config.get('memory', True),
            tools=[*gmail_tools, DateCalculationTool(), FileReadTool()],
            llm=self.llm
        )

    @task
    def categorization_task(self) -> Task:
        """The email categorization task."""
        return Task(
            config=self.tasks_config['categorization_task'],
            agent=self.categorizer(),
            output_file="output/categorization_report.json"
        )

    @task
    def organization_task(self) -> Task:
        """The email organization task."""
        return Task(
            config=self.tasks_config['organization_task'],
            agent=self.organizer(),
            output_file="output/organization_report.json"
        )

    @task
    def response_task(self) -> Task:
        """The email response task."""
        return Task(
            config=self.tasks_config['response_task'],
            agent=self.response_generator(),
            output_file="output/response_report.json"
        )

    @task
    def cleanup_task(self) -> Task:
        """The email cleanup task."""
        return Task(
            config=self.tasks_config['cleanup_task'],
            agent=self.cleaner(),
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


def create_crew_for_user(user_id: str, oauth_manager, user_api_keys: dict = None) -> OAuth2GmailCrewAi:
    """Create and configure a crew for a specific user with OAuth2 authentication.
    
    Args:
        user_id: The unique identifier for the user
        oauth_manager: The OAuth2Manager instance for the user
        user_api_keys: Optional dict with user-specific API keys {'anthropic': 'key', 'openai': 'key'}
        
    Returns:
        OAuth2GmailCrewAi: Configured crew instance for the user
    """
    # Create a new crew instance with the user_id, oauth_manager, and user API keys
    crew_instance = OAuth2GmailCrewAi(user_id=user_id, oauth_manager=oauth_manager, user_api_keys=user_api_keys)
    
    return crew_instance 