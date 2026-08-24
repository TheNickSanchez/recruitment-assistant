"""Unit tests for LLM env wiring (no live provider calls)."""

import pytest

from app.llm import get_llm


def test_get_llm_default_openai_host(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-not-real")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_BASE", raising=False)
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")
    llm = get_llm()
    assert llm.model == "gpt-4o"
    assert getattr(llm, "base_url", None) in (None, "")
    assert getattr(llm, "custom_openai", False) is False


def test_get_llm_litellm_gateway(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-litellm-virtual")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:4000")
    monkeypatch.setenv("OPENAI_MODEL", "claude-sonnet-4-6")
    llm = get_llm()
    assert llm.model == "claude-sonnet-4-6"
    assert llm.base_url == "http://127.0.0.1:4000/v1"
    assert getattr(llm, "custom_openai", False) is True


def test_get_llm_prefers_litellm_key_over_cursor_openai_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "crsr_" + ("a" * 64))
    monkeypatch.setenv("LITELLM_API_KEY", "sk-litellm-virtual")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://llm.example.com/v1")
    monkeypatch.setenv("OPENAI_MODEL", "claude-sonnet-5")
    llm = get_llm()
    assert llm.api_key == "sk-litellm-virtual"
    assert llm.base_url == "https://llm.example.com/v1"


def test_get_llm_rejects_cursor_api_key(monkeypatch):
    monkeypatch.setenv(
        "OPENAI_API_KEY",
        "crsr_" + ("a" * 64),
    )
    with pytest.raises(ValueError, match="Cursor API key"):
        get_llm()


def test_get_llm_requires_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LITELLM_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        get_llm()
