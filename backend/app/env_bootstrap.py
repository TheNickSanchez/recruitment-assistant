"""Load repo-root .env into os.environ (override=True).

Cursor / IDE shells sometimes inject OPENAI_API_KEY=crsr_... which would
otherwise shadow the LiteLLM virtual key in .env when uvicorn --env-file
uses python-dotenv's default no-override behavior (QA DEF-1 follow-up).
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _REPO_ROOT / ".env"
_loaded = False


def load_app_env(*, override: bool = True) -> Path | None:
    """Idempotent. Returns the .env path if it exists and was loaded."""
    global _loaded
    if _loaded:
        return _ENV_FILE if _ENV_FILE.is_file() else None
    if _ENV_FILE.is_file():
        load_dotenv(_ENV_FILE, override=override)
        _loaded = True
        return _ENV_FILE
    _loaded = True
    return None
