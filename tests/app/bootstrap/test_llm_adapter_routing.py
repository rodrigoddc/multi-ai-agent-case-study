"""Tests for bootstrap LLM adapter construction."""

import pytest

from src.app.application.agents.config import (
    AgentConfig,
    AgentConfigRegistry,
    AgentLLMConfig,
)
from src.app.bootstrap.lifespan import _build_llm_adapter, _required_llm_providers
from src.app.infrastructure.adapters.llm_provider_router import LLMProviderRouter


def _agent_config(name: str, provider: str) -> AgentConfig:
    return AgentConfig(
        name=name,
        llm=AgentLLMConfig(
            provider=provider,
            model=f"{provider}-model",
            temperature=0.2,
        ),
        prompt="prompt",
    )


def test_required_llm_providers_reads_agent_configs():
    registry = AgentConfigRegistry(
        configs={
            "gandalf": _agent_config("gandalf", "openrouter"),
            "elrond": _agent_config("elrond", "llamacpp"),
        }
    )

    assert _required_llm_providers(registry) == {"openrouter", "llamacpp"}


def test_build_llm_adapter_supports_llamacpp_only_without_openrouter_credentials():
    registry = AgentConfigRegistry(
        configs={"elrond": _agent_config("elrond", "llamacpp")}
    )

    adapter = _build_llm_adapter(registry)

    assert isinstance(adapter, LLMProviderRouter)


def test_build_llm_adapter_rejects_unsupported_provider():
    registry = AgentConfigRegistry(
        configs={"gandalf": _agent_config("gandalf", "anthropic")}
    )

    with pytest.raises(RuntimeError, match="Unsupported LLM provider"):
        _build_llm_adapter(registry)
