"""Trajectory projection tests for evals."""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from evals.trajectory import (
    expected_tool_sequence_from_dataset,
    extract_agent_turns,
    extract_tool_calls_from_messages,
    extract_tool_calls_from_state,
    project_trajectory,
)


def make_tool_call(name: str, args: dict, call_id: str) -> dict:
    """Create a tool call dict in LangChain format."""
    return {"name": name, "args": args, "id": call_id, "type": "tool_call"}


class TestExtractToolCalls:
    """Test tool call extraction from messages."""

    def test_extract_from_ai_message_with_tool_calls(self) -> None:
        """Extract tool calls from AIMessage with tool_calls attribute."""
        msg = AIMessage(
            content="",
            tool_calls=[
                make_tool_call(
                    "query_hotel_performance", {"metric": "sentiment"}, "call-1"
                ),
                make_tool_call("analyze_competitors", {}, "call-2"),
            ],
        )
        calls = extract_tool_calls_from_messages([msg])
        assert len(calls) == 2
        assert calls[0]["name"] == "query_hotel_performance"
        assert calls[0]["args"] == {"metric": "sentiment"}
        assert calls[0]["id"] == "call-1"
        assert calls[1]["name"] == "analyze_competitors"

    def test_extract_from_multiple_messages(self) -> None:
        """Extract from multiple AI messages in sequence."""
        msgs = [
            AIMessage(content="", tool_calls=[make_tool_call("tool_a", {}, "call-1")]),
            AIMessage(
                content="", tool_calls=[make_tool_call("tool_b", {"x": 1}, "call-2")]
            ),
        ]
        calls = extract_tool_calls_from_messages(msgs)
        assert len(calls) == 2
        assert calls[0]["name"] == "tool_a"
        assert calls[1]["name"] == "tool_b"

    def test_empty_on_messages_without_tool_calls(self) -> None:
        """Return empty list for messages without tool_calls."""
        msgs = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there"),
        ]
        calls = extract_tool_calls_from_messages(msgs)
        assert calls == []

    def test_skips_non_ai_messages(self) -> None:
        """Skip ToolMessage and HumanMessage even if they have tool_calls attr."""
        # ToolMessage shouldn't have tool_calls but be safe
        msgs = [
            HumanMessage(content="Hi"),
            ToolMessage(content="result", tool_call_id="call-1"),
        ]
        calls = extract_tool_calls_from_messages(msgs)
        assert calls == []


class TestExtractToolCallsFromState:
    """Test extract_tool_calls_from_state with AgentState-like input."""

    def test_extracts_from_state_messages(self) -> None:
        """Extract tool calls from state dict with messages."""
        state = {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[make_tool_call("tool_x", {"a": 1}, "call-1")],
                ),
            ],
            "query": "test",
            "user_id": "u1",
            "thread_id": "t1",
            "route_decision": "",
            "active_agent": "",
            "agent_transcript": [],
            "tool_results": {},
            "insights": [],
            "user_context": {},
            "weather_context": {},
            "compliance_status": {},
            "review_status": {},
            "final_answer": "",
            "reasoning_trace": "",
            "requires_approval": False,
        }
        calls = extract_tool_calls_from_state(state)  # type: ignore[arg-type]
        assert len(calls) == 1
        assert calls[0]["name"] == "tool_x"


class TestProjectTrajectory:
    """Test project_trajectory flattening state to flat tool sequence."""

    def test_projects_full_trajectory_with_results(self) -> None:
        """Project trajectory includes tool results from ToolMessages."""
        tool_result_msg = ToolMessage(
            content="Hotel data: 5 hotels found", tool_call_id="call-1"
        )
        ai_msg = AIMessage(
            content="",
            tool_calls=[
                make_tool_call(
                    "query_hotel_performance", {"metric": "sentiment"}, "call-1"
                )
            ],
        )
        state = {
            "messages": [ai_msg, tool_result_msg],
            "query": "test",
            "user_id": "u1",
            "thread_id": "t1",
            "route_decision": "",
            "active_agent": "aragorn",
            "agent_transcript": [],
            "tool_results": {},
            "insights": [],
            "user_context": {},
            "weather_context": {},
            "compliance_status": {},
            "review_status": {},
            "final_answer": "",
            "reasoning_trace": "",
            "requires_approval": False,
        }
        trajectory = project_trajectory(state)  # type: ignore[arg-type]
        assert len(trajectory) == 1
        step = trajectory[0]
        assert step["tool"] == "query_hotel_performance"
        assert step["args"] == {"metric": "sentiment"}
        assert step["result"] == "Hotel data: 5 hotels found"
        assert step["agent"] == "aragorn"
        assert step["tool_call_id"] == "call-1"

    def test_multiple_tools_different_agents(self) -> None:
        """Multiple tool calls from different agents tracked separately."""
        msgs = [
            AIMessage(
                content="",
                name="aragorn",
                tool_calls=[
                    make_tool_call(
                        "query_hotel_performance", {"metric": "sentiment"}, "call-1"
                    ),
                ],
            ),
            ToolMessage(content="result 1", tool_call_id="call-1"),
            AIMessage(
                content="",
                name="elrond",
                tool_calls=[
                    make_tool_call("analyze_competitors", {}, "call-2"),
                    make_tool_call("benchmark_adr_revpar", {"limit": 5}, "call-3"),
                ],
            ),
            ToolMessage(content="result 2", tool_call_id="call-2"),
            ToolMessage(content="result 3", tool_call_id="call-3"),
        ]
        state = {
            "messages": msgs,
            "query": "test",
            "user_id": "u1",
            "thread_id": "t1",
            "route_decision": "",
            "active_agent": "",
            "agent_transcript": [],
            "tool_results": {},
            "insights": [],
            "user_context": {},
            "weather_context": {},
            "compliance_status": {},
            "review_status": {},
            "final_answer": "",
            "reasoning_trace": "",
            "requires_approval": False,
        }
        trajectory = project_trajectory(state)  # type: ignore[arg-type]
        assert len(trajectory) == 3
        assert trajectory[0]["agent"] == "aragorn"
        assert trajectory[1]["agent"] == "elrond"
        assert trajectory[2]["agent"] == "elrond"
        assert trajectory[1]["tool"] == "analyze_competitors"
        assert trajectory[2]["tool"] == "benchmark_adr_revpar"

    def test_preserves_order(self) -> None:
        """Trajectory preserves invocation order."""
        msgs = [
            AIMessage(
                content="", name="a", tool_calls=[make_tool_call("tool1", {}, "call-1")]
            ),
            ToolMessage(content="r1", tool_call_id="call-1"),
            AIMessage(
                content="", name="a", tool_calls=[make_tool_call("tool2", {}, "call-2")]
            ),
            ToolMessage(content="r2", tool_call_id="call-2"),
        ]
        state = {
            "messages": msgs,
            "query": "test",
            "user_id": "u1",
            "thread_id": "t1",
            "route_decision": "",
            "active_agent": "",
            "agent_transcript": [],
            "tool_results": {},
            "insights": [],
            "user_context": {},
            "weather_context": {},
            "compliance_status": {},
            "review_status": {},
            "final_answer": "",
            "reasoning_trace": "",
            "requires_approval": False,
        }
        trajectory = project_trajectory(state)  # type: ignore[arg-type]
        assert [s["tool"] for s in trajectory] == ["tool1", "tool2"]

    def test_empty_trajectory_when_no_tool_calls(self) -> None:
        """Empty list when state has no tool calls."""
        state = {
            "messages": [HumanMessage(content="Hi"), AIMessage(content="Hello")],
            "query": "test",
            "user_id": "u1",
            "thread_id": "t1",
            "route_decision": "",
            "active_agent": "",
            "agent_transcript": [],
            "tool_results": {},
            "insights": [],
            "user_context": {},
            "weather_context": {},
            "compliance_status": {},
            "review_status": {},
            "final_answer": "Hello",
            "reasoning_trace": "",
            "requires_approval": False,
        }
        trajectory = project_trajectory(state)  # type: ignore[arg-type]
        assert trajectory == []


class TestExtractAgentTurns:
    """Test extract_agent_turns for agent-level view."""

    def test_extracts_turns_with_tool_calls_and_output(self) -> None:
        """Extract agent turns with their tool calls and final output."""
        msgs = [
            AIMessage(
                content="",
                name="aragorn",
                tool_calls=[
                    make_tool_call(
                        "query_hotel_performance", {"metric": "sentiment"}, "call-1"
                    ),
                ],
            ),
            ToolMessage(content="result", tool_call_id="call-1"),
            AIMessage(content="Hotels are doing well", name="aragorn"),
            AIMessage(
                content="",
                name="bilbo",
                tool_calls=[
                    make_tool_call("summarize_insights", {}, "call-2"),
                ],
            ),
            ToolMessage(content="summary", tool_call_id="call-2"),
            AIMessage(content="Final summary", name="bilbo"),
        ]
        state = {
            "messages": msgs,
            "query": "test",
            "user_id": "u1",
            "thread_id": "t1",
            "route_decision": "",
            "active_agent": "",
            "agent_transcript": [],
            "tool_results": {},
            "insights": [],
            "user_context": {},
            "weather_context": {},
            "compliance_status": {},
            "review_status": {},
            "final_answer": "",
            "reasoning_trace": "",
            "requires_approval": False,
        }
        turns = extract_agent_turns(state)  # type: ignore[arg-type]
        assert len(turns) == 2
        assert turns[0]["agent"] == "aragorn"
        assert len(turns[0]["tool_calls"]) == 1
        assert turns[0]["tool_calls"][0]["name"] == "query_hotel_performance"
        assert turns[0]["output"] == "Hotels are doing well"
        assert turns[1]["agent"] == "bilbo"
        assert turns[1]["output"] == "Final summary"


class TestExpectedToolSequence:
    """Test expected_tool_sequence_from_dataset mapping."""

    def test_maps_required_agents_to_tools(self) -> None:
        """Map required agents to their primary tools."""
        expected_output = {
            "required_agents": ["aragorn", "elrond", "bilbo", "faramir"],
            "optional_agents": ["samwise"],
            "forbidden_agents": ["radagast"],
        }
        sequence = expected_tool_sequence_from_dataset(expected_output)
        # Should have tools for all required agents
        assert "query_hotel_performance" in sequence  # aragorn
        assert "query_hotel_list" in sequence  # aragorn
        assert "analyze_competitors" in sequence  # elrond
        assert "benchmark_adr_revpar" in sequence  # elrond
        assert "summarize_insights" in sequence  # bilbo
        assert "list_capabilities" in sequence  # bilbo
        assert "safe_guardrail_response" in sequence  # faramir

    def test_empty_when_no_required_agents(self) -> None:
        """Empty list when no required agents."""
        expected_output = {
            "required_agents": [],
            "optional_agents": [],
            "forbidden_agents": [],
        }
        sequence = expected_tool_sequence_from_dataset(expected_output)
        assert sequence == []

    def test_unknown_agent_generates_fallback(self) -> None:
        """Unknown agent generates fallback tool name."""
        expected_output = {
            "required_agents": ["unknown_agent"],
            "optional_agents": [],
            "forbidden_agents": [],
        }
        sequence = expected_tool_sequence_from_dataset(expected_output)
        assert "unknown_agent_tool" in sequence


# Pytest markers
pytestmark = [
    pytest.mark.evals,
    pytest.mark.evals_trajectory,
]
