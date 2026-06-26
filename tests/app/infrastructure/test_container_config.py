"""Tests for container image/runtime configuration files."""

from pathlib import Path


def test_fastapi_image_includes_agent_config_files():
    dockerfile = Path("infra/container/app/Dockerfile").read_text(encoding="utf-8")

    assert "COPY config/ config/" in dockerfile


def test_compose_develop_watches_agent_config_files():
    compose = Path("infra/container/app/docker-compose.yml").read_text(encoding="utf-8")

    assert "path: ../../../config" in compose
    assert "target: /app/config" in compose
