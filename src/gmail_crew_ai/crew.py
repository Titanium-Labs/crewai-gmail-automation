#!/usr/bin/env python
import os
import json
from datetime import datetime, date
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
from gmail_crew_ai.models import EmailDetails, CategorizedEmailsList, OrganizedEmailsList, EmailResponsesList, EmailCleanupReport

@CrewBase
class GmailCrewAi():
	"""Crew that processes emails."""
	agents_config = 'config/agents.yaml'
	tasks_config = 'config/tasks.yaml'

	@before_kickoff
	def fetch_emails(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
		"""Fetch emails before starting the crew and calculate ages."""
		print("Fetching emails before starting the crew...")
		
		# Get the email limit from inputs
		email_limit = inputs.get('email_limit', 5)
		print(f"Fetching {email_limit} emails...")
		
		# Create the output directory if it doesn't exist
		os.makedirs("output", exist_ok=True)
		
		# Use the GetUnreadEmailsTool directly
		email_tool = GetUnreadEmailsTool()
		email_tuples = email_tool._run(limit=email_limit)
		
		# Convert email tuples to EmailDetails objects with pre-calculated ages
		emails = []
		today = date.today()
		for email_tuple in email_tuples:
			email_detail = EmailDetails.from_email_tuple(email_tuple)
			
			# Limit body content to prevent context overflow when agents process the file
			if email_detail.body and len(email_detail.body) > 300:
				email_detail.body = email_detail.body[:300] + "... [Body limited for processing efficiency]"
			
			# Calculate age if date is available
			if email_detail.date:
				try:
					email_date_obj = datetime.strptime(email_detail.date, "%Y-%m-%d").date()
					email_detail.age_days = (today - email_date_obj).days
					print(f"Email date: {email_detail.date}, age: {email_detail.age_days} days")
				except Exception as e:
					print(f"Error calculating age for email date {email_detail.date}: {e}")
					email_detail.age_days = None
			
			emails.append(email_detail.dict())
		
		# Ensure output directory exists
		os.makedirs('output', exist_ok=True)
		
		# Save emails to file with UTF-8 encoding
		with open('output/fetched_emails.json', 'w', encoding='utf-8') as f:
			json.dump(emails, f, indent=2, ensure_ascii=False)
		
		print(f"Fetched and saved {len(emails)} emails to output/fetched_emails.json")
		
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
			llm=self.llm,
		)

	@agent
	def organizer(self) -> Agent:
		"""The email organization agent."""
		return Agent(
			config=self.agents_config['organizer'],
			tools=[GmailOrganizeTool(), FileReadTool()],
			llm=self.llm,
		)
		
	@agent
	def response_generator(self) -> Agent:
		"""The email response generator agent."""
		return Agent(
			config=self.agents_config['response_generator'],
			tools=[SaveDraftTool()],
			llm=self.llm,
		)

	@agent
	def cleaner(self) -> Agent:
		"""The email cleanup agent."""
		return Agent(
			config=self.agents_config['cleaner'],
			tools=[GmailDeleteTool(), EmptyTrashTool()],
			llm=self.llm,
		)

	@task
	def categorization_task(self) -> Task:
		"""The email categorization task."""
		return Task(
			config=self.tasks_config['categorization_task'],
			output_pydantic=CategorizedEmailsList
		)
	
	@task
	def organization_task(self) -> Task:
		"""The email organization task."""
		return Task(
			config=self.tasks_config['organization_task'],
			output_pydantic=OrganizedEmailsList,
		)

	@task
	def response_task(self) -> Task:
		"""The email response task."""
		return Task(
			config=self.tasks_config['response_task'],
			output_pydantic=EmailResponsesList,
		)

	@task
	def cleanup_task(self) -> Task:
		"""The email cleanup task."""
		return Task(
			config=self.tasks_config['cleanup_task'],
			output_pydantic=EmailCleanupReport,
		)

	@crew
	def crew(self) -> Crew:
		"""Creates the email processing crew."""
		return Crew(
			agents=self.agents,
			tasks=self.tasks,
			process=Process.sequential,
			verbose=True
		)

	def _debug_callback(self, event_type, payload):
		"""Debug callback for crew events."""
		if event_type == "task_start":
			print(f"DEBUG: Starting task: {payload.get('task_name')}")
		elif event_type == "task_end":
			print(f"DEBUG: Finished task: {payload.get('task_name')}")
			print(f"DEBUG: Task output type: {type(payload.get('output'))}")
			
			# Add more detailed output inspection
			output = payload.get('output')
			if output:
				if isinstance(output, dict):
					print(f"DEBUG: Output keys: {output.keys()}")
					for key, value in output.items():
						print(f"DEBUG: {key}: {value[:100] if isinstance(value, str) and len(value) > 100 else value}")
				elif isinstance(output, list):
					print(f"DEBUG: Output list length: {len(output)}")
					if output and len(output) > 0:
						print(f"DEBUG: First item type: {type(output[0])}")
						if isinstance(output[0], dict):
							print(f"DEBUG: First item keys: {output[0].keys()}")
				else:
					print(f"DEBUG: Output: {str(output)[:200]}...")
		elif event_type == "agent_start":
			print(f"DEBUG: Agent starting: {payload.get('agent_name')}")
		elif event_type == "agent_end":
			print(f"DEBUG: Agent finished: {payload.get('agent_name')}")
		else:
			print(f"DEBUG: Event {event_type}: {payload}")
