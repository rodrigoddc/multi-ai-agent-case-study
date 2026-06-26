"""Chat Service — Application use case for handling chat interactions.

Orchestrates the LangGraph execution and state management.
"""

from __future__ import annotations

import logging
import re
from langgraph.graph.state import CompiledStateGraph

from src.app.application.models.request_identity import build_request_identity
from src.app.application.services.graph_input import (
    build_graph_config,
    build_graph_input,
)

logger = logging.getLogger(__name__)


_GENERIC_CAPABILITY_TAILS = (
    "I can help you with hotel performance questions, such as occupancy, RevPAR, sentiment trends, or portfolio comparisons. Please let me know what specific information you are looking for.",
    "I can help you with occupancy, RevPAR, sentiment trends, or portfolio comparisons.",
)


def _strip_generic_marketing(answer: str) -> str:
    cleaned = answer
    for tail in _GENERIC_CAPABILITY_TAILS:
        if tail in cleaned:
            cleaned = cleaned.replace(tail, "").strip()
    return cleaned


def md_to_html(text: str) -> str:
    """Minimal markdown-to-HTML for the subset Bilbo produces.

    Handles ## headings, **bold**, | table | syntax, and - lists.
    The result is safe for `| safe` in a Tailwind prose block.
    """
    lines = text.split("\n")
    out: list[str] = []
    in_table = False
    for line in lines:
        # Headings
        h_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if h_match:
            level = len(h_match.group(1))
            out.append(f"<h{level}>{h_match.group(2)}</h{level}>")
            continue
        # Bold
        bolded = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line)
        # Table rows
        is_table_row = bool(re.match(r"^\|.+\|$", bolded.strip()))
        if is_table_row:
            cells = [c.strip() for c in bolded.strip().strip("|").split("|")]
            # Skip separator row (|---|)
            if re.match(r"^[\s\-:|]+$", "|".join(cells)):
                continue
            if not in_table:
                # First row — open table, treat as header
                in_table = True
                out.append(
                    "<table><thead><tr>"
                    + "".join(f"<th>{c}</th>" for c in cells)
                    + "</tr></thead><tbody>"
                )
            else:
                out.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
            continue
        # Close table if exiting table context
        if in_table:
            out.append("</tbody></table>")
            in_table = False
        out.append(bolded)
    if in_table:
        out.append("</tbody></table>")
    html = "\n".join(out)
    # -- list items — skip if inside a table
    html = re.sub(r"^- (.+)$", r"<li>\1</li>", html, flags=re.MULTILINE)
    html = re.sub(r"((?:<li>.*?</li>\n?)+)", r"<ul>\1</ul>", html)
    return html


class ChatServiceError(Exception):
    """Domain error from ChatService operations."""


class ChatServiceTimeoutError(ChatServiceError):
    """Raised when the underlying LLM/graph call times out."""


class LLMAuthenticationError(ChatServiceError):
    """Raised when the LLM provider rejects the request due to missing/invalid credentials."""


class LLMProviderUnavailableError(ChatServiceError):
    """Raised when the configured LLM provider cannot be reached."""


class ChatService:
    """Handles chat interactions with the multi-agent graph."""

    def __init__(self, graph: CompiledStateGraph) -> None:
        self.graph = graph

    async def process_chat(
        self,
        message: str,
        thread_id: str | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
        tracing_config: dict | None = None,
        display_name: str | None = None,
    ) -> dict:
        """Process a chat message and return the final state.

        Args:
            message: User's input message.
            thread_id: Optional thread ID for conversation continuity.
            user_id: User identifier for tracing.
            session_id: Optional session ID for grouping traces.
            tracing_config: Optional pre-built Langfuse/LangGraph config.
            display_name: Optional user display name from browser storage.

        Returns:
            Dict containing final_answer, thread_id, and reasoning_trace.

        Raises:
            ChatServiceTimeoutError: If the graph/llm invocation times out.
        """
        identity = build_request_identity(
            user_id=user_id,
            thread_id=thread_id,
            session_id=session_id,
            display_name=display_name,
        )
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
            display_name=identity.display_name,
        )

        logger.info("Processing chat message (thread_id=%s)", identity.thread_id)
        try:
            result = await self.graph.ainvoke(graph_input, config)
        except LLMAuthenticationError, LLMProviderUnavailableError:
            raise
        except Exception as e:
            # Check if any wrapped exception is a timeout
            if isinstance(e, TimeoutError) or "timeout" in str(e).lower():
                error_msg = str(e)
                log_msg = error_msg[:500] + ("..." if len(error_msg) > 500 else "")
                logger.warning(
                    "Chat service timed out (thread_id=%s): %s",
                    identity.thread_id,
                    log_msg,
                )
                raise ChatServiceTimeoutError(f"LLM request timed out: {e}") from e
            raise

        return {
            "final_answer": _strip_generic_marketing(result.get("final_answer", "")),
            "thread_id": identity.thread_id,
            "reasoning_trace": result.get("reasoning_trace", ""),
        }
