"""AI provider selection + graceful no-key fallback (Task 5).

Gemini is the documented default, but a solo researcher with no API key must
still get a working extractor. ``_build_provider`` (and the parallel
``build_assistant``) must degrade to the offline heuristic instead of raising.
"""
from __future__ import annotations

import importlib

import pytest

from app.ai import service as ai_service_mod
from app.ai.assistant import HeuristicAssistant, build_assistant
from app.ai.heuristic import HeuristicExtractor


def _reload_config(monkeypatch, **env):
    """Rebuild the cached Settings with the given env overrides applied.

    Note: ``monkeypatch.delenv`` only clears the OS env var — pydantic-settings
    then falls back to any value in ``.env`` (this repo's .env carries a real
    GEMINI_API_KEY). To simulate "no key" deterministically, pass an empty
    string, which is set in the OS env (overriding .env) and is falsy.
    """
    for key, value in env.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    import app.core.config as config_mod

    config_mod.get_settings.cache_clear()
    importlib.reload(config_mod)
    return config_mod.settings


def test_default_provider_is_gemini(monkeypatch):
    settings = _reload_config(monkeypatch, AI_PROVIDER=None, GEMINI_API_KEY=None)
    assert settings.AI_PROVIDER == "gemini"


def test_gemini_without_key_falls_back_to_heuristic(monkeypatch):
    """Selecting gemini with no key must not raise — it degrades to heuristic."""
    _reload_config(monkeypatch, AI_PROVIDER="gemini", GEMINI_API_KEY="")
    importlib.reload(ai_service_mod)

    provider = ai_service_mod._build_provider()
    assert isinstance(provider, HeuristicExtractor)
    assert provider.name == "heuristic"


def test_assistant_without_key_falls_back_to_heuristic(monkeypatch):
    _reload_config(monkeypatch, AI_PROVIDER="gemini", GEMINI_API_KEY="")
    assert isinstance(build_assistant(), HeuristicAssistant)


@pytest.mark.asyncio
async def test_fallback_extractor_still_extracts(monkeypatch):
    """The fallback path is a real extractor, not a stub — it produces output."""
    _reload_config(monkeypatch, AI_PROVIDER="gemini", GEMINI_API_KEY="")
    importlib.reload(ai_service_mod)

    svc = ai_service_mod.AIService()
    result = await svc.extract("Jane Powell founded Acme Corporation in 2010.")
    assert svc.provider_name == "heuristic"
    assert any(e.name for e in result.entities)


@pytest.fixture(autouse=True)
def _restore_config(monkeypatch):
    """After each test, restore the test-suite default (heuristic) settings."""
    yield
    monkeypatch.setenv("AI_PROVIDER", "heuristic")
    import app.core.config as config_mod

    config_mod.get_settings.cache_clear()
    importlib.reload(config_mod)
    importlib.reload(ai_service_mod)
