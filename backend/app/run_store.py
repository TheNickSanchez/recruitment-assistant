"""In-memory run store.

No database for MVP (PRD §3, SAD §4 Data Architecture): run state lives
in-process only, for the lifetime of the server process.
"""

import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from app.models import RunErrorEnvelope, RunStatus


@dataclass
class RunRecord:
    run_id: str
    status: RunStatus
    created_at: datetime
    updated_at: datetime
    report: Optional[str] = None
    error: Optional[RunErrorEnvelope] = None


class RunStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._runs: dict[str, RunRecord] = {}

    def create(self) -> RunRecord:
        now = datetime.now(timezone.utc)
        record = RunRecord(
            run_id=str(uuid.uuid4()),
            status=RunStatus.pending,
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._runs[record.run_id] = record
        return record

    def get(self, run_id: str) -> Optional[RunRecord]:
        with self._lock:
            return self._runs.get(run_id)

    def mark_running(self, run_id: str) -> None:
        self._update(run_id, status=RunStatus.running)

    def mark_succeeded(self, run_id: str, report: str) -> None:
        self._update(run_id, status=RunStatus.succeeded, report=report)

    def mark_failed(self, run_id: str, error: RunErrorEnvelope) -> None:
        self._update(run_id, status=RunStatus.failed, error=error)

    def _update(self, run_id: str, **fields) -> None:
        with self._lock:
            record = self._runs.get(run_id)
            if record is None:
                return
            for key, value in fields.items():
                setattr(record, key, value)
            record.updated_at = datetime.now(timezone.utc)


run_store = RunStore()
