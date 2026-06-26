"""Tests for full-local agent YAML configuration."""

from pathlib import Path

from src.app.application.agents.config import AgentConfigRegistry


def test_local_agent_configs_can_use_runtime_llm_provider_override():
    registry = AgentConfigRegistry.load(
        config_root=Path("config/agents"),
        environment="local",
        provider="openrouter",
        model="runtime-model",
    )

    assert registry.configs
    for config in registry.configs.values():
        assert config.llm.provider == "openrouter"
        assert config.llm.model == "runtime-model"
