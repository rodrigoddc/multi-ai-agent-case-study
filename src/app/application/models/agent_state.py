"""Agent state schema — defines the graph's shared state shape.

Owned by application layer. Defines what data flows between agents.
"""

from typing import Annotated, Optional
from typing_extensions import TypedDict
import operator

from langchain_core.messages import BaseMessage, HumanMessage


class AgentState(TypedDict):
    """Main state for the multi-agent graph.

    All agents read from and write to this shared state. Fields with
    Annotated[..., operator.add] use a reducer to accumulate values
    across parallel branches.
    """

    # Input
    query: str
    """User's original question."""
    user_id: str
    """User identifier for memory and tracking."""
    thread_id: str
    """Conversation thread ID for checkpointing."""
    display_name: str
    """Display name collected from the browser."""
    messages: list[BaseMessage]
    """Full conversation history."""

    # Gandalf decision
    route_decision: str
    """Which agent path was selected."""
    active_agent: str
    """Currently active supervisor agent."""
    agent_plan: list[str]
    """Ordered queue of subagent names to execute. Gandalf sets it, router pops it."""
    agent_transcript: Annotated[list[dict], operator.add]
    """Ordered transcript of specialist agent outputs."""
    tool_results: dict
    """Structured results returned by subagent tools."""

    # Agent outputs
    insights: Annotated[list[str], operator.add]
    """From Elrond — performance analysis results."""
    user_context: dict
    """From Samwise — user preferences and conversation metadata."""
    weather_context: dict
    """From Radagast — weather facts and nature-condition context."""
    compliance_status: dict
    """From Aragorn — compliance validation results."""
    review_status: dict
    """From Faramir — final answer review results."""

    # Final response
    final_answer: str
    """Bilbo formatted response presented to the user."""
    reasoning_trace: str
    """Why this answer was generated — for observability."""

    # Human-in-the-loop
    requires_approval: bool
    """Does the response need user approval before delivery?"""
    approval_context: Optional[dict]
    """Context about what's being asked for approval."""
    requires_user_input: bool
    """Does the graph need clarification or other user input to continue?"""
    user_input_context: Optional[dict]
    """Context about the clarification or user input request."""
    user_feedback: Optional[str]
    """User's response to an interrupt (approve/reject/additional input)."""


def create_initial_state(
    query: str, user_id: str, thread_id: str, display_name: str | None = None
) -> AgentState:
    """Create a new initial state for a chat request."""
    return {
        "query": query,
        "user_id": user_id,
        "thread_id": thread_id,
        "display_name": display_name or "",
        "messages": [HumanMessage(content=query)],
        "route_decision": "",
        "active_agent": "gandalf",
        "agent_plan": [],
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
        "approval_context": None,
        "requires_user_input": False,
        "user_input_context": None,
        "user_feedback": None,
    }
