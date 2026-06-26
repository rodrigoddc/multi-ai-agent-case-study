"""Langfuse observability configuration — infrastructure adapter.

Provides Langfuse CallbackHandler for tracing LangChain and LangGraph
executions. All tracing IDs use UUIDv8 for timestamp-sortable
ordering (Python 3.14+). Metadata tags include "pattern:single-dispatch-tool"
to identify the multi-agent architecture pattern per LangChain docs.
"""

from __future__ import annotations

import logging
from hashlib import sha256

from langfuse.langchain import CallbackHandler
from langfuse.types import TraceContext

from src.app.application.models.request_identity import new_uuid8_hex
from src.app.infrastructure.config import llm as LLM_SETTINGS

logger = logging.getLogger(__name__)

APP_TRACE_TAG = "multi-ai-agents-case-study"
ONLINE_EVAL_CANDIDATE_TAG = "online-eval-candidate"
ONLINE_EVAL_POLICY = "online-v1"
ONLINE_EVAL_SAMPLE_RATE = 0.10
ARCHITECTURE_TAG = "pattern:single-dispatch-tool"


def should_sample_for_online_evaluation(seed: str, sample_rate: float) -> bool:
    """Return whether a stable seed is inside the deterministic sample bucket."""
    if sample_rate <= 0:
        return False
    if sample_rate >= 1:
        return True
    digest = sha256(seed.encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) % 10_000
    return bucket < int(sample_rate * 10_000)


def get_langfuse_handler(trace_id: str | None = None) -> CallbackHandler | None:
    """Create a Langfuse CallbackHandler.

    Args:
        trace_id: Optional trace ID used as Langfuse trace context.

    Returns:
        CallbackHandler instance, or None if Langfuse is not configured.
    """

    trace_context: TraceContext | None = None
    if trace_id is not None and trace_id.strip():
        trace_context = {"trace_id": trace_id.strip()}
    return CallbackHandler(trace_context=trace_context)


def build_langfuse_config(
    user_id: str | None = None,
    session_id: str | None = None,
    trace_id: str | None = None,
    tags: list[str] | None = None,
    thread_id: str | None = None,
    route: str = "insights",
    sample_rate: float = ONLINE_EVAL_SAMPLE_RATE,
) -> dict | None:
    """Build a LangGraph-compatible config dict with Langfuse callbacks.

    Creates exactly one CallbackHandler per call — LangGraph propagates it
    to all child LLM invocations, producing a single trace per request.

    Args:
        user_id: User ID for trace attribution.
        session_id: Session ID for grouping traces. Defaults to UUIDv8.
        trace_id: Explicit trace ID. Defaults to UUIDv8.
        tags: Optional tags for filtering traces.
        thread_id: Optional conversation thread ID included in metadata.
        route: User-facing app route or workflow name.
        sample_rate: Deterministic online evaluation sample rate.

    Returns:
        Config dict with callbacks and metadata, or None if Langfuse is not configured.
    """
    handler = get_langfuse_handler(trace_id=trace_id)
    if handler is None:
        return None

    if user_id is None or not user_id.strip():
        user_id = "anonymous"
    else:
        user_id = user_id.strip()
    if session_id is None or not session_id.strip():
        session_id = new_uuid8_hex()
    else:
        session_id = session_id.strip()
    if trace_id is None or not trace_id.strip():
        trace_id = new_uuid8_hex()
    else:
        trace_id = trace_id.strip()

    sample_seed = trace_id or thread_id or session_id or user_id
    eval_candidate = should_sample_for_online_evaluation(sample_seed, sample_rate)
    effective_tags = [APP_TRACE_TAG, route, ARCHITECTURE_TAG, *(tags or [])]
    if eval_candidate:
        effective_tags.append(ONLINE_EVAL_CANDIDATE_TAG)

    config: dict = {"callbacks": [handler]}
    metadata: dict = {
        "langfuse_user_id": user_id,
        "langfuse_session_id": session_id,
        "langfuse_trace_id": trace_id,
        "app": APP_TRACE_TAG,
        "route": route,
        "llm_selection": "per-agent-yaml",
        "llm_default_provider": LLM_SETTINGS.LLM_PROVIDER,
        "llm_default_model": LLM_SETTINGS.LLM_PROVIDER_MODEL,
        "eval_policy": ONLINE_EVAL_POLICY,
        "eval_sample_rate": str(sample_rate),
        "eval_candidate": str(eval_candidate),
    }
    if thread_id is not None and thread_id.strip():
        metadata["thread_id"] = thread_id.strip()
    metadata["langfuse_tags"] = _dedupe_tags(effective_tags)

    config["metadata"] = metadata
    return config


class LangfuseTracingService:
    """Container-managed tracing service for LangGraph requests."""

    def build_config(
        self,
        user_id: str,
        session_id: str,
        thread_id: str,
        trace_id: str | None = None,
        route: str = "insights",
    ) -> dict | None:
        """Build Langfuse runnable config for one request.

        Returns None if Langfuse is not configured.
        """
        return build_langfuse_config(
            user_id=user_id,
            session_id=session_id,
            trace_id=trace_id,
            thread_id=thread_id,
            tags=[route],
            route=route,
        )


def _dedupe_tags(tags: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        clean_tag = tag.strip()
        if not clean_tag or clean_tag in seen:
            continue
        seen.add(clean_tag)
        deduped.append(clean_tag)
    return deduped
