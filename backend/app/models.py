"""Pydantic request/response models for the run submission API.

Field set matches PRD FR-1 / SAD §4: title, description, responsibilities,
requirements, preferred qualifications, perks.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class JobRequisition(BaseModel):
    title: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    responsibilities: str = ""
    requirements: str = ""
    preferred_qualifications: str = ""
    perks: str = ""
    candidate_count: int = Field(default=10, ge=1, le=25)


class RunSubmissionResponse(BaseModel):
    run_id: str
    status: RunStatus


class RunErrorEnvelope(BaseModel):
    code: str
    message: str


class RunResultResponse(BaseModel):
    run_id: str
    status: RunStatus
    created_at: datetime
    updated_at: datetime
    report: Optional[str] = None
    error: Optional[RunErrorEnvelope] = None
