"""llama.cpp server LLM adapter."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx

from src.app.application.ports import LLMAdapter
from src.app.application.services.chat_service import LLMProviderUnavailableError
from src.app.infrastructure.config import LlamaCppSettings


class LlamaCppAdapter(LLMAdapter):
    """LLMAdapter implementation for a local llama.cpp OpenAI-compatible server."""

    def __init__(
        self,
        settings: LlamaCppSettings,
        client_factory: Callable[[], httpx.AsyncClient] | None = None,
    ) -> None:
        """Initialize the llama.cpp adapter.

        Args:
            settings: Local llama.cpp server settings.
            client_factory: Optional test seam for creating async HTTP clients.
        """
        self._settings = settings
        self._client_factory = client_factory or self._default_client_factory
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
        """Generate text via llama.cpp's OpenAI-compatible chat endpoint.

        Args:
            system_prompt: System-level instruction/context.
            user_message: User query or input.
            temperature: Sampling temperature.
            model: Required model identifier selected by the agent config.
            provider: Required provider name; only llamacpp is supported here.
            config: Optional runtime config, accepted for LLMAdapter compatibility.

        Returns:
            Generated assistant text.
        """
        if provider != "llamacpp":
            raise RuntimeError(
                f"Unsupported LLM provider for LlamaCppAdapter: {provider}"
            )

        response_payload = await self._post_chat_completion(
            model=model,
            system_prompt=system_prompt,
            user_message=user_message,
            temperature=temperature,
        )
        text = _extract_chat_content(response_payload)
        # Estimate token usage from char count (~4 chars/token)
        input_text = system_prompt + "\n" + user_message
        self.last_usage = {
            "input_tokens": max(1, len(input_text) // 4),
            "output_tokens": max(1, len(text) // 4),
            "total_tokens": max(1, (len(input_text) + len(text)) // 4),
        }
        return text

    def _default_client_factory(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self._settings.LLM_TIMEOUT_SECONDS)

    async def _post_chat_completion(
        self,
        model: str,
        system_prompt: str,
        user_message: str,
        temperature: float,
    ) -> dict[str, Any]:
        payload: dict[str, object] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": temperature,
            "stream": False,
            "max_tokens": 1024,
        }
        async with self._client_factory() as client:
            try:
                response = await client.post(
                    f"{self._settings.LLAMACPP_BASE_URL.rstrip('/')}/v1/chat/completions",
                    json=payload,
                )
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                raise LLMProviderUnavailableError(
                    "Local llama.cpp server is unavailable. Start the llama.cpp service and try again."
                ) from exc
            response.raise_for_status()
            parsed = response.json()
        if not isinstance(parsed, dict):
            raise RuntimeError("llama.cpp returned a non-object response")
        return parsed


def _extract_last_valid_json_object(text: str) -> str:
    """
    Extract the last valid JSON object from arbitrary text.

    This intentionally does NOT manually count braces.

    Instead, it:
    - Looks for possible JSON object starts: "{"
    - Uses Python's JSON parser to validate each candidate
    - Lets json.JSONDecoder handle braces inside strings correctly
    - Chooses the object that ends latest in the text, which is usually the
      final answer emitted by reasoning/thinking models
    """
    best: tuple[int, int] | None = None

    start = text.find("{")

    while start != -1:
        try:
            parsed, relative_end = json.JSONDecoder(strict=False).raw_decode(
                text[start:]
            )
        except json.JSONDecodeError:
            start = text.find("{", start + 1)
            continue

        if isinstance(parsed, dict):
            end = start + relative_end

            # Prefer the JSON object that finishes latest.
            # This avoids accidentally returning a nested object from inside
            # a larger valid JSON object.
            if best is None or end > best[1]:
                best = (start, end)

        start = text.find("{", start + 1)

    if best is None:
        return ""

    start, end = best
    return text[start:end]


def _extract_chat_content(response_payload: dict[str, Any]) -> str:
    """
    Safely extracts the final answer from a llama.cpp OpenAI-compatible chat response.

    Supports reasoning/thinking models where useful output may appear in:
    - message.content
    - message.reasoning_content
    - delta.content
    - delta.reasoning_content

    Returns:
    - The last valid JSON object found across reasoning_content + content
    - Otherwise falls back to content
    - Otherwise returns an empty string
    """
    try:
        choices = response_payload.get("choices") or []
        if not choices:
            return ""

        choice = choices[0] or {}

        message = choice.get("message") or choice.get("delta") or {}

        content = message.get("content") or ""
        reasoning = message.get("reasoning_content") or ""

        if not content and not reasoning:
            return ""

        if content:
            json_object = _extract_last_valid_json_object(content)
            if json_object:
                return json_object
            return content

        json_object = _extract_last_valid_json_object(reasoning)
        if json_object:
            return json_object

        return ""

    except Exception as exc:
        raise RuntimeError(
            f"Failed to parse llama.cpp payload: {exc}. Payload: {response_payload}"
        ) from exc
