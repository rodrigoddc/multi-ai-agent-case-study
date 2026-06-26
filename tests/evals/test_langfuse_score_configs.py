"""Tests for Langfuse score config sync."""

from __future__ import annotations

from types import SimpleNamespace

from evals.scoring import SCORE_DEFINITIONS, ScoreDataType
from evaluators.sync_langfuse_score_configs import (
    ADDITIONAL_SCORE_CONFIGS,
    canonical_score_configs,
    sync_score_configs,
)


class FakeScoreConfigsApi:
    """Fake Langfuse score config API."""

    def __init__(self, existing: list[SimpleNamespace] | None = None) -> None:
        self.existing = existing or []
        self.created: list[dict] = []
        self.updated: list[tuple[str, dict]] = []

    def get(self, *, limit: int):
        """Return existing score configs."""
        return SimpleNamespace(data=self.existing[:limit])

    def create(self, **kwargs):
        """Capture created score config."""
        self.created.append(kwargs)
        return SimpleNamespace(id=f"config-{kwargs['name']}", **kwargs)

    def update(self, config_id: str, **kwargs):
        """Capture updated score config."""
        self.updated.append((config_id, kwargs))
        return SimpleNamespace(id=config_id, **kwargs)


class FakeClient:
    """Fake Langfuse client exposing score config API."""

    def __init__(self, existing: list[SimpleNamespace] | None = None) -> None:
        self.api = SimpleNamespace(score_configs=FakeScoreConfigsApi(existing))


def test_canonical_score_configs_include_local_score_definitions() -> None:
    """All local score definitions are provisioned as Langfuse score configs."""
    names = {config.name for config in canonical_score_configs()}

    assert set(SCORE_DEFINITIONS).issubset(names)


def test_canonical_score_configs_include_online_evaluator_scores() -> None:
    """Online evaluator-only scores are provisioned too."""
    names = {config.name for config in canonical_score_configs()}

    assert {config.name for config in ADDITIONAL_SCORE_CONFIGS}.issubset(names)
    assert "no_internal_agent_leakage" in names
    assert "no_empty_data_fallback" in names


def test_boolean_score_configs_have_pass_fail_categories() -> None:
    """Boolean score configs use explicit pass/fail categories."""
    configs = canonical_score_configs()

    boolean_configs = [
        config for config in configs if config.data_type == ScoreDataType.BOOLEAN
    ]

    assert boolean_configs
    assert all(
        config.categories == ((0.0, "fail"), (1.0, "pass"))
        for config in boolean_configs
    )


def test_numeric_score_configs_have_zero_one_bounds() -> None:
    """Numeric score configs preserve normalized 0-1 ranges."""
    configs = canonical_score_configs()

    numeric_configs = [
        config for config in configs if config.data_type == ScoreDataType.NUMERIC
    ]

    assert numeric_configs
    assert all(config.min_value == 0.0 for config in numeric_configs)
    assert all(config.max_value == 1.0 for config in numeric_configs)


def test_sync_score_configs_creates_missing_configs() -> None:
    """Missing Langfuse score configs are created."""
    client = FakeClient()

    created, updated = sync_score_configs(client, canonical_score_configs()[:2])

    assert created == 2
    assert updated == 0
    assert len(client.api.score_configs.created) == 2


def test_sync_score_configs_updates_existing_configs() -> None:
    """Existing Langfuse score configs are updated by name."""
    existing = [SimpleNamespace(id="score-config-1", name="trajectory_match")]
    client = FakeClient(existing=existing)

    created, updated = sync_score_configs(client, canonical_score_configs()[:1])

    assert created == 0
    assert updated == 1
    assert client.api.score_configs.updated[0][0] == "score-config-1"
    assert client.api.score_configs.updated[0][1]["name"] == "trajectory_match"
