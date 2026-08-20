"""FastAPI backend for the Recruitment Assistant (SAD §4).

Endpoints:
  POST /api/runs           - submit a job requisition, get back a run_id
  GET  /api/runs/{run_id}  - poll run status / fetch the final report
  GET  /health             - operational sanity check (SAD §5)
"""

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.crew import run_crew
from app.models import (
    JobRequisition,
    RunErrorEnvelope,
    RunResultResponse,
    RunSubmissionResponse,
)
from app.run_store import run_store
from app.trace_log import log_event

app = FastAPI(title="Recruitment Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


def _execute_run(run_id: str, requisition: JobRequisition) -> None:
    run_store.mark_running(run_id)
    log_event(run_id, "run_started", job_title=requisition.title)
    try:
        report = run_crew(
            inputs={
                "job_title": requisition.title,
                "job_description": requisition.description,
                "responsibilities": requisition.responsibilities,
                "requirements": requisition.requirements,
                "preferred_qualifications": requisition.preferred_qualifications,
                "perks": requisition.perks,
                "candidate_count": requisition.candidate_count,
            }
        )
    except Exception as exc:  # noqa: BLE001 - surface any pipeline failure as a failed run
        log_event(run_id, "run_failed", error=str(exc))
        run_store.mark_failed(
            run_id,
            RunErrorEnvelope(code="pipeline_error", message=str(exc)),
        )
        return

    log_event(run_id, "run_succeeded")
    run_store.mark_succeeded(run_id, report)


@app.post("/api/runs", response_model=RunSubmissionResponse, status_code=202)
def submit_run(
    requisition: JobRequisition, background_tasks: BackgroundTasks
) -> RunSubmissionResponse:
    record = run_store.create()
    log_event(record.run_id, "run_submitted", job_title=requisition.title)
    background_tasks.add_task(_execute_run, record.run_id, requisition)
    return RunSubmissionResponse(run_id=record.run_id, status=record.status)


@app.get("/api/runs/{run_id}", response_model=RunResultResponse)
def get_run(run_id: str) -> RunResultResponse:
    record = run_store.get(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="run not found")
    return RunResultResponse(
        run_id=record.run_id,
        status=record.status,
        created_at=record.created_at,
        updated_at=record.updated_at,
        report=record.report,
        error=record.error,
    )
