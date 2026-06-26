"""Typed per-agent YAML configuration."""

from __future__ import annotations
import yaml

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AgentLLMConfig(BaseModel):
    """LLM settings owned by one AI agent."""

    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    temperature: float = Field(ge=0.0, le=1.0)


class AgentConfig(BaseModel):
    """Validated runtime configuration for one AI agent."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    llm: AgentLLMConfig
    prompt: str = Field(min_length=1)
    tool_selection_prompt: str | None = None
    plan_prompt: str | None = None
    clarification_prompt: str | None = None
    clarification_policy: str | None = None

    @field_validator(
        "prompt",
        "tool_selection_prompt",
        "plan_prompt",
        "clarification_prompt",
        "clarification_policy",
    )
    @classmethod
    def validate_prompt(cls, value: str | None) -> str | None:
        """Reject blank prompts after YAML whitespace normalization."""
        if value is None:
            return None
        prompt = value.strip()
        if not prompt:
            raise ValueError("agent prompt must not be blank")
        return prompt


class AgentConfigRegistry(BaseModel):
    """Collection of validated AI agent configurations."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    configs: dict[str, AgentConfig]

    @classmethod
    def load(
        cls,
        *,
        config_root: Path,
        environment: str,
        provider: str,
        model: str,
    ) -> "AgentConfigRegistry":
        """Load environment-specific YAML configs with local fallback.

        Args:
            config_root: Directory containing per-environment config directories.
            environment: Requested runtime environment.
            provider: LLM provider from runtime settings.
            model: LLM model from runtime settings.

        Returns:
            Registry keyed by LOTR agent name.
        """
        configs: dict[str, AgentConfig] = {}
        for path in _config_paths(config_root=config_root, environment=environment):
            raw_config = _load_yaml_object(path)
            name = path.stem
            config = AgentConfig(
                name=name,
                llm=AgentLLMConfig(
                    provider=str(raw_config.get("provider", provider)),
                    model=str(raw_config.get("model", model)),
                    temperature=float(raw_config["temperature"]),
                ),
                prompt=str(raw_config["prompt"]),
                tool_selection_prompt=_optional_string(
                    raw_config.get("tool_selection_prompt")
                ),
                plan_prompt=_optional_string(raw_config.get("plan_prompt")),
                clarification_prompt=_optional_string(
                    raw_config.get("clarification_prompt")
                ),
                clarification_policy=_optional_string(
                    raw_config.get("clarification_policy")
                ),
            )
            configs[name] = config
        return cls(configs=configs)

    def require(self, agent_name: str) -> AgentConfig:
        """Return one agent config or fail fast if it is missing."""
        config = self.configs.get(agent_name)
        if config is None:
            raise KeyError(f"Missing AI agent config for {agent_name}")
        return config


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _config_paths(*, config_root: Path, environment: str) -> list[Path]:
    environment_dir = config_root / environment
    paths = {path.stem: path for path in sorted(config_root.glob("*.yml"))}
    if environment_dir != config_root:
        paths.update(
            {path.stem: path for path in sorted(environment_dir.glob("*.yml"))}
        )
    return list(paths.values())


def _load_yaml_object(path: Path) -> dict[str, Any]:

    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError(f"Agent config must be a YAML mapping: {path}")
    return parsed
