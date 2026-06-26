"""SSE Service — Application use case for graph progress streaming.

Generates Server-Sent Events from real LangGraph custom progress messages.
LangGraph node updates are only inspected for the final answer; they are not
shown as progress because node labels are inferred by this service, not emitted
by the running agent/tool code.
"""

from __future__ import annotations

import logging
import re
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from fastapi.templating import Jinja2Templates
from langgraph.graph.state import CompiledStateGraph
from sse_starlette import ServerSentEvent

from src.app.application.models.request_identity import (
    build_request_identity,
    new_uuid8_hex,
)
from src.app.application.services.graph_input import (
    build_graph_config,
    build_graph_input,
)
from src.app.application.services.chat_service import (
    LLMProviderUnavailableError,
    _strip_generic_marketing,  # ponytail: shared helper, not duplicated
    md_to_html,
)

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[2]
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@dataclass
class AgentActivity:
    """Display grouping for one agent's progress branch."""

    agent_name: str
    activity: str
    details: list[str]


_AGENT_LABEL_PREFIXES: dict[str, str] = {
    "gandalf": "Gandalf is ",
    "aragorn": "Aragorn is ",
    "samwise": "Samwise is ",
    "elrond": "Elrond is ",
    "bilbo": "Bilbo is ",
    "faramir": "Faramir is ",
    "radagast": "Radagast is ",
}

_TOOL_AGENT_PREFIXES: dict[str, str] = {
    "load_user_preferences": "Samwise",
    "samwise.": "Samwise",
    "get_portfolio_metrics": "Elrond",
    "get_top_hotels": "Elrond",
    "get_underperforming_hotels": "Elrond",
    "get_top_hotels_by": "Elrond",
    "get_underperforming_hotels_by": "Elrond",
    "get_hotels_by_trend": "Elrond",
    "elrond.": "Elrond",
}


class SSEChatService:
    """Handles chat progress streaming from real agent-emitted events."""

    def __init__(self, graph: CompiledStateGraph) -> None:
        self.graph = graph

    async def stream_chat(
        self,
        message: str,
        user_id: str | None = None,
        thread_id: str | None = None,
        session_id: str | None = None,
        tracing_config: dict | None = None,
        message_id: str | None = None,
        target_id: str = "chat-messages",
        thread_input_id: str = "thread-id",
        display_name: str | None = None,
    ) -> AsyncGenerator[ServerSentEvent, None]:
        """Stream real custom progress events and the final graph answer.

        Args:
            message: User's input message.
            user_id: User identifier for tracing.
            thread_id: Optional thread ID for conversation continuity.
            session_id: Optional session ID for grouping traces.
            tracing_config: Optional pre-built Langfuse/LangGraph config.
            message_id: Optional rendered chat message ID for OOB fragments.
            target_id: DOM ID of the chat message container for HTMX scroll targets.
            thread_input_id: DOM ID of the thread input updated by streamed fragments.

        Yields:
            ServerSentEvent objects containing server-rendered HTML fragments.
        """
        identity = build_request_identity(
            user_id=user_id,
            thread_id=thread_id,
            session_id=session_id,
        )
        effective_message_id = message_id or new_uuid8_hex()
        emitted_labels: set[str] = set()
        emitted_answers: set[str] = set()
        finalized_workflows: set[str] = set()
        agent_activities: list[AgentActivity] = []
        config = build_graph_config(
            user_id=identity.user_id,
            thread_id=identity.thread_id,
            session_id=identity.session_id,
            tracing_config=tracing_config,
        )
        graph_input = await build_graph_input(
            graph=self.graph,
            config=config,
            message=message,
            user_id=identity.user_id,
            thread_id=identity.thread_id,
            display_name=display_name,
        )

        logger.info("Starting SSE progress stream (thread_id=%s)", identity.thread_id)

        try:
            async for stream_item in cast(Any, self.graph).astream(
                graph_input,
                config,
                stream_mode=["updates", "custom"],
                version="v2",
            ):
                stream_mode, chunk = self._parse_stream_item(stream_item)

                if stream_mode == "custom":
                    label = self._extract_custom_label(chunk)
                    if label:
                        async for event in self._build_activity_events(
                            label=label,
                            message_id=effective_message_id,
                            emitted_labels=emitted_labels,
                            agent_activities=agent_activities,
                        ):
                            yield event
                    continue

                if stream_mode == "updates":
                    async for event in self._stream_final_answer_events(
                        update=chunk,
                        thread_id=identity.thread_id,
                        message_id=effective_message_id,
                        agent_activities=agent_activities,
                        emitted_answers=emitted_answers,
                        finalized_workflows=finalized_workflows,
                        target_id=target_id,
                        thread_input_id=thread_input_id,
                    ):
                        yield event

            yield ServerSentEvent(event="done", data="")
            logger.info(
                "SSE progress stream complete (thread_id=%s)", identity.thread_id
            )

        except LLMProviderUnavailableError as exc:
            logger.warning(
                "SSE progress stream provider unavailable (thread_id=%s): %s",
                identity.thread_id,
                exc,
            )
            yield self._build_status_event(
                label=str(exc),
                message_id=effective_message_id,
                status="failed",
            )
            yield self._build_answer_event(
                content=str(exc),
                thread_id=identity.thread_id,
                message_id=effective_message_id,
                agent_activities=agent_activities,
                target_id=target_id,
                thread_input_id=thread_input_id,
            )
            yield ServerSentEvent(event="done", data="")
        except Exception as exc:
            logger.exception(
                "SSE progress stream error (thread_id=%s): %s", identity.thread_id, exc
            )
            yield self._build_status_event(
                label="The assistant hit an error while processing this request",
                message_id=effective_message_id,
                status="failed",
            )
            yield ServerSentEvent(event="done", data="")

    def _parse_stream_item(self, stream_item: Any) -> tuple[str | None, Any]:
        """Normalize LangGraph stream output shapes."""
        if isinstance(stream_item, dict):
            stream_type = stream_item.get("type")
            if isinstance(stream_type, str) and "data" in stream_item:
                return stream_type, stream_item.get("data")
            return None, stream_item

        if not isinstance(stream_item, tuple):
            return None, stream_item

        if len(stream_item) == 2:
            stream_mode, chunk = stream_item
            return stream_mode, chunk

        if len(stream_item) == 3:
            _, stream_mode, chunk = stream_item
            return stream_mode, chunk

        logger.debug("Ignoring unknown LangGraph stream item shape: %r", stream_item)
        return None, None

    async def _stream_final_answer_events(
        self,
        update: Any,
        thread_id: str,
        message_id: str,
        agent_activities: list[AgentActivity],
        emitted_answers: set[str],
        finalized_workflows: set[str],
        target_id: str = "chat-messages",
        thread_input_id: str = "thread-id",
    ) -> AsyncGenerator[ServerSentEvent, None]:
        """Yield a final answer event when a graph update contains display content."""
        if not isinstance(update, dict):
            return

        interrupt_context = _extract_interrupt_context(update.get("__interrupt__"))
        question = _interrupt_question(interrupt_context)
        if question:
            answer_key = _answer_key(question)
            if answer_key in emitted_answers:
                return
            emitted_answers.add(answer_key)
            async for event in self._finalize_workflow_events(
                message_id=message_id,
                agent_activities=agent_activities,
                finalized_workflows=finalized_workflows,
            ):
                yield event
            yield self._build_answer_event(
                content=question,
                thread_id=thread_id,
                message_id=message_id,
                agent_activities=agent_activities,
                is_clarification=True,
                clarifying_question=question,
                options=_clarification_options(interrupt_context),
                target_id=target_id,
                thread_input_id=thread_input_id,
            )
            return

        for node_update in update.values():
            if not isinstance(node_update, dict):
                continue

            if node_update.get("requires_approval", False):
                continue

            final_answer = node_update.get("final_answer")
            if not isinstance(final_answer, str) or not final_answer.strip():
                continue

            answer = _strip_generic_marketing(final_answer.strip())
            answer_key = _answer_key(answer)
            if answer_key in emitted_answers:
                continue
            emitted_answers.add(answer_key)
            is_clarification = _is_clarifying_question(answer)
            async for event in self._finalize_workflow_events(
                message_id=message_id,
                agent_activities=agent_activities,
                finalized_workflows=finalized_workflows,
            ):
                yield event
            yield self._build_answer_event(
                content=answer,
                thread_id=thread_id,
                message_id=message_id,
                agent_activities=agent_activities,
                is_clarification=is_clarification,
                clarifying_question=answer if is_clarification else None,
                target_id=target_id,
                thread_input_id=thread_input_id,
            )

    async def _build_activity_events(
        self,
        label: str,
        message_id: str,
        emitted_labels: set[str],
        agent_activities: list[AgentActivity],
    ) -> AsyncGenerator[ServerSentEvent, None]:
        clean_label = label.strip()
        if not clean_label or clean_label in emitted_labels:
            return

        emitted_labels.add(clean_label)
        previous_activity_count = len(agent_activities)
        previous_activity = agent_activities[-1] if agent_activities else None
        agent_activities[:] = self._append_agent_activity(agent_activities, clean_label)
        started_new_activity = len(agent_activities) > previous_activity_count
        yield self._build_status_event(label=clean_label, message_id=message_id)
        if started_new_activity and previous_activity is not None:
            yield self._build_completed_step_event(
                activity=previous_activity,
                message_id=message_id,
                step_number=len(agent_activities) - 1,
            )
        yield self._build_active_step_event(
            activity=agent_activities[-1], message_id=message_id
        )

    async def _finalize_workflow_events(
        self,
        message_id: str,
        agent_activities: list[AgentActivity],
        finalized_workflows: set[str],
    ) -> AsyncGenerator[ServerSentEvent, None]:
        """Complete the visible final activity before rendering the answer."""
        if message_id in finalized_workflows:
            return

        finalized_workflows.add(message_id)
        if agent_activities:
            yield self._build_completed_step_event(
                activity=agent_activities[-1],
                message_id=message_id,
                step_number=len(agent_activities),
            )
        yield self._build_clear_active_step_event()
        yield self._build_status_event(
            label="Assistant workflow complete",
            message_id=message_id,
            status="complete",
        )

    def _build_status_event(
        self,
        label: str,
        message_id: str,
        status: str = "running",
    ) -> ServerSentEvent:
        """Build an HTMX SSE status summary from a Jinja fragment."""
        return ServerSentEvent(
            event="ChatStatus",
            data=self._render_template(
                "components/chat_progress_summary.html",
                {"label": label, "message_id": message_id, "status": status},
            ),
        )

    def _build_completed_step_event(
        self, activity: AgentActivity, message_id: str, step_number: int
    ) -> ServerSentEvent:
        """Build an HTMX SSE completed timeline item."""
        return ServerSentEvent(
            event="ChatCompletedStep",
            data=self._render_template(
                "components/chat_completed_step_item.html",
                {
                    "agent_name": activity.agent_name,
                    "activity": activity.activity,
                    "details": activity.details,
                    "completed_step_id": f"chat-completed-step-{message_id}-{step_number}",
                },
            ),
        )

    def _build_active_step_event(
        self, activity: AgentActivity, message_id: str
    ) -> ServerSentEvent:
        """Build an HTMX SSE active timeline item."""
        return ServerSentEvent(
            event="ChatActiveStep",
            data=self._render_template(
                "components/chat_step_item.html",
                {
                    "agent_name": activity.agent_name,
                    "activity": activity.activity,
                    "details": activity.details,
                    "message_id": message_id,
                    "status": "running",
                },
            ),
        )

    def _build_clear_active_step_event(self) -> ServerSentEvent:
        """Clear the HTMX active-step slot after the final step completes."""
        return ServerSentEvent(event="ChatActiveStep", data="")

    def _extract_options_from_question(self, question: str) -> list[str] | None:
        """Extract explicit binary options from a clarifying question."""
        q = question.strip()
        want_match = re.search(
            r"(?:would you like|do you want|do you prefer|please choose)\s+(.+?)\s+or\s+(.+?)[?.]?\s*$",
            q,
            re.IGNORECASE,
        )
        if want_match:
            return _clean_options(want_match.group(1), want_match.group(2))

        return None

    def _build_answer_event(
        self,
        content: str,
        thread_id: str,
        message_id: str,
        agent_activities: list[AgentActivity],
        is_clarification: bool = False,
        clarifying_question: str | None = None,
        options: list[str] | None = None,
        target_id: str = "chat-messages",
        thread_input_id: str = "thread-id",
    ) -> ServerSentEvent:
        """Build an HTMX SSE final-answer event from a Jinja fragment."""
        rendered_options = options
        if is_clarification and clarifying_question:
            rendered_options = rendered_options or self._extract_options_from_question(
                clarifying_question
            )

        return ServerSentEvent(
            event="ChatFinal",
            data=self._render_template(
                "components/chat_final_answer.html",
                {
                    "content": md_to_html(content),
                    "thread_id": thread_id,
                    "message_id": message_id,
                    "agent_activities": agent_activities,
                    "is_clarification": is_clarification,
                    "clarifying_question": clarifying_question,
                    "options": rendered_options,
                    "target_id": target_id,
                    "thread_input_id": thread_input_id,
                },
            ),
        )

    def _render_template(self, name: str, context: dict[str, Any]) -> str:
        template = templates.env.get_template(name)
        return template.render(**context).strip()

    def _append_agent_activity(
        self, activities: list[AgentActivity], label: str
    ) -> list[AgentActivity]:
        agent_name, detail = self._split_agent_activity(label)
        if activities and activities[-1].agent_name == agent_name:
            activities[-1].details.append(detail)
            return activities
        return [
            *activities,
            AgentActivity(agent_name=agent_name, activity=detail, details=[]),
        ]

    def _split_agent_activity(self, label: str) -> tuple[str, str]:
        if label.lower().startswith("calling tool: "):
            tool_name = label.split(":", maxsplit=1)[1].strip()
            return self._agent_for_tool(tool_name), f"calling tool: {tool_name}"

        for agent_name, prefix in _AGENT_LABEL_PREFIXES.items():
            if label.startswith(prefix):
                return agent_name.title(), label.removeprefix(prefix)
        return "Agent", label

    def _agent_for_tool(self, tool_name: str) -> str:
        for prefix, agent_name in _TOOL_AGENT_PREFIXES.items():
            if tool_name.startswith(prefix):
                return agent_name
        return "Agent"

    def _extract_custom_label(self, chunk: Any) -> str | None:
        if isinstance(chunk, str):
            return chunk.strip() or None

        if not isinstance(chunk, dict):
            return None

        event_type = chunk.get("type")
        if event_type == "tool_call":
            name = chunk.get("name")
            if isinstance(name, str) and name.strip():
                return f"Calling tool: {name.strip()}"
            return None

        content = chunk.get("content") or chunk.get("status") or chunk.get("message")
        if isinstance(content, str) and content.strip():
            return content.strip()
        return None


def _answer_key(content: str) -> str:
    """Normalize answer text for stream-level deduplication."""
    return " ".join(content.split()).casefold()


def _extract_interrupt_context(interrupt_data: Any) -> dict[str, Any] | None:
    """Extract the LangGraph interrupt context payload."""
    if not isinstance(interrupt_data, (list, tuple)) or not interrupt_data:
        return None
    interrupt_value = getattr(interrupt_data[0], "value", interrupt_data[0])
    if isinstance(interrupt_value, dict):
        return interrupt_value
    return None


def _interrupt_question(context: dict[str, Any] | None) -> str | None:
    if not isinstance(context, dict):
        return None
    question = context.get("question") or context.get("clarifying_question")
    if isinstance(question, str) and question.strip():
        return question.strip()
    return None


def _clarification_options(context: dict[str, Any] | None) -> list[str]:
    if not isinstance(context, dict):
        return []
    raw_options = context.get("options", [])
    if not isinstance(raw_options, list):
        return []
    return [option for option in raw_options if isinstance(option, str) and option]


def _clean_options(raw_first: str, raw_second: str) -> list[str] | None:
    """Normalize two extracted clarification options."""
    first = raw_first.strip(" .?\n\t")
    second = raw_second.strip(" .?\n\t")
    if len(first) <= 2 or len(second) <= 2:
        return None
    return [first, second]


def _is_clarifying_question(content: str) -> bool:
    """Return whether final content should render as a clarification prompt."""
    lowered = content.lower().strip()
    if not lowered.endswith("?"):
        return False
    # Exclude conversational suggestions that happen to end with a question
    non_clarification_markers = (
        "i don't have",
        "i can help you with",
        "you can ask me",
        "would you like to tell me",
    )
    for marker in non_clarification_markers:
        if marker in lowered:
            return False
    return any(token in lowered for token in (" or ", "which ", "what "))
