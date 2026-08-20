"""Integration tests for the FastAPI run-submission/status API (SAD §9).

The crew's `run_crew` is monkeypatched to avoid real LLM/search API calls and
nondeterminism in CI, per SAD §9 "Integration tests" guidance.
"""

import time

import pytest
from fastapi.testclient import TestClient

from app import main


@pytest.fixture(autouse=True)
def _fresh_run_store():
    main.run_store._runs.clear()
    yield
    main.run_store._runs.clear()


@pytest.fixture(autouse=True)
def _stub_run_crew(monkeypatch):
    """Never hit the real CrewAI/LLM/search pipeline in this test module.

    Per SAD §9 "Integration tests": mock/stub LLM and search/scrape tool
    responses to avoid real API cost and nondeterminism in CI. Individual
    tests may override this with their own monkeypatch.setattr call.
    """
    monkeypatch.setattr(main, "run_crew", lambda inputs: "stub report")


@pytest.fixture
def client():
    return TestClient(main.app)


VALID_REQUISITION = {
    "title": "Senior Backend Engineer",
    "description": "Own the recruitment assistant backend.",
    "responsibilities": "Design and ship APIs.",
    "requirements": "5+ years Python.",
    "preferred_qualifications": "CrewAI experience.",
    "perks": "Remote friendly.",
}


def test_health_check(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_submit_run_missing_required_fields_returns_422(client):
    resp = client.post("/api/runs", json={"perks": "no title or description"})
    assert resp.status_code == 422


def test_submit_run_returns_pending_run_id(client):
    resp = client.post("/api/runs", json=VALID_REQUISITION)
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "pending"
    assert body["run_id"]


def test_get_unknown_run_returns_404(client):
    resp = client.get("/api/runs/does-not-exist")
    assert resp.status_code == 404


def test_full_run_lifecycle_succeeds(client, monkeypatch):
    monkeypatch.setattr(
        main,
        "run_crew",
        lambda inputs: "## Recommendations\n...\n## Outreach Guidance\n...",
    )

    submit_resp = client.post("/api/runs", json=VALID_REQUISITION)
    run_id = submit_resp.json()["run_id"]

    deadline = time.time() + 5
    status = None
    body = {}
    while time.time() < deadline:
        result_resp = client.get(f"/api/runs/{run_id}")
        assert result_resp.status_code == 200
        body = result_resp.json()
        status = body["status"]
        if status == "succeeded":
            break
        time.sleep(0.05)

    assert status == "succeeded"
    assert "## Recommendations" in body["report"]
    assert "## Outreach Guidance" in body["report"]


def test_full_run_lifecycle_reports_failure(client, monkeypatch):
    def _boom(inputs):
        raise RuntimeError("tool binding error")

    monkeypatch.setattr(main, "run_crew", _boom)

    submit_resp = client.post("/api/runs", json=VALID_REQUISITION)
    run_id = submit_resp.json()["run_id"]

    deadline = time.time() + 5
    status = None
    body = {}
    while time.time() < deadline:
        result_resp = client.get(f"/api/runs/{run_id}")
        body = result_resp.json()
        status = body["status"]
        if status == "failed":
            break
        time.sleep(0.05)

    assert status == "failed"
    assert body["error"]["code"] == "pipeline_error"
