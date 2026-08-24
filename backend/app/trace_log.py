"""Trace Log persistence per the crewai adapter rule's "Logging" section.

Records lifecycle events (task start/stop, retries, run outcome) for each
run under project-context/2.build/logs, secrets redacted. No Prompt Trace
capture is implemented here (would require a CrewAI step callback wired to
the LLM call) — recorded as a gap in backend.md, not fabricated.
"""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parents[2] / "project-context" / "2.build" / "logs"
_logger = logging.getLogger("recruitment.trace")

_SECRET_PATTERN = re.compile(
    r"(sk-[A-Za-z0-9]{10,}|(?i:api[_-]?key)\s*[=:]\s*\S+)"
)


def _redact(text: str) -> str:
    return _SECRET_PATTERN.sub("[REDACTED]", text)


def log_event(run_id: str, event: str, **details) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "event": event,
        "details": {k: _redact(str(v)) for k, v in details.items()},
    }
    log_file = LOG_DIR / f"{run_id}.jsonl"
    with log_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    _logger.info("run_event run_id=%s event=%s", run_id, event)
