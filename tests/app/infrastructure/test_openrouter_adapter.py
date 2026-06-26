"""Tests for OpenRouter adapter tracing behavior."""

from src.app.infrastructure.adapters.openrouter_adapter import _without_callbacks


def test_without_callbacks_removes_callbacks_from_inner_provider_config():
    callback = object()

    result = _without_callbacks(
        {
            "callbacks": [callback],
            "metadata": {"trace_id": "abc"},
            "tags": ["agent:test"],
        }
    )

    assert result.get("callbacks") == []
    assert result.get("metadata") == {"trace_id": "abc"}
    assert result.get("tags") == ["agent:test"]


def test_without_callbacks_accepts_empty_config():
    assert _without_callbacks(None) == {"callbacks": []}
