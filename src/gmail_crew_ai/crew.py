#!/usr/bin/env python
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
class GmailCrewAi():
	"""Gmail Crew with basic tools (without embedchain dependency)."""
	agents_config = 'config/agents.yaml'
	tasks_config = 'config/tasks.yaml'

	def __init__(self):
		"""Initialize the crew and display available tools."""
		print("\n🚀 INITIALIZING GMAIL CREW AI")
		print("=" * 50)
		print("📧 Gmail automation with basic tools")
		print("⚠️  Note: Advanced tools disabled due to embedchain dependency conflicts")
		print("=" * 50)

	llm = LLM(
		model="openai/gpt-4o-mini",
		api_key=os.getenv("OPENAI_API_KEY"),
	)

	@before_kickoff
	def fetch_emails(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
		"""Fetch emails before starting the crew and calculate ages."""
		print("Fetching emails and calculating ages...")
		
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
			
			print(f"✅ Fetched {len(emails)} emails with age calculations")
			return inputs
			
		except Exception as e:
			print(f"❌ Error fetching emails: {e}")
			print("Creating empty email file for demo mode")
			# Create empty file so agents don't fail
			os.makedirs('output', exist_ok=True)
			with open('output/fetched_emails.json', 'w') as f:
				json.dump([], f)
			return inputs

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

	@crew
	def crew(self) -> Crew:
		"""The Gmail automation crew."""
		return Crew(
			agents=self.agents,
			tasks=self.tasks,
			process=Process.sequential,
			verbose=True,
		)
