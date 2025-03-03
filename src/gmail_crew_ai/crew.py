from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

from gmail_crew_ai.tools.gmail_tools import GetUnreadEmailsTool, SaveDraftTool, GmailOrganizeTool, GmailDeleteTool
from gmail_crew_ai.tools.slack_tool import SlackNotificationTool
from gmail_crew_ai.tools.date_tools import DateCalculationTool

@CrewBase
class GmailCrewAi():
	"""Crew that processes emails."""
	agents_config = 'config/agents.yaml'
	tasks_config = 'config/tasks.yaml'

	@agent
	def categorizer(self) -> Agent:
		"""The email categorizer agent."""
		return Agent(
			config=self.agents_config['categorizer'],
			tools=[GetUnreadEmailsTool()],
		)

	@agent
	def organizer(self) -> Agent:
		"""The email organization agent."""
		return Agent(
			config=self.agents_config['organizer'],
			tools=[GmailOrganizeTool()],
		)
		
	@agent
	def response_generator(self) -> Agent:
		"""The email response generator agent."""
		return Agent(
			config=self.agents_config['response_generator'],
			tools=[SaveDraftTool()],
		)
	
	@agent
	def notifier(self) -> Agent:
		"""The email notification agent."""
		return Agent(
			config=self.agents_config['notifier'],
			tools=[SlackNotificationTool()],
		)

	@agent
	def cleaner(self) -> Agent:
		"""The email cleanup agent."""
		return Agent(
			config=self.agents_config['cleaner'],
			tools=[GmailDeleteTool(), DateCalculationTool()],
		)

	@task
	def categorization_task(self) -> Task:
		"""The email categorization task."""
		return Task(
			config=self.tasks_config['categorization_task'],
		)
	
	@task
	def organization_task(self) -> Task:
		"""The email organization task."""
		return Task(
			config=self.tasks_config['organization_task'],
		)

	@task
	def response_task(self) -> Task:
		"""The email response task."""
		return Task(
			config=self.tasks_config['response_task'],
		)
	
	@task
	def notification_task(self) -> Task:
		"""The email notification task."""
		return Task(
			config=self.tasks_config['notification_task'],
		)

	@task
	def cleanup_task(self) -> Task:
		"""The email cleanup task."""
		return Task(
			config=self.tasks_config['cleanup_task'],
		)

	@crew
	def crew(self) -> Crew:
		"""Creates the email processing crew."""
		return Crew(
			agents=self.agents, # Automatically created by the @agent decorator
			tasks=self.tasks, # Automatically created by the @task decorator
			process=Process.sequential,
			verbose=True,
		)
