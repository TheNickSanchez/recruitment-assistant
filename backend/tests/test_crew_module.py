"""Static regression guard: no LinkedIn tool bound to any agent (SAD §9)."""

from pathlib import Path

CREW_PY = Path(__file__).resolve().parents[1] / "app" / "crew.py"


def test_crew_module_has_no_linkedin_tool():
    source = CREW_PY.read_text().lower()
    assert "linkedintool" not in source


def test_crew_module_uses_sequential_process():
    source = CREW_PY.read_text()
    assert "Process.sequential" in source
    assert "memory=False" in source
