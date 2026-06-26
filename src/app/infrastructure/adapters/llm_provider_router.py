"""LLM adapter router for per-agent provider selection."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from src.app.application.ports import LLMAdapter

logger = logging.getLogger(__name__)


class LLMProviderRouter(LLMAdapter):
    """Route LLM calls to the adapter selected by agent configuration."""

    def __init__(self, adapters: Mapping[str, LLMAdapter]) -> None:
        """Initialize the router.

        Args:
            adapters: Concrete LLM adapters keyed by provider name.
        """
        self._adapters = dict(adapters)
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
        """Generate text through the adapter selected by provider."""
        adapter = self._adapters.get(provider)
        if adapter is None:
            raise RuntimeError(f"Unsupported LLM provider: {provider}")

        logger.info(
            "Dispatching LLM request provider=%s model=%s temperature=%s adapter=%s",
            provider,
            model,
            temperature,
            adapter.__class__.__name__,
        )
        text = await adapter.generate(
            system_prompt=system_prompt,
            user_message=user_message,
            temperature=temperature,
            model=model,
            provider=provider,
            config=config,
        )
        self.last_usage = getattr(adapter, "last_usage", None)
        logger.info(
            "Completed LLM request provider=%s model=%s usage=%s",
            provider,
            model,
            self.last_usage,
        )
        return text
