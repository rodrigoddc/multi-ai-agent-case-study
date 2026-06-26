"""Application environment strategies."""

from __future__ import annotations

from dataclasses import dataclass

from src.app.infrastructure.config import AppEnvironment


@dataclass(frozen=True, slots=True)
class AppStrategy:
    """Runtime policy for a specific application environment."""

    environment: AppEnvironment
    persistence_enabled: bool
    auto_create_tables: bool
    langfuse_required: bool
    mount_static: bool


_STRATEGIES: dict[AppEnvironment, AppStrategy] = {
    AppEnvironment.LOCAL: AppStrategy(
        environment=AppEnvironment.LOCAL,
        persistence_enabled=True,
        auto_create_tables=True,
        langfuse_required=True,
        mount_static=True,
    ),
    AppEnvironment.TEST: AppStrategy(
        environment=AppEnvironment.TEST,
        persistence_enabled=False,
        auto_create_tables=False,
        langfuse_required=False,
        mount_static=True,
    ),
    AppEnvironment.DEV: AppStrategy(
        environment=AppEnvironment.DEV,
        persistence_enabled=True,
        auto_create_tables=True,
        langfuse_required=True,
        mount_static=True,
    ),
    AppEnvironment.PROD: AppStrategy(
        environment=AppEnvironment.PROD,
        persistence_enabled=True,
        auto_create_tables=False,
        langfuse_required=True,
        mount_static=True,
    ),
}
