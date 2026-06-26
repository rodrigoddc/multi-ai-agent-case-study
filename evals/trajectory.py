"""Trajectory projection from LangGraph state to agentevals format."""

from __future__ import annotations

from typing import Any

from src.app.application.models.agent_state import AgentState


def extract_tool_calls_from_state(state: AgentState) -> list[dict[str, Any]]:
    """Extract tool calls from AgentState in agentevals-compatible format.

    Returns list of dicts with: name, args, id, type='tool_call'.
    """
    return extract_tool_calls_from_messages(state.get("messages", []))


def extract_tool_calls_from_messages(messages: list[Any]) -> list[dict[str, Any]]:
    """Extract tool calls from a list of messages in agentevals-compatible format.

    Returns list of dicts with: name, args, id, type='tool_call'.
    """
    calls: list[dict[str, Any]] = []
    for msg in messages:
        tool_calls = getattr(msg, "tool_calls", None)
        if not tool_calls:
            continue
        for tc in tool_calls:
            calls.append(
                {
                    "name": tc.get("name"),
                    "args": tc.get("args", {}),
                    "id": tc.get("id"),
                    "type": "tool_call",
                }
            )
    return calls


def extract_agent_turns(state: AgentState) -> list[dict[str, Any]]:
    """Extract the sequence of agent turns from AgentState.

    Returns list of dicts with: agent_name, tool_calls (list), output (str).
    """
    turns: list[dict[str, Any]] = []
    messages = state.get("messages", [])
    current_agent = None
    current_calls: list[dict[str, Any]] = []

    for msg in messages:
        # Check if this is an AI message with tool calls (agent turn)
        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls:
            current_agent = getattr(msg, "name", None) or getattr(
                msg, "additional_kwargs", {}
            ).get("name", None)
            current_calls = extract_tool_calls_from_messages([msg])
            continue

        # Check if this is a ToolMessage (tool result)
        if (
            getattr(msg, "type", None) == "tool"
            or msg.__class__.__name__ == "ToolMessage"
        ):
            # Tool result belongs to the previous agent turn
            continue

        # Check if this is an AI message without tool calls (final answer from agent)
        if getattr(msg, "type", None) == "ai" and not tool_calls:
            content = getattr(msg, "content", "")
            if content and current_agent:
                turns.append(
                    {
                        "agent": current_agent,
                        "tool_calls": current_calls,
                        "output": content if isinstance(content, str) else str(content),
                    }
                )
                current_agent = None
                current_calls = []

    return turns


def project_trajectory(state: AgentState) -> list[dict[str, Any]]:
    """Project full AgentState into a flat trajectory for agentevals matching.

    Returns list of steps, each step is a dict with:
    - "tool": tool name
    - "args": tool arguments
    - "result": tool result (if available in subsequent messages)
    - "agent": agent name that invoked the tool

    This flattens the multi-turn agent workflow into a single tool invocation sequence
    matching the reference trajectory format.
    """
    trajectory: list[dict[str, Any]] = []
    messages = state.get("messages", [])

    # Get fallback agent from state
    fallback_agent = state.get("active_agent")

    # Build a map of tool_call_id -> tool result
    tool_results: dict[str, Any] = {}
    for msg in messages:
        if (
            getattr(msg, "type", None) == "tool"
            or msg.__class__.__name__ == "ToolMessage"
        ):
            tool_call_id = getattr(msg, "tool_call_id", None)
            if tool_call_id:
                content = getattr(msg, "content", "")
                tool_results[tool_call_id] = (
                    content if isinstance(content, str) else str(content)
                )

    for msg in messages:
        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls:
            # Prefer message name, then additional_kwargs.name, then state active_agent
            current_agent = (
                getattr(msg, "name", None)
                or getattr(msg, "additional_kwargs", {}).get("name", None)
                or fallback_agent
            )
            for tc in tool_calls:
                tool_id = tc.get("id")
                trajectory.append(
                    {
                        "tool": tc.get("name"),
                        "args": tc.get("args", {}),
                        "result": tool_results.get(tool_id),
                        "agent": current_agent,
                        "tool_call_id": tool_id,
                    }
                )

    return trajectory


def expected_tool_sequence_from_dataset(expected_output: dict[str, Any]) -> list[str]:
    """Convert dataset expected_output.required_agents to expected tool sequence pattern.

    This is a heuristic: map agent names to their primary tools.
    """
    agent_to_tools = {
        "gandalf": ["ask_clarification"],
        "aragorn": ["query_hotel_performance", "query_hotel_list"],
        "elrond": ["analyze_competitors", "benchmark_adr_revpar"],
        "bilbo": ["summarize_insights", "list_capabilities"],
        "samwise": ["get_reviews_summary", "check_booking_health"],
        "radagast": ["get_weather_forecast", "get_weather_impact"],
        "faramir": ["safe_guardrail_response"],
    }

    required = expected_output.get("required_agents", [])
    sequence: list[str] = []
    for agent in required:
        sequence.extend(agent_to_tools.get(agent, [f"{agent}_tool"]))
    return sequence


__all__ = [
    "extract_tool_calls_from_state",
    "extract_tool_calls_from_messages",
    "extract_agent_turns",
    "project_trajectory",
    "expected_tool_sequence_from_dataset",
]
