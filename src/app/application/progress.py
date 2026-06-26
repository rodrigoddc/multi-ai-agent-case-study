"""LangGraph custom progress event helpers."""

from __future__ import annotations

import logging

from langgraph.config import get_stream_writer

logger = logging.getLogger(__name__)


def emit_progress(content: str) -> None:
    """Emit a custom LangGraph progress message when streaming is active.

    Args:
        content: User-facing progress status.
    """
    _emit_custom_event({"content": content})


def emit_tool_call(name: str) -> None:
    """Emit a custom LangGraph tool-call event when streaming is active.

    Args:
        name: Stable user-safe tool name.
    """
    _emit_custom_event({"type": "tool_call", "name": name})


def _emit_custom_event(payload: dict[str, str]) -> None:
    try:
        writer = get_stream_writer()
    except KeyError, RuntimeError:
        return

    writer(payload)
