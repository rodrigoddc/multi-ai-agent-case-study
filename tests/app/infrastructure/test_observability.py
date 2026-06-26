"""Tests for Langfuse tracing config metadata."""

from src.app.infrastructure.observability import build_langfuse_config


def test_langfuse_config_marks_llm_env_values_as_defaults():
    config = build_langfuse_config(
        user_id="user-1",
        session_id="session-1",
        trace_id="trace-1",
        sample_rate=0,
    )

    assert config is not None
    metadata = config["metadata"]
    assert metadata["llm_selection"] == "per-agent-yaml"
    assert "llm_default_provider" in metadata
    assert "llm_default_model" in metadata
    assert "llm_provider" not in metadata
    assert "llm_model" not in metadata
