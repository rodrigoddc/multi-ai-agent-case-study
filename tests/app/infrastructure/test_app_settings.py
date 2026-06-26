"""Tests for aggregate application settings."""

from src.app.infrastructure.config import AppEnvironment, AppSettings, LLMSettings


def test_app_settings_reads_app_env_from_environment(monkeypatch):
    """APP_ENV is loaded from environment without selecting the LLM provider."""
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    settings = AppSettings()

    assert settings.APP_ENV == AppEnvironment.LOCAL


def test_llm_provider_is_loaded_independently_from_app_env(monkeypatch):
    """LLM_PROVIDER, not APP_ENV, selects the runtime LLM provider."""
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    settings = AppSettings()
    llm_settings = LLMSettings()

    assert settings.APP_ENV == AppEnvironment.LOCAL
    assert llm_settings.LLM_PROVIDER == "openrouter"
