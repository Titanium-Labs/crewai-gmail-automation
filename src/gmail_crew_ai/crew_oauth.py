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
    from .utils.email_tracker import EmailTracker
    OAUTH2_AVAILABLE = True
except ImportError:
    print("⚠️ OAuth2 tools not available. Please check your setup.")
    # Set dummy classes to None to avoid unbound variable errors
    OAuth2GetUnreadEmailsTool = None  # type: ignore
    OAuth2GmailOrganizeTool = None  # type: ignore
    OAuth2GmailDeleteTool = None  # type: ignore
    OAuth2SaveDraftTool = None  # type: ignore
    EmailTracker = None  # type: ignore
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
        
        # Initialize email tracker for this user
        self.email_tracker = EmailTracker(self.user_id) if EmailTracker else None
            
        # Silently use OAuth2 authentication
        pass
        
        if not OAUTH2_AVAILABLE:
            raise ImportError("OAuth2Manager not available. Please check your OAuth2 setup.")
        
        # Setup LLM with user-specific API keys
        try:
            self.llm = self._setup_llm()
            pass  # LLM setup completed
        except Exception as e:
            # Log error without printing to UI
            raise
            
        # Initialize OAuth2Manager if not provided
        if not self.oauth_manager:
            self.oauth_manager = OAuth2Manager()

    def _get_gmail_tools(self):
        """Get OAuth2 Gmail tools."""
        if not OAUTH2_AVAILABLE:
            raise ImportError("OAuth2 Gmail tools not available. Please check your setup.")
            
        # Do NOT include OAuth2GetUnreadEmailsTool here to prevent agents from fetching emails
        # Emails are already fetched once in prepare_emails() before crew starts
        return [
            OAuth2GmailOrganizeTool(user_id=self.user_id, oauth_manager=self.oauth_manager),
            OAuth2GmailDeleteTool(user_id=self.user_id, oauth_manager=self.oauth_manager),
            OAuth2SaveDraftTool(user_id=self.user_id, oauth_manager=self.oauth_manager),
            OAuth2EmptyTrashTool(user_id=self.user_id, oauth_manager=self.oauth_manager)
        ]

    @before_kickoff
    def prepare_emails(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch emails using OAuth2 authentication."""
        # Fetching emails using OAuth2
        
        # Ensure output directory exists
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        
        # Get email limit from inputs (default to 10 for OAuth2)
        email_limit = inputs.get('email_limit', 10)
        # Processing emails

        try:
            # Get OAuth2 email tool
            if not OAUTH2_AVAILABLE:
                raise ImportError("OAuth2GetUnreadEmailsTool not available")
                
            tool = OAuth2GetUnreadEmailsTool(user_id=self.user_id, oauth_manager=self.oauth_manager)

            # Fetch emails
            raw_emails = tool._run(max_emails=email_limit)
            
            if not raw_emails:
                # No unread emails found
                return inputs

            # Filter out already-processed emails if tracker is available
            emails_to_process = []
            skipped_count = 0
            
            if self.email_tracker:
                print(f"📊 Checking for previously processed emails...")
                for subject, sender, body, email_id, thread_info in raw_emails:
                    if not self.email_tracker.is_processed(email_id):
                        emails_to_process.append((subject, sender, body, email_id, thread_info))
                    else:
                        skipped_count += 1
                        print(f"⏭️  Skipping already-processed email: {subject[:50]}...")
                
                if skipped_count > 0:
                    print(f"✅ Skipped {skipped_count} previously processed email(s)")
                    stats = self.email_tracker.get_statistics()
                    print(f"📈 Total emails tracked: {stats['total_tracked']}, Duplicates skipped: {stats['duplicates_skipped']}")
            else:
                emails_to_process = raw_emails
            
            if not emails_to_process:
                print("ℹ️  All fetched emails have been previously processed")
                return inputs

            # Process emails into EmailDetails format
            emails = []
            processed_ids = []
            for subject, sender, body, email_id, thread_info in emails_to_process:
                processed_ids.append(email_id)
                # Limit body content to optimize token usage (targeting 500-1000 tokens per email)
                # Keep only first 200 characters which should contain the most important content
                limited_body = body[:200] + "... [Body truncated for efficiency]" if len(body) > 200 else body
                
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
                    # Error calculating age for email date
                    email_detail.age_days = None

                emails.append(email_detail.dict())

            # Save emails to file with UTF-8 encoding
            with open('output/fetched_emails.json', 'w', encoding='utf-8') as f:
                json.dump(emails, f, indent=2, ensure_ascii=False)

            # Store processed email IDs for later tracking
            inputs['processed_email_ids'] = processed_ids
            
            # Fetched and saved emails to output/fetched_emails.json
            return inputs

        except Exception as e:
            # Error fetching emails
            return inputs

    def _setup_llm(self):
        """Setup LLM with user-specific API keys and environment fallback."""
        # Ensure environment variables are loaded with override
        load_dotenv(override=True)
        
        # Get model from environment with smart fallback
        model = os.getenv("MODEL", "openai/gpt-4.1")
        
        # Check if we're in a rate limit retry scenario
        if os.getenv("RATE_LIMIT_FALLBACK") == "true":
            # Switch to OpenAI model as fallback
            if "claude" in model.lower() or "anthropic" in model.lower():
                model = "openai/gpt-4-turbo-preview"
                print(f"Rate limit detected, switching to fallback model: {model}")
        
        # Helper function to get API key with user preference and environment fallback
        def get_api_key_with_fallback(key_type: str) -> str:
            # Try user-specific key first
            if self.user_api_keys and key_type in self.user_api_keys and self.user_api_keys[key_type]:
                pass  # Using user's API key
                return self.user_api_keys[key_type]
            
            # Fallback to environment key
            env_key = os.getenv(f"{key_type.upper()}_API_KEY")
            if env_key:
                pass  # Using default API key from environment
                return env_key
            
            return None
        
        # Determine which API key to use based on model
        if "do-ai" in model.lower():
            api_key = get_api_key_with_fallback("do_ai")
            if not api_key:
                pass  # No DO AI API key, falling back to OpenAI
                model = "openai/gpt-4.1"
                api_key = get_api_key_with_fallback("openai")
        elif "anthropic" in model.lower():
            api_key = get_api_key_with_fallback("anthropic")
            if not api_key:
                pass  # No Anthropic API key, falling back to OpenAI
                model = "openai/gpt-4o-mini"
                api_key = get_api_key_with_fallback("openai")
            else:
                # Validate Anthropic API key format
                if not api_key.startswith("sk-ant-"):
                    pass  # Invalid Anthropic API key format, falling back
                    model = "openai/gpt-4o-mini"
                    api_key = get_api_key_with_fallback("openai")
        else:
            api_key = get_api_key_with_fallback("openai")
            if not api_key:
                pass  # No OpenAI API key, falling back to Claude
                model = "anthropic/claude-3-5-sonnet-latest"
                api_key = get_api_key_with_fallback("anthropic")
            else:
                # Validate OpenAI API key format
                if not api_key.startswith("sk-"):
                    pass  # Invalid OpenAI API key format, falling back
                    model = "anthropic/claude-3-5-sonnet-20241022"
                    api_key = get_api_key_with_fallback("anthropic")
        
        if not api_key:
            error_msg = "No valid API key found. Please configure API keys in settings or set DO_AI_API_KEY, OPENAI_API_KEY or ANTHROPIC_API_KEY in your .env file."
            pass  # Error message
            raise ValueError(error_msg)
        
        # Validate API key format more thoroughly
        is_valid_format = False
        if "do-ai" in model.lower():
            # DO AI model is deprecated, switch to OpenAI
            print(f"DO AI model '{model}' is no longer supported, switching to OpenAI")
            model = "openai/gpt-4.1"
            api_key = get_api_key_with_fallback("openai")
            if not api_key:
                raise ValueError("No OpenAI API key found for fallback")
            is_valid_format = api_key.startswith("sk-")
        elif "anthropic" in model.lower() and api_key.startswith("sk-ant-"):
            is_valid_format = True
        elif "openai" in model.lower() and api_key.startswith("sk-"):
            is_valid_format = True
            
        if not is_valid_format:
            error_msg = f"Invalid API key format for {model}. Anthropic keys should start with 'sk-ant-', OpenAI keys should start with 'sk-'."
            pass  # Error message
            raise ValueError(error_msg)
        
        # Model and API key setup complete
        
        try:
            # Create LLM instance
            llm_instance = LLM(model=model, api_key=api_key)
            pass  # LLM instance created
            
            # Test the API key by making a simple completion request
            try:
                # Testing API key validity
                test_response = llm_instance.call(messages=[{"role": "user", "content": "test"}])
                pass  # API key validated
            except Exception as api_error:
                error_str = str(api_error)
                if "authentication" in error_str.lower() or "invalid x-api-key" in error_str.lower():
                    error_msg = f"API key authentication failed. The {('Anthropic' if 'anthropic' in model.lower() else 'OpenAI')} API key is invalid or expired. Please update your API key."
                    pass  # Error message
                    raise ValueError(error_msg)
                elif "rate_limit" in error_str.lower() or "rate limit" in error_str.lower():
                    # Handle rate limit by switching to fallback model
                    if "anthropic" in model.lower():
                        print(f"Rate limit hit for {model}, switching to OpenAI fallback")
                        model = "openai/gpt-4o-mini"
                        api_key = get_api_key_with_fallback("openai")
                        if api_key:
                            llm_instance = LLM(model=model, api_key=api_key)
                            return llm_instance
                    error_msg = f"Rate limit exceeded. Please try again later or switch to a different model."
                    raise ValueError(error_msg)
                else:
                    # Re-raise other errors
                    raise
            
            return llm_instance
        except Exception as e:
            error_msg = f"Failed to create LLM instance: {e}"
            pass  # Error message
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
        # Add search tool specifically for context research before replies
        search_tool = OAuth2GetUnreadEmailsTool(user_id=self.user_id, oauth_manager=self.oauth_manager)
        config = self.agents_config['response_generator']
        return Agent(
            role=config['role'],
            goal=config['goal'], 
            backstory=config['backstory'],
            memory=config.get('memory', True),
            tools=[*gmail_tools, search_tool, FileReadTool()],
            llm=self.llm,
            allow_delegation=False,  # Explicitly disable delegation to ensure tools are used directly
            verbose=True,  # Enable verbose mode to see tool execution
            max_iter=10,  # Allow more iterations for tool execution
            max_execution_time=600  # Allow up to 10 minutes for execution
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
            verbose=False
        )

    def get_user_email(self) -> str:
        """Get user email from OAuth2 manager."""
        if not OAUTH2_AVAILABLE or not self.oauth_manager:
            return "unknown@user.com"
            
        try:
            return self.oauth_manager.get_user_email()
        except Exception as e:
            # Error getting user email
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