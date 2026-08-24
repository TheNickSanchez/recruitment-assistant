"""Unit tests for observability helpers (no live CrewAI / LLM calls)."""

import logging

from app.logging_config import _RedactFilter, env_flag


def test_env_flag_true_values(monkeypatch):
    monkeypatch.setenv("FLAG_X", "true")
    assert env_flag("FLAG_X") is True
    monkeypatch.setenv("FLAG_X", "1")
    assert env_flag("FLAG_X") is True


def test_env_flag_false_and_default(monkeypatch):
    monkeypatch.delenv("FLAG_X", raising=False)
    assert env_flag("FLAG_X", default=False) is False
    monkeypatch.setenv("FLAG_X", "false")
    assert env_flag("FLAG_X", default=True) is False


def test_redact_filter_strips_api_key_like_strings():
    record = logging.LogRecord(
        name="recruitment",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="token sk-abcdefghijklmnopqrstuvwxyz error",
        args=(),
        exc_info=None,
    )
    assert _RedactFilter().filter(record) is True
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in record.msg
    assert "[REDACTED]" in record.msg
