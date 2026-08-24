"""Shared LLM factory for the RecruitmentCrew.

Supports native OpenAI *or* an OpenAI-compatible gateway (LiteLLM proxy, etc.)
via env vars. Cursor API keys (crsr_...) are *not* chat-completions keys and
cannot be used here — see deploy.md.
"""

from __future__ import annotations

import os

from crewai import LLM

from app.logging_config import get_logger

logger = get_logger("llm")

_DEFAULT_MODEL = "gpt-4o"


def _first_env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value is not None and value.strip():
            return value.strip()
    return None


def _normalize_base_url(url: str) -> str:
    """Ensure OpenAI-compatible clients hit .../v1."""
    cleaned = url.rstrip("/")
    if cleaned.endswith("/v1"):
        return cleaned
    return f"{cleaned}/v1"


def get_llm() -> LLM:
    """Build the CrewAI LLM from process environment.

    Env (names only):
      OPENAI_API_KEY /
        LITELLM_API_KEY       required (OpenAI key *or* LiteLLM virtual key)
      OPENAI_MODEL /
        OPENAI_MODEL_NAME     model id the gateway expects (default gpt-4o)
      OPENAI_BASE_URL /
        OPENAI_API_BASE       OpenAI-compatible gateway (…/v1 appended if missing)

    Callers should ensure repo-root `.env` is loaded first (see
    `app.env_bootstrap.load_app_env` in `main.py`).
    """
    # Prefer an explicit LiteLLM key when present so a Cursor-injected
    # OPENAI_API_KEY=crsr_... cannot win.
    api_key = _first_env("LITELLM_API_KEY", "OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY (or LITELLM_API_KEY) is required for the crew LLM"
        )

    if api_key.startswith("crsr_"):
        raise ValueError(
            "OPENAI_API_KEY looks like a Cursor API key (crsr_...). "
            "Cursor keys drive the Cloud Agents API, not OpenAI-compatible "
            "chat completions. Put your LiteLLM virtual key in OPENAI_API_KEY "
            "(or LITELLM_API_KEY) and set OPENAI_BASE_URL to the gateway."
        )

    model = _first_env("OPENAI_MODEL", "OPENAI_MODEL_NAME") or _DEFAULT_MODEL
    base_url = _first_env("OPENAI_BASE_URL", "OPENAI_API_BASE")

    kwargs: dict = {
        "model": model,
        "api_key": api_key,
    }
    if base_url:
        # OpenAI-compatible gateway (LiteLLM proxy, etc.). Force the native
        # OpenAI client path so unknown model ids are not mis-routed.
        kwargs["base_url"] = _normalize_base_url(base_url)
        kwargs["custom_openai"] = True
        logger.info(
            "llm configured via custom gateway model=%s base_url=%s",
            model,
            kwargs["base_url"],
        )
    else:
        logger.info("llm configured via default OpenAI host model=%s", model)

    return LLM(**kwargs)
