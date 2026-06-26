"""Samwise — memory and user context AI subagent using LangGraph store tools."""

from __future__ import annotations

import uuid
from typing import Any

from langchain.tools import tool
from langgraph.store.base import BaseStore
from pydantic import BaseModel

from src.app.application.agents.base import LLMBackedSubagent
from src.app.application.agents.config import AgentConfig
from src.app.application.progress import emit_tool_call
from src.app.application.ports import LLMAdapter


class SamwiseContext(BaseModel):
    """Context schema for Samwise long-term memory tools."""

    user_id: str


@tool
async def remember_user_preference(preference: str, runtime: Any) -> str:
    """Save a non-sensitive user preference to long-term memory."""
    user_id = getattr(runtime.context, "user_id", "anonymous")
    store: BaseStore = runtime.store
    namespace = (user_id, "preferences")
    key = str(uuid.uuid4())
    await store.aput(
        namespace,
        key,
        {"preference": str(preference), "source": "conversation"},
    )
    return f"Saved preference for user {user_id}: {preference}"


@tool
async def load_user_preferences(runtime: Any) -> str:
    """Load stored user preferences from long-term memory."""
    user_id = getattr(runtime.context, "user_id", "anonymous")
    store: BaseStore = runtime.store
    namespace = (user_id, "preferences")
    try:
        items = await store.asearch(namespace, limit=10)
    except TypeError:
        items = []
    preferences = [item.value.get("preference", "") for item in items]
    return f"Loaded {len(preferences)} preferences for user {user_id}: {preferences}"


class SamwiseAgent(LLMBackedSubagent):
    """AI subagent responsible for user memory and preferences."""

    def __init__(
        self,
        llm: LLMAdapter,
        config: AgentConfig,
        store: BaseStore | None = None,
    ) -> None:
        tools = [remember_user_preference, load_user_preferences] if store else []
        super().__init__(
            name="samwise",
            llm=llm,
            config=config,
            tools=tools,
            store=store,
            context_schema=SamwiseContext,
        )
        self.store = store

    async def load_context(self, state: dict[str, Any]) -> dict:
        """Load stored user preferences from the graph state."""
        user_id = state.get("user_id", "anonymous")
        messages = state.get("messages", [])

        context: dict[str, Any] = {
            "user_id": user_id,
            "preferences": [],
            "message_count": len(messages),
        }
        if self.store is None:
            return context

        emit_tool_call("load_user_preferences")
        namespace = (user_id, "preferences")
        try:
            items = await self.store.asearch(namespace, limit=10)
        except TypeError:
            items = []
        context["preferences"] = [item.value for item in items] if items else []
        return context
