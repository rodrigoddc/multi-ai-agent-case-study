"""Test helpers for required AI agent configs."""

from src.app.application.agents.config import (
    AgentConfig,
    AgentConfigRegistry,
    AgentLLMConfig,
)


def agent_config(agent_name: str) -> AgentConfig:
    """Build a valid test config for one LOTR agent."""
    return AgentConfig(
        name=agent_name,
        llm=AgentLLMConfig(
            provider="openrouter",
            model=f"test-{agent_name}-model",
            temperature=0.2,
        ),
        prompt=f"test prompt for {agent_name}",
        tool_selection_prompt=(
            "test tool selector {tool_descriptions} {query}"
            if agent_name == "elrond"
            else None
        ),
        clarification_prompt=(
            "test clarification {available_metrics} {query}"
            if agent_name == "elrond"
            else None
        ),
        clarification_policy=(
            '{"required_slots": ["scope", "date_interval", "metric"], '
            '"scope_terms": ["portfolio", "hotel", "hotels"], '
            '"date_interval_terms": ["current", "latest", "2026"], '
            '"metric_terms": ["revpar", "occupancy", "sentiment"], '
            '"ambiguous_metric_terms": {"revenue": "RevPAR is available"}, '
            '"clarifying_question": "Which hotel or portfolio scope, date interval, and metric should I use?"}'
            if agent_name == "elrond"
            else None
        ),
        plan_prompt=("test plan selector {query}" if agent_name == "gandalf" else None),
    )


def agent_config_registry() -> AgentConfigRegistry:
    """Build a full valid LOTR agent config registry for tests."""
    return AgentConfigRegistry(
        configs={
            name: agent_config(name)
            for name in (
                "gandalf",
                "aragorn",
                "samwise",
                "elrond",
                "bilbo",
                "faramir",
                "radagast",
            )
        }
    )
