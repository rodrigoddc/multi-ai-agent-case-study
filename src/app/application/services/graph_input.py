"""Helpers for preparing LangGraph chat inputs."""

from __future__ import annotations

from typing import Any, cast

from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from src.app.application.models.agent_state import AgentState, create_initial_state

GraphInput = AgentState | Command
RunnableConfig = dict[str, Any]


async def build_graph_input(
    *,
    graph: CompiledStateGraph,
    config: RunnableConfig,
    message: str,
    user_id: str,
    thread_id: str,
    display_name: str | None = None,
) -> GraphInput:
    """Build graph input for either a new request or interrupted thread resume."""
    if await has_pending_interrupt(graph=graph, config=config):
        return Command(resume=message)

    return create_initial_state(
        query=message,
        user_id=user_id,
        thread_id=thread_id,
        display_name=display_name,
    )


async def has_pending_interrupt(
    *, graph: CompiledStateGraph, config: RunnableConfig
) -> bool:
    """Return whether the graph checkpoint is paused at a LangGraph interrupt."""
    if getattr(graph, "checkpointer", None) is None:
        return False

    snapshot = await cast(Any, graph).aget_state(config)
    return bool(snapshot.next)


def build_graph_config(
    *,
    user_id: str,
    thread_id: str,
    session_id: str,
    tracing_config: dict | None,
) -> RunnableConfig:
    """Build LangGraph runnable config for a chat request."""
    config: RunnableConfig = {
        "configurable": {
            "thread_id": thread_id,
            "user_id": user_id,
            "session_id": session_id,
        },
    }
    if tracing_config:
        config.update(tracing_config)
    return config
