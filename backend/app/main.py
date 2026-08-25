"""FastAPI backend for the Recruitment Assistant (SAD §4).

Endpoints:
  POST /api/runs           - submit a job requisition, get back a run_id
  GET  /api/runs/{run_id}  - poll run status / fetch the final report
  GET  /health             - operational sanity check (SAD §5)
"""

from __future__ import annotations

import logging as std_logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from app.crew import run_crew
from app.env_bootstrap import load_app_env
from app.logging_config import configure_logging, env_flag, get_logger, log_level
from app.models import (
    JobRequisition,
    RunErrorEnvelope,
    RunResultResponse,
    RunSubmissionResponse,
)
from app.run_store import run_store
from app.ssl_bootstrap import configure_ssl
from app.trace_log import log_event

# Prefer repo-root .env over IDE-injected env (e.g. Cursor crsr_ OPENAI_API_KEY).
load_app_env(override=True)
# Corp SSL intercept (Zscaler): CrewAI PlusAPI ignores SSL_CERT_FILE (trust_env=False).
configure_ssl()

logger = get_logger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_app_env(override=True)
    configure_ssl()
    configure_logging()
    logger.info(
        "startup app=%s env=%s runtime=crewai log_level=%s tracing=%s base_url=%s ssl_ca=%s",
        os.getenv("APP_NAME", "Recruitment Assistant"),
        os.getenv("APP_ENV", "development"),
        std_logging.getLevelName(log_level()),
        env_flag("CREWAI_TRACING_ENABLED"),
        os.getenv("OPENAI_BASE_URL") or os.getenv("OPENAI_API_BASE") or "(default OpenAI)",
        os.getenv("SSL_CERT_FILE") or "(default)",
    )
    yield
    logger.info("shutdown")


app = FastAPI(title="Recruitment Assistant API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "unhandled exception method=%s path=%s",
            request.method,
            request.url.path,
        )
        raise
    duration_ms = (time.perf_counter() - start) * 1000
    path = request.url.path
    status = response.status_code
    level = logger.info
    # Health + status polling are high-frequency; keep them off INFO.
    if path == "/health" or (request.method == "GET" and path.startswith("/api/runs/")):
        level = logger.debug
    if status >= 500:
        level = logger.error
    elif status >= 400:
        level = logger.warning
    level(
        "request method=%s path=%s status=%s duration_ms=%.1f",
        request.method,
        path,
        status,
        duration_ms,
    )
    return response


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


def _execute_run(run_id: str, requisition: JobRequisition) -> None:
    run_store.mark_running(run_id)
    log_event(run_id, "run_started", job_title=requisition.title)
    logger.info(
        "crew run started run_id=%s job_title=%s candidate_count=%s",
        run_id,
        requisition.title,
        requisition.candidate_count,
    )
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
        logger.exception(
            "crew run failed run_id=%s job_title=%s",
            run_id,
            requisition.title,
        )
        log_event(run_id, "run_failed", error=str(exc))
        run_store.mark_failed(
            run_id,
            RunErrorEnvelope(code="pipeline_error", message=str(exc)),
        )
        return

    logger.info(
        "crew run succeeded run_id=%s report_chars=%s",
        run_id,
        len(report),
    )
    log_event(run_id, "run_succeeded")
    run_store.mark_succeeded(run_id, report)


@app.post("/api/runs", response_model=RunSubmissionResponse, status_code=202)
def submit_run(
    requisition: JobRequisition, background_tasks: BackgroundTasks
) -> RunSubmissionResponse:
    record = run_store.create()
    logger.info(
        "run submitted run_id=%s job_title=%s candidate_count=%s",
        record.run_id,
        requisition.title,
        requisition.candidate_count,
    )
    log_event(record.run_id, "run_submitted", job_title=requisition.title)
    background_tasks.add_task(_execute_run, record.run_id, requisition)
    return RunSubmissionResponse(run_id=record.run_id, status=record.status)


@app.get("/api/runs/{run_id}", response_model=RunResultResponse)
def get_run(run_id: str) -> RunResultResponse:
    record = run_store.get(run_id)
    if record is None:
        logger.warning("run not found run_id=%s", run_id)
        raise HTTPException(status_code=404, detail="run not found")
    return RunResultResponse(
        run_id=record.run_id,
        status=record.status,
        created_at=record.created_at,
        updated_at=record.updated_at,
        report=record.report,
        error=record.error,
    )
