"""OpenRouter LLM adapter — infrastructure implementation of LLMAdapter port.

Wraps ChatOpenRouter to implement the LLMAdapter protocol.
Uses Pydantic BaseSettings for credential handling.
Callback propagation: does NOT create its own Langfuse CallbackHandler.
LangGraph propagates the handler from config["callbacks"] downstream.

All settings are mandatory — the adapter fails fast if credentials are missing.
"""

from __future__ import annotations

import logging
from typing import Any, cast

from langchain_core.runnables import RunnableConfig
from langchain_openrouter import ChatOpenRouter
from openrouter.errors.responsevalidationerror import ResponseValidationError
from openrouter.errors.unauthorizedresponse_error import UnauthorizedResponseError
from pydantic import SecretStr

from src.app.application.ports import LLMAdapter
from src.app.application.services.chat_service import LLMAuthenticationError

logger = logging.getLogger(__name__)


class OpenRouterAdapter(LLMAdapter):
    """OpenRouter implementation of the LLMAdapter port.

    Thread-safe: creates ChatOpenRouter instance per-call.
    Does NOT create its own Langfuse CallbackHandler — callbacks are
    propagated by LangGraph through the graph-level config.

    Requires a valid LLM_PROVIDER_API_KEY environment variable.
    """

    def __init__(
        self,
        api_key: SecretStr,
        model: str = "openrouter/free",
        default_temperature: float = 0.8,
        timeout_seconds: float = 300.0,
    ) -> None:
        """Initialize the OpenRouter adapter.

        Args:
            api_key: The OpenRouter API key.
            model: Model identifier.
            default_temperature: Default sampling temperature.
            timeout_seconds: Request timeout in seconds.
        """
        if not api_key:
            raise RuntimeError("OpenRouter API key is required")

        self._api_key = api_key
        self._model = model
        self._default_temperature = default_temperature
        self._timeout_seconds = timeout_seconds
        self.last_usage: dict[str, int | float] | None = None
        logger.info("OpenRouterAdapter using model %s", self._model)

    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float,
        model: str,
        provider: str,
        config: dict[str, Any] | None = None,
    ) -> str:
        """Generate a response from OpenRouter.

        Args:
            system_prompt: System-level instruction/context.
            user_message: User's query or input.
            temperature: Sampling temperature (overrides default).
            config: Optional LangChain config dict (callbacks, tags, etc.).
            model: Required model identifier selected by the agent config.
            provider: Required provider name; only openrouter is supported here.

        Returns:
            Generated text response.

        Raises:
            RuntimeError: If API call fails due to missing/invalid credentials.
            TimeoutError: If the request times out or gateway times out (504).
        """
        if provider != "openrouter":
            raise RuntimeError(
                f"Unsupported LLM provider for OpenRouterAdapter: {provider}"
            )

        llm = ChatOpenRouter(
            api_key=self._api_key,
            model=model,
            temperature=temperature,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        try:
            response = await llm.ainvoke(
                messages,
                config=_without_callbacks(config),
            )
            # Capture token usage and cost from the AIMessage metadata
            meta = getattr(response, "response_metadata", {}) or {}
            usage = getattr(response, "usage_metadata", None) or {}
            self.last_usage = {}
            if usage.get("input_tokens") is not None:
                self.last_usage["input_tokens"] = usage["input_tokens"]
            if usage.get("output_tokens") is not None:
                self.last_usage["output_tokens"] = usage["output_tokens"]
            if usage.get("total_tokens") is not None:
                self.last_usage["total_tokens"] = usage["total_tokens"]
            # OpenRouter returns cost in response_metadata
            cost = meta.get("cost") if isinstance(meta, dict) else None
            if cost is not None:
                self.last_usage["cost"] = cost
        except UnauthorizedResponseError as e:
            # Authentication error - missing or invalid API key
            error_msg = str(e)
            log_msg = error_msg[:500] + ("..." if len(error_msg) > 500 else "")
            logger.error("OpenRouter authentication failed: %s", log_msg)
            raise LLMAuthenticationError(
                f"OpenRouter authentication failed: {error_msg}"
            ) from e
        except ResponseValidationError as e:
            # Check if it's a gateway timeout (504) or other HTTP error
            error_msg = str(e)
            # Truncate for logging — full error preserved in exception chain
            log_msg = error_msg[:500] + ("..." if len(error_msg) > 500 else "")
            if (
                "504" in error_msg
                or "gateway timeout" in error_msg.lower()
                or "timeout" in error_msg.lower()
            ):
                logger.warning("OpenRouter gateway timeout: %s", log_msg)
                raise TimeoutError(f"OpenRouter gateway timeout: {error_msg}") from e
            logger.error("OpenRouter response validation error: %s", log_msg)
            raise RuntimeError(
                f"OpenRouter response validation failed: {error_msg}"
            ) from e
        except Exception as e:
            # Catch any other timeout-related errors
            error_msg = str(e)
            log_msg = error_msg[:500] + ("..." if len(error_msg) > 500 else "")
            if "timeout" in error_msg.lower() or "504" in error_msg:
                logger.warning("OpenRouter request timeout: %s", log_msg)
                raise TimeoutError(f"OpenRouter request timed out: {error_msg}") from e
            raise

        return response.content if hasattr(response, "content") else str(response)


def _without_callbacks(config: dict[str, Any] | None) -> RunnableConfig:
    """Return LangChain config safe for an inner provider call.

    The outer PortBackedChatModel is the application LLM span. Forwarding
    callbacks into ChatOpenRouter creates a second nested Langfuse LLM span
    and double-counts cost for the same provider request.
    """
    inner_config = dict(config or {})
    inner_config["callbacks"] = []
    return cast(RunnableConfig, inner_config)
