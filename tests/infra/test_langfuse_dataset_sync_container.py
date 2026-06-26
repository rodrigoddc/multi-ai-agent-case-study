"""Tests for the Langfuse dataset sync and online evaluator job containers."""

from __future__ import annotations

from pathlib import Path

APP_COMPOSE = Path("infra/container/app/docker-compose.yml")
LOCAL_COMPOSE = Path("infra/container/local/docker-compose.yml")
JOBS_DOCKERFILE = Path("infra/container/jobs/Dockerfile")


def test_app_compose_declares_langfuse_dataset_sync_job() -> None:
    """Local app Compose exposes a profiled dataset sync job."""
    compose = APP_COMPOSE.read_text(encoding="utf-8")

    assert "sync-langfuse-datasets:" in compose
    assert "evaluators/sync_langfuse_datasets.py" in compose
    assert 'profiles: ["sync"]' in compose


def test_app_compose_declares_langfuse_score_config_sync_job() -> None:
    """Local app Compose exposes a profiled Langfuse score config sync job."""
    compose = APP_COMPOSE.read_text(encoding="utf-8")

    assert "sync-langfuse-score-configs:" in compose
    assert "evaluators/sync_langfuse_score_configs.py" in compose
    assert 'profiles: ["sync"]' in compose


def test_app_compose_declares_langfuse_llm_judge_evaluator_sync_job() -> None:
    """Local app Compose exposes a profiled Langfuse LLM judge evaluator sync job."""
    compose = APP_COMPOSE.read_text(encoding="utf-8")

    assert "sync-langfuse-llm-judge-evaluators:" in compose
    assert "evaluators/sync_langfuse_llm_judge_evaluators.py" in compose
    assert 'profiles: ["sync"]' in compose


def test_local_compose_overrides_langfuse_dataset_sync_job() -> None:
    """Full-local Compose points dataset sync at the internal Langfuse service."""
    compose = LOCAL_COMPOSE.read_text(encoding="utf-8")

    assert "sync-langfuse-datasets:" in compose
    assert "LANGFUSE_HOST: http://langfuse-web:3000" in compose
    assert "langfuse-web:" in compose
    assert "langfuse-worker:" in compose


def test_local_compose_overrides_langfuse_score_config_sync_job() -> None:
    """Full-local Compose points score config sync at the internal Langfuse service."""
    compose = LOCAL_COMPOSE.read_text(encoding="utf-8")

    assert "sync-langfuse-score-configs:" in compose
    assert "LANGFUSE_HOST: http://langfuse-web:3000" in compose


def test_local_compose_overrides_llm_judge_evaluator_sync_job() -> None:
    """Full-local Compose points evaluator sync at the internal Langfuse service."""
    compose = LOCAL_COMPOSE.read_text(encoding="utf-8")

    assert "sync-langfuse-llm-judge-evaluators:" in compose
    assert "LANGFUSE_HOST: http://langfuse-web:3000" in compose


def test_local_compose_declares_online_evaluator_job() -> None:
    """Full-local Compose exposes a profiled sampled online evaluator job."""
    compose = LOCAL_COMPOSE.read_text(encoding="utf-8")

    assert "run-online-langfuse-evaluators:" in compose
    assert "evaluators/run_online_langfuse_evaluators.py" in compose
    assert 'profiles: ["eval"]' in compose


def test_jobs_image_copies_langfuse_eval_runtime_files() -> None:
    """Job image includes eval scripts, helpers, and local JSONL datasets."""
    dockerfile = JOBS_DOCKERFILE.read_text(encoding="utf-8")

    assert "COPY evaluators/ evaluators/" in dockerfile
    assert "COPY evals/*.py evals/" in dockerfile
    assert "COPY evals/datasets/ evals/datasets/" in dockerfile
