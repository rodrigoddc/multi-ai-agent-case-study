"""Multi-agent graph assembly — application orchestration layer.

Single-node graph: Gandalf (the supervisor) is a LangChain create_agent
with call_agent and list_agents tools that dispatch to subagents via the
single dispatch tool pattern (per LangChain docs). The graph handles
interrupt/resume for user clarification requests.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.store.base import BaseStore
from langgraph.types import interrupt

from src.app.application.agents.protocols import AIAgent
from src.app.application.models.agent_state import AgentState

logger = logging.getLogger(__name__)


def _apply_interrupt_feedback(
    *, state: dict[str, Any], update: dict[str, Any], feedback: Any
) -> dict[str, Any]:
    feedback_text = _feedback_text(
        feedback=feedback, approval_context=update.get("approval_context")
    )
    messages = list(state.get("messages", []))
    if feedback_text:
        messages.append(HumanMessage(content=feedback_text))
    return {
        **state,
        **update,
        "query": _query_with_clarification(
            original_query=str(state.get("query", "")),
            feedback=feedback_text,
        ),
        "messages": messages,
        "requires_approval": False,
        "approval_context": None,
        "requires_user_input": False,
        "user_input_context": None,
        "user_feedback": feedback_text,
    }


def _feedback_text(*, feedback: Any, approval_context: Any) -> str:
    text = str(feedback).strip()
    if not text:
        return text
    options = _approval_options(approval_context)
    if len(text.split()) < 2:
        return text
    lowered_text = text.casefold()
    for option in options:
        lowered_option = option.casefold()
        if lowered_option == lowered_text or lowered_option.endswith(lowered_text):
            return option
    return text


def _approval_options(approval_context: Any) -> list[str]:
    if not isinstance(approval_context, dict):
        return []
    raw_options = approval_context.get("options", [])
    if not isinstance(raw_options, list):
        return []
    return [option for option in raw_options if isinstance(option, str) and option]


def _query_with_clarification(*, original_query: str, feedback: str) -> str:
    clean_query = original_query.strip()
    if not feedback:
        return clean_query
    if not clean_query:
        return feedback
    if clean_query == feedback:
        return clean_query
    return f"{clean_query}\n\nUser clarification: {feedback}"


async def build_graph(
    checkpointer: Optional[BaseCheckpointSaver] = None,
    store: Optional[BaseStore] = None,
    supervisor: AIAgent | None = None,
    supervisor_node_name: str = "gandalf",
) -> CompiledStateGraph:
    """Build and compile the single-node supervisor graph.

    Gandalf is a create_agent with call_agent/list_agents tools that dispatch
    to subagents via the single dispatch tool pattern. The node wrapper handles
    interrupts for user clarification.

    Args:
        checkpointer: Optional checkpoint saver.
        store: Optional store for long-term memory.
        supervisor: Supervisor agent (GandalfAgent or any AIAgent implementer).
        supervisor_node_name: Graph node name for the supervisor.

    Returns:
        Compiled LangGraph state graph.
    """
    if supervisor is None:
        raise RuntimeError("build_graph requires a supervisor")

    workflow = StateGraph(AgentState)

    async def gandalf_wrapped(state: AgentState) -> dict[str, Any]:
        current_state = dict(state)
        update = await supervisor.run(current_state)

        while update.get("requires_approval", False):
            feedback = interrupt(update.get("approval_context") or {})
            feedback_text = str(feedback).strip()
            if feedback_text:
                # Normalize partial input to available options
                options = _approval_options(update.get("approval_context"))
                if len(feedback_text.split()) >= 2:
                    lowered = feedback_text.casefold()
                    for option in options:
                        if option.casefold() == lowered or option.casefold().endswith(
                            lowered
                        ):
                            feedback_text = option
                            break
                messages = list(current_state.get("messages", []))
                messages.append(HumanMessage(content=feedback_text))
                orig_query = str(current_state.get("query", ""))
                if orig_query and orig_query != feedback_text:
                    current_state["query"] = (
                        f"{orig_query}\n\nUser clarification: {feedback_text}"
                    )
                elif feedback_text:
                    current_state["query"] = feedback_text
                current_state["messages"] = messages
                current_state["user_feedback"] = feedback_text
            current_state["requires_approval"] = False
            current_state["approval_context"] = None
            update = await supervisor.run(current_state)

        return update

    workflow.add_node(supervisor_node_name, gandalf_wrapped)
    workflow.add_edge(START, supervisor_node_name)
    workflow.add_edge(supervisor_node_name, END)

    return workflow.compile(
        checkpointer=checkpointer,
        store=store,
        interrupt_before=[],
        name=supervisor_node_name,
    )
