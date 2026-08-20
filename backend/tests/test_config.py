"""Unit tests: agent/task YAML config loads and has required shape.

Mapped to PRD FR-1..FR-4 / SAD §9 "Unit tests" and "Runtime-specific checks".
"""

from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parents[1] / "app" / "config"

EXPECTED_AGENTS = {"researcher", "evaluator", "recommender"}
EXPECTED_TASKS = {
    "research_candidates_task",
    "evaluate_and_score_candidates_task",
    "recommend_candidates_task",
}


def _load(name: str) -> dict:
    with (CONFIG_DIR / name).open() as f:
        return yaml.safe_load(f)


def test_exactly_three_agents_configured():
    agents = _load("agents.yaml")
    assert set(agents.keys()) == EXPECTED_AGENTS


def test_exactly_three_tasks_configured():
    tasks = _load("tasks.yaml")
    assert set(tasks.keys()) == EXPECTED_TASKS


def test_each_agent_has_role_goal_backstory():
    agents = _load("agents.yaml")
    for name, agent in agents.items():
        assert agent.get("role"), f"{name} missing role"
        assert agent.get("goal"), f"{name} missing goal"
        assert agent.get("backstory"), f"{name} missing backstory"
        assert agent.get("allow_delegation") is False, (
            f"{name} must have allow_delegation=False per adapter rule"
        )


def test_each_task_has_expected_output_and_agent():
    tasks = _load("tasks.yaml")
    for name, task in tasks.items():
        assert task.get("expected_output"), f"{name} missing expected_output"
        assert task.get("agent") in EXPECTED_AGENTS, f"{name} has unknown agent"


def test_final_task_has_two_item_context_chain():
    tasks = _load("tasks.yaml")
    final_task = tasks["recommend_candidates_task"]
    assert final_task.get("context") == [
        "research_candidates_task",
        "evaluate_and_score_candidates_task",
    ]


def test_no_linkedin_tool_referenced_anywhere():
    agents_text = (CONFIG_DIR / "agents.yaml").read_text().lower()
    tasks_text = (CONFIG_DIR / "tasks.yaml").read_text().lower()
    assert "linkedintool" not in agents_text
    assert "linkedintool" not in tasks_text


REQUISITION_PLACEHOLDERS = {
    "{job_title}",
    "{job_description}",
    "{responsibilities}",
    "{requirements}",
    "{preferred_qualifications}",
    "{perks}",
}


def test_every_requisition_field_is_used_by_at_least_one_task():
    tasks_text = (CONFIG_DIR / "tasks.yaml").read_text()
    for placeholder in REQUISITION_PLACEHOLDERS:
        assert placeholder in tasks_text, (
            f"{placeholder} from the JobRequisition input is never referenced "
            "in any task description/expected_output — it would be silently "
            "dropped from the pipeline"
        )
