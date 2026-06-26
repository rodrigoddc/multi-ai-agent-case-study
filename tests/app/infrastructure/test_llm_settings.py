"""Tests for generic LLM provider settings."""

from src.app.infrastructure.config import LLMSettings


def test_openrouter_llm_settings_load_api_key_from_env_or_dotenv():
    """OpenRouter settings are loaded by BaseSettings from env/.env."""
    settings = LLMSettings(LLM_PROVIDER="openrouter")

    assert settings.LLM_PROVIDER == "openrouter"
    assert settings.LLM_PROVIDER_API_KEY is not None


def test_llamacpp_llm_settings_load_provider_from_env_or_constructor():
    """LLM_PROVIDER controls local llama.cpp selection independently of APP_ENV."""
    settings = LLMSettings(LLM_PROVIDER="llamacpp")

    assert settings.LLM_PROVIDER == "llamacpp"
    assert settings.LLM_PROVIDER_API_KEY is not None
