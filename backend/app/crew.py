"""CrewAI runtime entrypoint for the Recruitment Assistant application crew.

Implements the 3-agent sequential pipeline (Researcher -> Evaluator ->
Recommender) per project-context/1.define/sad.md §2 and the crewai adapter
rule (.cursor/rules/adapter-crewai.mdc).
"""

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import ScrapeWebsiteTool, SerperDevTool

from app.llm import get_llm
from app.logging_config import env_flag, get_logger

# Adapter rule "Execution" baseline controls (.cursor/rules/adapter-crewai.mdc).
MAX_ITER = 12
MAX_RETRY_LIMIT = 2
MAX_RPM = 20

logger = get_logger("crew")


@CrewBase
class RecruitmentCrew:
    """Researcher -> Evaluator -> Recommender sequential crew."""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    def _tools(self):
        # Least-privilege, shared tool set per SAD §2: SerperDevTool +
        # ScrapeWebsiteTool only. No LinkedIn tool (excluded from MVP scope).
        return [SerperDevTool(), ScrapeWebsiteTool()]

    def _agent_kwargs(self) -> dict:
        return {
            "tools": self._tools(),
            "llm": get_llm(),
            "allow_delegation": False,
            "max_iter": MAX_ITER,
            "max_retry_limit": MAX_RETRY_LIMIT,
        }

    @agent
    def researcher(self) -> Agent:
        return Agent(
            config=self.agents_config["researcher"],
            **self._agent_kwargs(),
        )

    @agent
    def evaluator(self) -> Agent:
        return Agent(
            config=self.agents_config["evaluator"],
            **self._agent_kwargs(),
        )

    @agent
    def recommender(self) -> Agent:
        return Agent(
            config=self.agents_config["recommender"],
            **self._agent_kwargs(),
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
        tracing = env_flag("CREWAI_TRACING_ENABLED")
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            memory=False,
            max_rpm=MAX_RPM,
            verbose=True,
            tracing=tracing,
            task_callback=_log_task_output,
        )


def _log_task_output(output) -> None:
    """Observability only — does not alter task output or agent behavior."""
    name = getattr(output, "name", None) or getattr(output, "description", "")
    agent_role = ""
    agent = getattr(output, "agent", None)
    if agent is not None:
        agent_role = getattr(agent, "role", "") or str(agent)
    summary = str(output)
    logger.info(
        "crew task finished name=%s agent=%s output_chars=%s",
        name or "(unnamed)",
        agent_role or "(unknown)",
        len(summary),
    )


def run_crew(inputs: dict) -> str:
    """Kick off the crew synchronously and return the final markdown report."""
    job_title = inputs.get("job_title", "")
    candidate_count = inputs.get("candidate_count")
    tracing = env_flag("CREWAI_TRACING_ENABLED")
    logger.info(
        "crew kickoff starting job_title=%s candidate_count=%s tracing=%s",
        job_title,
        candidate_count,
        tracing,
    )
    try:
        result = RecruitmentCrew().crew().kickoff(inputs=inputs)
    except Exception:
        logger.exception(
            "crew kickoff failed job_title=%s candidate_count=%s",
            job_title,
            candidate_count,
        )
        raise
    text = str(result)
    logger.info(
        "crew kickoff completed job_title=%s report_chars=%s",
        job_title,
        len(text),
    )
    return text
