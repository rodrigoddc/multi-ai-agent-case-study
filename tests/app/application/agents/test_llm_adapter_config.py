"""Tests for required model/provider LLM adapter calls."""

from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from src.app.application.agents.base import PortBackedChatModel
from src.app.application.agents.config import AgentConfig, AgentLLMConfig


def test_agent_config_requires_provider_and_model():
    with pytest.raises(ValidationError):
        AgentLLMConfig(temperature=0.2)


@pytest.mark.asyncio
async def test_port_backed_chat_model_requires_model_and_provider():
    llm = AsyncMock()
    llm.generate = AsyncMock(return_value="ok")
    chat_model = PortBackedChatModel(
        llm=llm,
        system_prompt="prompt",
        temperature=0.2,
        model_name="model-a",
        provider="openrouter",
    )

    result = await chat_model.ainvoke("hello")

    assert result.content == "ok"
    llm.generate.assert_awaited_once_with(
        system_prompt="prompt",
        user_message="hello",
        temperature=0.2,
        model="model-a",
        provider="openrouter",
    )


def test_port_backed_chat_model_rejects_missing_model_or_provider():
    with pytest.raises(ValidationError):
        PortBackedChatModel(
            llm=AsyncMock(),
            system_prompt="prompt",
            temperature=0.2,
        )


def test_agent_config_supplies_required_model_provider_to_agent_config():
    config = AgentConfig(
        name="gandalf",
        llm=AgentLLMConfig(
            provider="openrouter",
            model="model-a",
            temperature=0.2,
        ),
        prompt="prompt",
    )

    assert config.llm.model == "model-a"
    assert config.llm.provider == "openrouter"
