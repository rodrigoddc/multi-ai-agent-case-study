"""Tests for the local llama.cpp LLM adapter."""

from types import SimpleNamespace

import httpx
import pytest

from src.app.application.services.chat_service import LLMProviderUnavailableError
from src.app.infrastructure.adapters.llamacpp_adapter import (
    LlamaCppAdapter,
    _extract_chat_content,
)
from src.app.infrastructure.config import LlamaCppSettings


class FakeAsyncClient:
    """Tiny httpx.AsyncClient stand-in for adapter tests."""

    def __init__(self, response: object) -> None:
        self.response = response
        self.requests: list[dict[str, object]] = []

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def post(self, url: str, json: dict[str, object]) -> object:
        self.requests.append({"url": url, "json": json})
        return self.response


class FakeResponse:
    """Minimal HTTP response object for llama.cpp adapter tests."""

    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.raise_for_status_called = False

    def raise_for_status(self) -> None:
        self.raise_for_status_called = True

    def json(self) -> dict[str, object]:
        return self.payload


class FailingAsyncClient:
    """HTTP client stand-in that simulates a down llama.cpp server."""

    async def __aenter__(self) -> "FailingAsyncClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def post(self, url: str, json: dict[str, object]) -> object:
        request = httpx.Request("POST", url)
        raise httpx.ConnectError("All connection attempts failed", request=request)


@pytest.mark.asyncio
async def test_llamacpp_adapter_calls_openai_compatible_chat_completions():
    response = FakeResponse({"choices": [{"message": {"content": "local answer"}}]})
    client = FakeAsyncClient(response=response)
    adapter = LlamaCppAdapter(
        settings=LlamaCppSettings(
            LLAMACPP_BASE_URL="http://localhost:8080",
            LLM_PROVIDER_MODEL="gemma-4-12B-it-qat-UD-Q4_K_XL.gguf",
        ),
        client_factory=lambda: client,
    )

    result = await adapter.generate(
        system_prompt="system",
        user_message="hello",
        temperature=0.2,
        model="gemma-4-12B-it-qat-UD-Q4_K_XL.gguf",
        provider="llamacpp",
    )

    assert result == "local answer"
    assert response.raise_for_status_called is True
    assert client.requests == [
        {
            "url": "http://localhost:8080/v1/chat/completions",
            "json": {
                "model": "gemma-4-12B-it-qat-UD-Q4_K_XL.gguf",
                "messages": [
                    {"role": "system", "content": "system"},
                    {"role": "user", "content": "hello"},
                ],
                "temperature": 0.2,
                "stream": False,
                "max_tokens": 1024,
            },
        }
    ]


@pytest.mark.asyncio
async def test_llamacpp_adapter_rejects_non_local_provider():
    adapter = LlamaCppAdapter(
        settings=LlamaCppSettings(
            LLAMACPP_BASE_URL="http://localhost:8080",
            LLM_PROVIDER_MODEL="gemma-4-12B-it-qat-UD-Q4_K_XL.gguf",
        ),
        client_factory=lambda: FakeAsyncClient(response=SimpleNamespace()),
    )

    with pytest.raises(RuntimeError, match="Unsupported LLM provider"):
        await adapter.generate(
            system_prompt="system",
            user_message="hello",
            temperature=0.2,
            model="gemma-4-12B-it-qat-UD-Q4_K_XL.gguf",
            provider="openrouter",
        )


@pytest.mark.asyncio
async def test_llamacpp_adapter_raises_provider_unavailable_when_server_is_down():
    adapter = LlamaCppAdapter(
        settings=LlamaCppSettings(
            LLAMACPP_BASE_URL="http://localhost:8080",
            LLM_PROVIDER_MODEL="gemma-4-12B-it-qat-UD-Q4_K_XL.gguf",
        ),
        client_factory=FailingAsyncClient,
    )

    with pytest.raises(
        LLMProviderUnavailableError, match="llama.cpp server is unavailable"
    ):
        await adapter.generate(
            system_prompt="system",
            user_message="hello",
            temperature=0.2,
            model="gemma-4-12B-it-qat-UD-Q4_K_XL.gguf",
            provider="llamacpp",
        )


def test_llamacpp_settings_load_from_env_or_dotenv():
    settings = LlamaCppSettings()

    assert settings.LLAMACPP_BASE_URL
    assert settings.LLM_PROVIDER_MODEL == "gemma-4-12B-it-qat-UD-Q4_K_XL.gguf"


def test_extract_chat_content_prefers_content_over_reasoning():
    result = _extract_chat_content(
        {
            "choices": [
                {
                    "message": {
                        "reasoning_content": '{"tool_names": ["wrong"]}',
                        "content": '{"tool_names": ["get_portfolio_metrics"], "needs_clarification": false}',
                    }
                }
            ]
        }
    )

    assert (
        result
        == '{"tool_names": ["get_portfolio_metrics"], "needs_clarification": false}'
    )


def test_extract_chat_content_uses_reasoning_json_only_when_content_is_empty():
    result = _extract_chat_content(
        {
            "choices": [
                {
                    "message": {
                        "reasoning_content": (
                            "Thinking text. "
                            '{"intent": "hotel_analytics", "agent_plan": ["aragorn", "elrond", "bilbo", "faramir"]}'
                        ),
                        "content": "",
                    }
                }
            ]
        }
    )

    assert result == (
        '{"intent": "hotel_analytics", "agent_plan": '
        '["aragorn", "elrond", "bilbo", "faramir"]}'
    )
