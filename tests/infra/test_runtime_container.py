"""Tests for the local sync job container setup."""

from __future__ import annotations

from pathlib import Path

APP_COMPOSE = Path("infra/container/app/docker-compose.yml")
LOCAL_COMPOSE = Path("infra/container/local/docker-compose.yml")
JOBS_DOCKERFILE = Path("infra/container/jobs/Dockerfile")


def test_app_compose_includes_sync_jobs() -> None:
    """Local app Compose includes profiled Langfuse sync jobs."""
    compose = APP_COMPOSE.read_text(encoding="utf-8")

    assert "sync-langfuse-datasets:" in compose
    assert "sync-langfuse-score-configs:" in compose
    assert 'profiles: ["sync"]' in compose


def test_local_compose_includes_sync_job_overrides() -> None:
    """Full-local Compose overrides Langfuse sync jobs for internal networking."""
    compose = LOCAL_COMPOSE.read_text(encoding="utf-8")

    assert "sync-langfuse-datasets:" in compose
    assert "sync-langfuse-score-configs:" in compose
    assert "sleep infinity" not in compose
    assert "LANGFUSE_HOST: http://langfuse-web:3000" in compose


def test_jobs_image_copies_eval_sync_runtime_files() -> None:
    """Sync job image includes command scripts and local datasets."""
    text = JOBS_DOCKERFILE.read_text(encoding="utf-8")

    assert "COPY evaluators/ evaluators/" in text
    assert "COPY evals/datasets/ evals/datasets/" in text
