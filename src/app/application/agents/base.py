"""Base helpers for LOTR subagents."""

from __future__ import annotations

import json
import logging
from json import JSONDecoder
from typing import Any, ClassVar, Type

from langchain.agents import create_agent
from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.store.base import BaseStore
from pydantic import BaseModel, ConfigDict, Field

from src.app.application.agents.config import AgentConfig
from src.app.application.ports import LLMAdapter

logger = logging.getLogger(__name__)


class PortBackedChatModel(BaseChatModel):
    """Minimal chat model backed by the project LLMAdapter port."""

    model_config: ClassVar[ConfigDict] = ConfigDict(arbitrary_types_allowed=True)

    llm: Any
    system_prompt: str
    temperature: float = 0.8
    provider: str = Field(min_length=1)
    model_name: str = Field(default="", min_length=1)

    @property
    def _llm_type(self) -> str:
        return self.model_name

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        raise RuntimeError("PortBackedChatModel supports async invocation only")

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        content = "\n".join(str(message.content) for message in messages)
        generate_kwargs: dict[str, Any] = {
            "system_prompt": self.system_prompt,
            "user_message": content,
            "temperature": self.temperature,
            "model": self.model_name,
            "provider": self.provider,
        }
        if "config" in kwargs:
            generate_kwargs["config"] = kwargs["config"]
        text = await self.llm.generate(**generate_kwargs)

        # Capture token usage and cost from adapter's last_usage
        usage_meta: dict[str, int] = {}
        response_meta: dict[str, Any] = {"model": self.model_name}
        last_usage = getattr(self.llm, "last_usage", None)
        if isinstance(last_usage, dict):
            if last_usage.get("input_tokens"):
                usage_meta["input_tokens"] = int(last_usage["input_tokens"])
            if last_usage.get("output_tokens"):
                usage_meta["output_tokens"] = int(last_usage["output_tokens"])
            if last_usage.get("total_tokens"):
                usage_meta["total_tokens"] = int(last_usage["total_tokens"])
            if last_usage.get("cost"):
                response_meta["cost"] = float(last_usage["cost"])

        return ChatResult(
            generations=[
                ChatGeneration(
                    message=AIMessage(content=text, usage_metadata=usage_meta or None),
                    generation_info=response_meta,
                )
            ]
        )

    def bind_tools(
        self,
        tools: Any,
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> PortBackedChatModel:
        """Return this port-backed model for agent tool binding."""
        return self


class LLMBackedSubagent:
    """Small application-level wrapper around a named subagent.

    The `create_agent` instance is created to keep the architecture aligned
    with the documented subagents pattern. Actual provider calls still go through the
    injected `LLMAdapter` port so application code does not construct infrastructure.
    """

    def __init__(
        self,
        *,
        name: str,
        llm: LLMAdapter,
        tools: list[Any] | None = None,
        config: AgentConfig,
        store: BaseStore | None = None,
        context_schema: Type[BaseModel] | None = None,
    ) -> None:
        if config is None:
            raise ValueError(f"Agent config is required for {name}")
        self.config = config
        self.name = name
        self.system_prompt = config.prompt
        self.llm = llm
        self.temperature = config.llm.temperature
        self.model_name = config.llm.model
        self.provider = config.llm.provider
        self.store = store
        self.context_schema = context_schema
        self.agent = create_agent(
            model=PortBackedChatModel(
                llm=llm,
                system_prompt=self.system_prompt,
                temperature=self.temperature,
                model_name=self.model_name,
                provider=self.provider,
                name=self.model_name,
            ),
            tools=tools or [],
            system_prompt=self.system_prompt,
            name=name,
            store=store,
            context_schema=context_schema,
        )

    async def generate(self, user_message: str) -> str:
        """Generate subagent output through its agent."""
        logger.info(
            "Agent %s invoking LLM provider=%s model=%s temperature=%s",
            self.name,
            self.provider,
            self.model_name,
            self.temperature,
        )
        result = await self.agent.ainvoke(
            {"messages": [{"role": "user", "content": user_message}]},
            {"run_name": self.model_name},
        )
        messages = result.get("messages", []) if isinstance(result, dict) else []
        if not messages:
            return ""
        last_message = messages[-1]
        content = getattr(last_message, "content", last_message)
        return str(content)


def parse_json_object(raw: str, *, fallback: dict[str, Any]) -> dict[str, Any]:
    """Parse a JSON object from an LLM response.

    Args:
        raw: Raw model output.
        fallback: Value returned when parsing fails or does not produce an object.

    Returns:
        Parsed JSON object or fallback.
    """
    clean_raw = _strip_json_fence(raw.strip())
    for candidate in _json_candidates(clean_raw):
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate, strict=False)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return fallback


def _strip_json_fence(raw: str) -> str:
    if not raw.startswith("```"):
        return raw
    lines = [line for line in raw.splitlines() if not line.strip().startswith("```")]
    return "\n".join(lines).strip()


def _json_candidates(raw: str) -> list[str]:
    candidates = [raw, _strip_thinking_blocks(raw), *_extract_json_objects(raw)]
    unique_candidates: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        clean_candidate = _strip_json_fence(candidate.strip())
        if not clean_candidate or clean_candidate in seen:
            continue
        seen.add(clean_candidate)
        unique_candidates.append(clean_candidate)
    return unique_candidates


def _strip_thinking_blocks(raw: str) -> str:
    text = raw
    while "<think>" in text and "</think>" in text:
        start = text.find("<think>")
        end = text.find("</think>", start)
        if end == -1:
            break
        text = text[:start] + text[end + len("</think>") :]
    return text.strip()


def _extract_json_objects(raw: str) -> list[str]:
    decoder = JSONDecoder(strict=False)
    objects: list[str] = []
    for index, char in enumerate(raw):
        if char != "{":
            continue
        try:
            parsed, end = decoder.raw_decode(raw[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            objects.append(raw[index : index + end])
    if objects:
        return list(reversed(objects))
    fallback = _extract_json_object(raw)
    return [fallback] if fallback else []


def _extract_json_object(raw: str) -> str:
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end <= start:
        return ""
    return raw[start : end + 1]
