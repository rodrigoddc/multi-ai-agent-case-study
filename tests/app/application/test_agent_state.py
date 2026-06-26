"""Tests for AgentState schema."""

from src.app.application.models.agent_state import AgentState


def test_agent_state_creation():
    """Test state creation with valid data."""
    state = AgentState(
        query="test query",
        user_id="user-1",
        thread_id="thread-1",
        messages=[],
        route_decision="",
        active_agent="gandalf",
        agent_transcript=[],
        tool_results={},
        insights=[],
        user_context={},
        compliance_status={},
        review_status={},
        final_answer="",
        reasoning_trace="",
        requires_approval=False,
        approval_context=None,
        user_feedback=None,
    )
    assert state["query"] == "test query"
    assert state["user_id"] == "user-1"


def test_agent_state_with_empty_lists():
    """Test state with empty lists."""
    state = AgentState(
        query="",
        user_id="",
        thread_id="",
        messages=[],
        route_decision="",
        active_agent="gandalf",
        agent_transcript=[],
        tool_results={},
        insights=[],
        user_context={},
        compliance_status={},
        review_status={},
        final_answer="",
        reasoning_trace="",
        requires_approval=False,
        approval_context=None,
        user_feedback=None,
    )
    assert state["insights"] == []
    assert state["messages"] == []


def test_agent_state_optional_fields():
    """Test state with optional fields as None."""
    state = AgentState(
        query="",
        user_id="",
        thread_id="",
        messages=[],
        route_decision="",
        active_agent="gandalf",
        agent_transcript=[],
        tool_results={},
        insights=[],
        user_context={},
        compliance_status={},
        review_status={},
        final_answer="",
        reasoning_trace="",
        requires_approval=False,
        approval_context=None,
        user_feedback=None,
    )
    assert state["approval_context"] is None
    assert state["user_feedback"] is None
