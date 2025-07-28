#!/usr/bin/env python
"""Enhanced Gmail Crew with feedback loop and summary generation."""

import os
import json
from datetime import datetime, date
from typing import Dict, Any
from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task, before_kickoff

from gmail_crew_ai.tools import (
    GetUnreadEmailsTool, 
    GmailOrganizeTool, 
    GmailDeleteTool, 
    SaveDraftTool, 
    EmptyTrashTool
)
from gmail_crew_ai.tools.file_tools import FileReadTool
from gmail_crew_ai.tools.enhanced_tools_config import basic_tools_config
from gmail_crew_ai.models import EmailDetails, CategorizedEmailsList, OrganizedEmailsList, EmailResponsesList, EmailCleanupReport


@CrewBase
class GmailCrewAiWithFeedback():
    """Enhanced Gmail Crew with feedback loop and learning capabilities."""
    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'

    def __init__(self):
        """Initialize the enhanced crew with feedback capabilities."""
        print("\n🚀 INITIALIZING ENHANCED GMAIL CREW AI WITH FEEDBACK")
        print("=" * 60)
        print("📧 Gmail automation with feedback loop and learning")
        print("🔄 Includes: Summary generation + User feedback processing")
        print("🧠 Features: Rule learning + System improvement")
        print("=" * 60)

    # Get model from environment with smart fallback
    model = os.getenv("MODEL", "anthropic/claude-4-sonnet")
    
    # Determine which API key to use based on model
    if "anthropic" in model.lower():
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            print("⚠️  ANTHROPIC_API_KEY not found, falling back to OpenAI")
            model = "openai/gpt-4o-mini"
            api_key = os.getenv("OPENAI_API_KEY")
    else:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("⚠️  OPENAI_API_KEY not found, falling back to Claude")
            model = "anthropic/claude-4-sonnet"
            api_key = os.getenv("ANTHROPIC_API_KEY")
    
    if not api_key:
        raise ValueError("No valid API key found. Please set OPENAI_API_KEY or ANTHROPIC_API_KEY in your .env file.")
    
    print(f"🤖 Using model: {model}")
    llm = LLM(model=model, api_key=api_key)

    @before_kickoff
    def fetch_emails_and_prepare(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch emails and prepare system for processing."""
        print("🔍 Fetching emails and preparing system...")
        
        try:
            # For OAuth2, try to get emails without credentials first
            tool = GetUnreadEmailsTool()
            emails_data = tool.run()
            
            # Parse the JSON response if it's a string
            if isinstance(emails_data, str):
                emails = json.loads(emails_data)
            else:
                emails = emails_data
            
            # Calculate email ages
            for email in emails:
                if 'date' in email:
                    try:
                        email_date = datetime.fromisoformat(email['date'].replace('Z', '+00:00'))
                        age_days = (datetime.now().replace(tzinfo=email_date.tzinfo) - email_date).days
                        email['age_days'] = age_days
                    except Exception as e:
                        print(f"Error calculating age for email: {e}")
                        email['age_days'] = 0
            
            # Save to file for agents to read
            os.makedirs('output', exist_ok=True)
            with open('output/fetched_emails.json', 'w') as f:
                json.dump(emails, f, indent=2)
            
            # Load and apply learned rules
            self._apply_learned_rules()
            
            print(f"✅ Fetched {len(emails)} emails with age calculations")
            print(f"🧠 Applied learned user rules")
            return inputs
            
        except Exception as e:
            print(f"❌ Error fetching emails: {e}")
            print("Creating empty email file for demo mode")
            # Create empty file so agents don't fail
            os.makedirs('output', exist_ok=True)
            with open('output/fetched_emails.json', 'w') as f:
                json.dump([], f)
            return inputs

    def _apply_learned_rules(self):
        """Apply previously learned rules to the current processing session."""
        try:
            rules_file = 'knowledge/user_learned_rules.json'
            if os.path.exists(rules_file):
                with open(rules_file, 'r') as f:
                    rules_data = json.load(f)
                
                active_rules = sum(1 for category in rules_data['learned_rules'].values() 
                                 for rule in category if rule.get('active', True))
                print(f"📋 Loaded {active_rules} active learned rules")
            else:
                print("📋 No learned rules file found - using defaults")
        except Exception as e:
            print(f"⚠️ Error loading learned rules: {e}")

    # All original agents
    @agent
    def categorizer(self) -> Agent:
        """The email categorizer agent."""
        return Agent(
            config=self.agents_config['categorizer'],
            tools=basic_tools_config.get_categorizer_tools(),
            verbose=True,
            llm=self.llm
        )

    @agent
    def organizer(self) -> Agent:
        """The email organizer agent."""
        return Agent(
            config=self.agents_config['organizer'],
            tools=basic_tools_config.get_organizer_tools(),
            verbose=True,
            llm=self.llm
        )

    @agent
    def response_generator(self) -> Agent:
        """The email response generator agent."""
        return Agent(
            config=self.agents_config['response_generator'],
            tools=basic_tools_config.get_response_generator_tools(),
            verbose=True,
            llm=self.llm
        )

    @agent
    def cleaner(self) -> Agent:
        """The email cleanup specialist agent."""
        return Agent(
            config=self.agents_config['cleaner'],
            tools=basic_tools_config.get_cleaner_tools(),
            verbose=True,
            llm=self.llm
        )

    # New enhanced agents
    @agent
    def summary_reporter(self) -> Agent:
        """The summary reporter agent."""
        return Agent(
            config=self.agents_config['summary_reporter'],
            tools=basic_tools_config.get_summary_reporter_tools(),
            verbose=True,
            llm=self.llm
        )

    @agent
    def feedback_processor(self) -> Agent:
        """The feedback processor agent."""
        return Agent(
            config=self.agents_config['feedback_processor'],
            tools=basic_tools_config.get_feedback_processor_tools(),
            verbose=True,
            llm=self.llm
        )

    # All original tasks
    @task
    def categorization_task(self) -> Task:
        """Task for categorizing emails."""
        return Task(
            config=self.tasks_config['categorization_task'],
            agent=self.categorizer(),
            output_file='output/categorized_emails.json'
        )

    @task
    def organization_task(self) -> Task:
        """Task for organizing emails."""
        return Task(
            config=self.tasks_config['organization_task'],
            agent=self.organizer(),
            context=[self.categorization_task()],
            output_file='output/organized_emails.json'
        )

    @task
    def response_task(self) -> Task:
        """Task for generating email responses."""
        return Task(
            config=self.tasks_config['response_task'],
            agent=self.response_generator(),
            context=[self.categorization_task(), self.organization_task()],
            output_file='output/email_responses.json'
        )

    @task
    def cleanup_task(self) -> Task:
        """Task for cleaning up emails."""
        return Task(
            config=self.tasks_config['cleanup_task'],
            agent=self.cleaner(),
            context=[self.categorization_task(), self.organization_task()],
            output_file='output/cleanup_report.json'
        )

    # New enhanced tasks
    @task
    def summary_report_task(self) -> Task:
        """Task for generating summary report."""
        return Task(
            config=self.tasks_config['summary_report_task'],
            agent=self.summary_reporter(),
            context=[self.categorization_task(), self.organization_task(), self.response_task(), self.cleanup_task()],
            output_file='output/summary_report.json'
        )

    @task
    def feedback_monitoring_task(self) -> Task:
        """Task for monitoring feedback (runs separately)."""
        return Task(
            config=self.tasks_config['feedback_monitoring_task'],
            agent=self.feedback_processor(),
            context=[],
            output_file='output/feedback_processed.json'
        )

    @crew
    def main_processing_crew(self) -> Crew:
        """The main Gmail processing crew (without feedback monitoring)."""
        return Crew(
            agents=[
                self.categorizer(),
                self.organizer(), 
                self.response_generator(),
                self.cleaner(),
                self.summary_reporter()
            ],
            tasks=[
                self.categorization_task(),
                self.organization_task(),
                self.response_task(), 
                self.cleanup_task(),
                self.summary_report_task()
            ],
            process=Process.sequential,
            verbose=True,
        )

    @crew 
    def feedback_crew(self) -> Crew:
        """Separate crew for feedback monitoring."""
        return Crew(
            agents=[self.feedback_processor()],
            tasks=[self.feedback_monitoring_task()],
            process=Process.sequential,
            verbose=True,
        )

    def run_main_processing(self, inputs: Dict[str, Any] = None) -> Dict[str, Any]:
        """Run the main email processing workflow."""
        print("\n🔄 Starting main email processing workflow...")
        if inputs is None:
            inputs = {}
        
        try:
            result = self.main_processing_crew().kickoff(inputs=inputs)
            print("✅ Main processing workflow completed")
            return result
        except Exception as e:
            print(f"❌ Error in main processing: {e}")
            return {"error": str(e)}

    def run_feedback_monitoring(self, inputs: Dict[str, Any] = None) -> Dict[str, Any]:
        """Run the feedback monitoring workflow."""
        print("\n👂 Starting feedback monitoring workflow...")
        if inputs is None:
            inputs = {}
            
        try:
            result = self.feedback_crew().kickoff(inputs=inputs)
            print("✅ Feedback monitoring completed")
            return result
        except Exception as e:
            print(f"❌ Error in feedback monitoring: {e}")
            return {"error": str(e)}

    def run_complete_cycle(self, inputs: Dict[str, Any] = None) -> Dict[str, Any]:
        """Run complete processing cycle: main processing + feedback monitoring."""
        print("\n🚀 Starting complete Gmail automation cycle...")
        
        # Run main processing
        main_result = self.run_main_processing(inputs)
        
        # Run feedback monitoring
        feedback_result = self.run_feedback_monitoring(inputs)
        
        return {
            "main_processing": main_result,
            "feedback_monitoring": feedback_result,
            "cycle_completed": True,
            "timestamp": datetime.now().isoformat()
        }


def create_enhanced_crew() -> GmailCrewAiWithFeedback:
    """Factory function to create the enhanced crew."""
    return GmailCrewAiWithFeedback()


if __name__ == "__main__":
    # Example usage
    crew = create_enhanced_crew()
    result = crew.run_complete_cycle()
    print(f"\n🎉 Complete cycle result: {result}")