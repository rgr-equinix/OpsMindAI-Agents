import os
from crewai import LLM
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

from opsmindai_crew.tools.webhook_alert_parser import WebhookAlertParserTool
from opsmindai_crew.tools.application_log_analyzer import ApplicationLogAnalyzer
from opsmindai_crew.tools.incident_database_tool import IncidentDatabaseTool
from opsmindai_crew.tools.current_date_tool import CurrentDateTool
from opsmindai_crew.tools.slack_message_test_tool import SlackMessageTestTool
from opsmindai_crew.tools.enhanced_github_repository_scanner import EnhancedGitHubRepositoryScanner
from opsmindai_crew.tools.github_pr_creator import GitHubPRCreatorTool
from opsmindai_crew.tools.code_diff_generator import CodeDiffGeneratorTool
from opsmindai_crew.tools.github_repository_analyzer import GitHubRepositoryAnalyzer
from opsmindai_crew.tools.java_npe_diff_generator import JavaNpeDiffGeneratorTool
from opsmindai_crew.tools.github_pr_test_tool import GitHubPRTestTool
from opsmindai_crew.tools.incident_retrospective_generator import IncidentRetrospectiveGenerator
from opsmindai_crew.tools.file_organizer_tool import FileOrganizerTool
from opsmindai_crew.tools.pdf_generator_tool import PDFGeneratorTool
from opsmindai_crew.tools.single_incident_reader import SingleIncidentReader
from opsmindai_crew.tools.timeline_extractor import TimelineExtractor
from opsmindai_crew.tools.slack_file_uploader import SlackFileUploader
from opsmindai_crew.tools.file_to_base64_tool import FileToBase64Tool



@CrewBase
class OpsmindaiCrewCrew:
    """OpsmindaiCrew crew"""

    
    @agent
    def alert_detection_agent(self) -> Agent:
        
        return Agent(
            config=self.agents_config["alert_detection_agent"],
            
            
            tools=[
				WebhookAlertParserTool(),
				ApplicationLogAnalyzer()
            ],
            reasoning=False,
            max_reasoning_attempts=None,
            inject_date=True,
            allow_delegation=False,
            max_iter=25,
            max_rpm=None,
            max_execution_time=None,
            llm=LLM(
                model="ollama/llama3.2:latest",
                temperature=0.7,
            ),
        )
    
    @agent
    def incident_orchestration_manager(self) -> Agent:
        
        return Agent(
            config=self.agents_config["incident_orchestration_manager"],
            
            
            tools=[
				IncidentDatabaseTool(),
				CurrentDateTool(),
				SlackMessageTestTool()
            ],
            reasoning=False,
            max_reasoning_attempts=None,
            inject_date=True,
            allow_delegation=False,
            max_iter=25,
            max_rpm=None,
            max_execution_time=None,
            llm=LLM(
                model="ollama/llama3.2:latest",
                temperature=0.7,
            ),
        )
    
    @agent
    def incident_fix_agent(self) -> Agent:
        
        return Agent(
            config=self.agents_config["incident_fix_agent"],
            
            
            tools=[
				IncidentDatabaseTool(),
				EnhancedGitHubRepositoryScanner(),
				GitHubPRCreatorTool(),
				CodeDiffGeneratorTool(),
				SlackMessageTestTool(),
				GitHubRepositoryAnalyzer(),
				JavaNpeDiffGeneratorTool(),
				GitHubPRTestTool()
            ],
            reasoning=False,
            max_reasoning_attempts=None,
            inject_date=True,
            allow_delegation=False,
            max_iter=25,
            max_rpm=None,
            max_execution_time=None,
            llm=LLM(
                model="ollama/qwen2.5:7b",
                temperature=0.7,
            ),
        )
    
    @agent
    def senior_incident_retrospective_analyst(self) -> Agent:
        
        return Agent(
            config=self.agents_config["senior_incident_retrospective_analyst"],
            
            
            tools=[
                SingleIncidentReader(),
                TimelineExtractor(),
                FileOrganizerTool(), 
                PDFGeneratorTool(),
                FileToBase64Tool(),
                SlackFileUploader()
            ],
            reasoning=False,
            max_reasoning_attempts=None,
            inject_date=True,
            allow_delegation=False,
            max_iter=25,
            max_rpm=None,
            max_execution_time=None,
            llm=LLM(
                model="ollama/qwen2.5:7b", #"ollama/llama3.2:latest",
                temperature=0.7,
            ),
        )
    

    
    @task
    def analyze_application_log_content(self) -> Task:
        return Task(
            config=self.tasks_config["analyze_application_log_content"],
            markdown=False,
        )
    
    @task
    def orchestrate_incident_management_workflow(self) -> Task:
        return Task(
            config=self.tasks_config["orchestrate_incident_management_workflow"],
            markdown=False,
        )
    
    @task
    def complete_incident_resolution_workflow(self) -> Task:
        return Task(
            config=self.tasks_config["complete_incident_resolution_workflow"],
            markdown=False,
        )
    
    @task
    def generate_comprehensive_incident_retrospective_report(self) -> Task:
        return Task(
            config=self.tasks_config["generate_comprehensive_incident_retrospective_report"],
            markdown=False,
        )
    

    @crew
    def crew(self) -> Crew:
        """Creates the OpsmindaiCrew crew"""
        return Crew(
            agents=self.agents,  # Automatically created by the @agent decorator
            tasks=self.tasks,  # Automatically created by the @task decorator
            process=Process.sequential,
            verbose=True,
        )
