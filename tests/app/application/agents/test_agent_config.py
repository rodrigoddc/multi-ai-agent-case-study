"""Tests for per-agent YAML configuration loading."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from src.app.application.agents.config import (
    AgentConfig,
    AgentConfigRegistry,
    AgentLLMConfig,
)


def test_agent_config_registry_loads_environment_specific_yaml(tmp_path: Path):
    config_root = tmp_path / "agents"
    local_dir = config_root
    prod_dir = config_root / "production"
    local_dir.mkdir(parents=True)
    prod_dir.mkdir(parents=True)
    (local_dir / "gandalf.yml").write_text(
        "provider: openrouter\n"
        "model: local-model\n"
        "temperature: 0.2\n"
        "prompt: |\n"
        "  local prompt\n",
        encoding="utf-8",
    )
    (prod_dir / "gandalf.yml").write_text(
        "provider: llamacpp\n"
        "model: production-model\n"
        "temperature: 0.1\n"
        "prompt: |\n"
        "  production prompt\n"
        "tool_selection_prompt: |\n"
        "  select tools for {query}\n"
        "plan_prompt: |\n"
        "  plan agents for {query}\n",
        encoding="utf-8",
    )

    registry = AgentConfigRegistry.load(
        config_root=config_root,
        environment="production",
        provider="openrouter",
        model="runtime-model",
    )

    config = registry.require("gandalf")
    assert config.name == "gandalf"
    assert config.llm.provider == "llamacpp"
    assert config.llm.model == "production-model"
    assert config.llm.temperature == 0.1
    assert config.prompt == "production prompt"
    assert config.tool_selection_prompt == "select tools for {query}"
    assert config.plan_prompt == "plan agents for {query}"


def test_elrond_local_config_owns_system_and_tool_selection_prompts():
    config_path = Path("config/agents/elrond.yml")

    registry = AgentConfigRegistry.load(
        config_root=config_path.parent,
        environment="local",
        provider="openrouter",
        model="test-model",
    )
    config = registry.require("elrond")

    assert "You are Elrond" in config.prompt
    assert "Ask only when the missing detail would materially change" in config.prompt
    assert config.tool_selection_prompt is not None
    assert "Select Elrond private tools" in config.tool_selection_prompt
    assert "{query}" in config.tool_selection_prompt
    assert "answer_options" in config.tool_selection_prompt
    assert "Current portfolio by RevPAR" not in config.tool_selection_prompt
    formatted = config.tool_selection_prompt.format(
        query="Which hotels are performing best by revenue?",
        tool_descriptions="- get_top_hotels_by_revpar: Read top hotels by RevPAR",
    )
    assert '"tool_names"' in formatted


def test_elrond_tool_selection_prompt_escapes_literal_json_braces():
    config_path = Path("config/agents/elrond.yml")

    registry = AgentConfigRegistry.load(
        config_root=config_path.parent,
        environment="local",
        provider="openrouter",
        model="test-model",
    )
    config = registry.require("elrond")

    assert config.tool_selection_prompt is not None
    formatted = config.tool_selection_prompt.format(
        query="Which hotels are performing best by revenue?",
        tool_descriptions="- get_top_hotels_by_revpar: Read top hotels by RevPAR",
    )
    assert "Which hotels are performing best by revenue?" in formatted
    assert '"tool_names"' in formatted


def test_gandalf_local_config_owns_plan_prompt():
    config_path = Path("config/agents/gandalf.yml")

    registry = AgentConfigRegistry.load(
        config_root=config_path.parent,
        environment="local",
        provider="openrouter",
        model="test-model",
    )
    config = registry.require("gandalf")

    assert config.plan_prompt is not None
    assert "Choose the user's intent" in config.plan_prompt
    assert '"intent"' in config.plan_prompt
    assert "{query}" in config.plan_prompt
    assert "{agent_specs}" in config.plan_prompt


def test_agent_config_registry_falls_back_to_local_yaml(tmp_path: Path):
    config_root = tmp_path / "agents"
    local_dir = config_root
    local_dir.mkdir(parents=True)
    (local_dir / "aragorn.yml").write_text(
        "provider: openrouter\n"
        "model: local-guard-model\n"
        "temperature: 0\n"
        "prompt: |\n"
        "  guard prompt\n",
        encoding="utf-8",
    )

    registry = AgentConfigRegistry.load(
        config_root=config_root,
        environment="staging",
        provider="runtime-provider",
        model="runtime-model",
    )

    config = registry.require("aragorn")
    assert config.llm.provider == "openrouter"
    assert config.llm.model == "local-guard-model"


def test_agent_config_registry_uses_runtime_provider_and_model_as_fallbacks(
    tmp_path: Path,
):
    config_root = tmp_path / "agents"
    config_root.mkdir(parents=True)
    (config_root / "bilbo.yml").write_text(
        "temperature: 0.4\nprompt: |\n  writer prompt\n",
        encoding="utf-8",
    )

    registry = AgentConfigRegistry.load(
        config_root=config_root,
        environment="local",
        provider="openrouter",
        model="runtime-model",
    )

    config = registry.require("bilbo")
    assert config.llm.provider == "openrouter"
    assert config.llm.model == "runtime-model"


def test_agent_config_registry_can_override_only_provider(tmp_path: Path):
    config_root = tmp_path / "agents"
    config_root.mkdir(parents=True)
    (config_root / "elrond.yml").write_text(
        "provider: llamacpp\ntemperature: 0\nprompt: |\n  strategist prompt\n",
        encoding="utf-8",
    )

    registry = AgentConfigRegistry.load(
        config_root=config_root,
        environment="local",
        provider="openrouter",
        model="runtime-model",
    )

    config = registry.require("elrond")
    assert config.llm.provider == "llamacpp"
    assert config.llm.model == "runtime-model"


def test_agent_config_registry_can_override_only_model(tmp_path: Path):
    config_root = tmp_path / "agents"
    config_root.mkdir(parents=True)
    (config_root / "radagast.yml").write_text(
        "model: weather-model\ntemperature: 0.3\nprompt: |\n  weather prompt\n",
        encoding="utf-8",
    )

    registry = AgentConfigRegistry.load(
        config_root=config_root,
        environment="local",
        provider="openrouter",
        model="runtime-model",
    )

    config = registry.require("radagast")
    assert config.llm.provider == "openrouter"
    assert config.llm.model == "weather-model"


def test_agent_config_rejects_invalid_temperature():
    with pytest.raises(ValidationError):
        AgentConfig(
            name="aragorn",
            llm=AgentLLMConfig(
                provider="openrouter",
                model="model",
                temperature=2.0,
            ),
            prompt="prompt",
        )


def test_agent_config_registry_requires_known_agent(tmp_path: Path):
    registry = AgentConfigRegistry(configs={})

    with pytest.raises(KeyError, match="Missing AI agent config"):
        registry.require("gandalf")
