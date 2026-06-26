"""Tests for per-agent LLM provider routing."""

from __future__ import annotations

import logging
from typing import Any

import pytest

from src.app.infrastructure.adapters.llm_provider_router import LLMProviderRouter


class FakeLLMAdapter:
    """Fake adapter that records generate calls."""

    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []
        self.last_usage: dict[str, int | float] | None = None

    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float,
        model: str,
        provider: str,
        config: dict[str, Any] | None = None,
    ) -> str:
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_message": user_message,
                "temperature": temperature,
                "model": model,
                "provider": provider,
                "config": config,
            }
        )
        self.last_usage = {
            "input_tokens": 1,
            "output_tokens": 2,
            "total_tokens": 3,
        }
        return self.response


@pytest.mark.asyncio
async def test_llm_provider_router_routes_to_selected_provider():
    openrouter = FakeLLMAdapter("remote")
    llamacpp = FakeLLMAdapter("local")
    router = LLMProviderRouter(
        {
            "openrouter": openrouter,
            "llamacpp": llamacpp,
        }
    )

    result = await router.generate(
        system_prompt="system",
        user_message="hello",
        temperature=0.1,
        model="local-model",
        provider="llamacpp",
        config={"tags": ["test"]},
    )

    assert result == "local"
    assert openrouter.calls == []
    assert llamacpp.calls == [
        {
            "system_prompt": "system",
            "user_message": "hello",
            "temperature": 0.1,
            "model": "local-model",
            "provider": "llamacpp",
            "config": {"tags": ["test"]},
        }
    ]


@pytest.mark.asyncio
async def test_llm_provider_router_logs_selected_provider_and_model(caplog):
    adapter = FakeLLMAdapter("ok")
    router = LLMProviderRouter({"openrouter": adapter})

    with caplog.at_level(logging.INFO):
        await router.generate(
            system_prompt="system",
            user_message="hello",
            temperature=0.2,
            model="remote-model",
            provider="openrouter",
        )

    logs = "\n".join(record.message for record in caplog.records)
    assert "Dispatching LLM request provider=openrouter model=remote-model" in logs
    assert "adapter=FakeLLMAdapter" in logs
    assert "Completed LLM request provider=openrouter model=remote-model" in logs


@pytest.mark.asyncio
async def test_llm_provider_router_preserves_selected_adapter_usage():
    adapter = FakeLLMAdapter("ok")
    router = LLMProviderRouter({"openrouter": adapter})

    await router.generate(
        system_prompt="system",
        user_message="hello",
        temperature=0.2,
        model="remote-model",
        provider="openrouter",
    )

    assert router.last_usage == {
        "input_tokens": 1,
        "output_tokens": 2,
        "total_tokens": 3,
    }


@pytest.mark.asyncio
async def test_llm_provider_router_rejects_unknown_provider():
    router = LLMProviderRouter({})

    with pytest.raises(RuntimeError, match="Unsupported LLM provider: anthropic"):
        await router.generate(
            system_prompt="system",
            user_message="hello",
            temperature=0.2,
            model="claude",
            provider="anthropic",
        )
