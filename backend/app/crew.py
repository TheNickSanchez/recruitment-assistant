"""CrewAI runtime entrypoint for the Recruitment Assistant application crew.

Implements the 3-agent sequential pipeline (Researcher -> Evaluator ->
Recommender) per project-context/1.define/sad.md §2 and the crewai adapter
rule (.cursor/rules/adapter-crewai.mdc).
"""

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import ScrapeWebsiteTool, SerperDevTool

# Adapter rule "Execution" baseline controls (.cursor/rules/adapter-crewai.mdc).
MAX_ITER = 12
MAX_RETRY_LIMIT = 2
MAX_RPM = 20


@CrewBase
class RecruitmentCrew:
    """Researcher -> Evaluator -> Recommender sequential crew."""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    def _tools(self):
        # Least-privilege, shared tool set per SAD §2: SerperDevTool +
        # ScrapeWebsiteTool only. No LinkedIn tool (excluded from MVP scope).
        return [SerperDevTool(), ScrapeWebsiteTool()]

    @agent
    def researcher(self) -> Agent:
        return Agent(
            config=self.agents_config["researcher"],
            tools=self._tools(),
            allow_delegation=False,
            max_iter=MAX_ITER,
            max_retry_limit=MAX_RETRY_LIMIT,
        )

    @agent
    def evaluator(self) -> Agent:
        return Agent(
            config=self.agents_config["evaluator"],
            tools=self._tools(),
            allow_delegation=False,
            max_iter=MAX_ITER,
            max_retry_limit=MAX_RETRY_LIMIT,
        )

    @agent
    def recommender(self) -> Agent:
        return Agent(
            config=self.agents_config["recommender"],
            tools=self._tools(),
            allow_delegation=False,
            max_iter=MAX_ITER,
            max_retry_limit=MAX_RETRY_LIMIT,
        )

    @task
    def research_candidates_task(self) -> Task:
        return Task(config=self.tasks_config["research_candidates_task"])

    @task
    def evaluate_and_score_candidates_task(self) -> Task:
        return Task(
            config=self.tasks_config["evaluate_and_score_candidates_task"]
        )

    @task
    def recommend_candidates_task(self) -> Task:
        return Task(config=self.tasks_config["recommend_candidates_task"])

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            memory=False,
            max_rpm=MAX_RPM,
            verbose=True,
        )


def run_crew(inputs: dict) -> str:
    """Kick off the crew synchronously and return the final markdown report."""
    result = RecruitmentCrew().crew().kickoff(inputs=inputs)
    return str(result)
