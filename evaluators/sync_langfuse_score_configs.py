#!/usr/bin/env python
"""Sync canonical score configs to Langfuse.

Langfuse server-side evaluator setup has two parts:
1. Score configs: reusable score definitions stored on the Langfuse server.
2. Evaluator execution: local/online jobs that write scores using these names.

This script provisions the score configs so Langfuse has the evaluator/score
schema before dataset experiments or online evaluator jobs emit scores.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from langfuse import get_client
from langfuse.api.commons.types.config_category import ConfigCategory
from langfuse.api.commons.types.score_config_data_type import ScoreConfigDataType

from evals.scoring import SCORE_DEFINITIONS, ScoreDataType


@dataclass(frozen=True)
class ScoreConfigDefinition:
    """Langfuse score config definition."""

    name: str
    data_type: str
    description: str
    min_value: float | None = None
    max_value: float | None = None
    categories: tuple[tuple[float, str], ...] = ()


ADDITIONAL_SCORE_CONFIGS: tuple[ScoreConfigDefinition, ...] = (
    ScoreConfigDefinition(
        name="no_internal_agent_leakage",
        data_type=ScoreDataType.BOOLEAN,
        description="Whether user-facing output avoids internal agent names.",
        categories=((0.0, "fail"), (1.0, "pass")),
    ),
    ScoreConfigDefinition(
        name="no_empty_data_fallback",
        data_type=ScoreDataType.BOOLEAN,
        description="Whether user-facing output avoids empty/no-data fallback text.",
        categories=((0.0, "fail"), (1.0, "pass")),
    ),
)


def canonical_score_configs() -> list[ScoreConfigDefinition]:
    """Return score configs for local evals and Langfuse online evaluators."""
    configs: list[ScoreConfigDefinition] = []
    for name, definition in SCORE_DEFINITIONS.items():
        score_range = definition.get("range") or []
        min_value = float(score_range[0]) if len(score_range) == 2 else None
        max_value = float(score_range[1]) if len(score_range) == 2 else None
        configs.append(
            ScoreConfigDefinition(
                name=name,
                data_type=definition["data_type"],
                description=definition["description"],
                min_value=min_value,
                max_value=max_value,
                categories=_default_categories(definition["data_type"]),
            )
        )
    configs.extend(ADDITIONAL_SCORE_CONFIGS)
    return configs


def get_langfuse_client(host: str | None = None) -> Any:
    """Create Langfuse client with environment credentials."""
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    if not public_key or not secret_key:
        raise RuntimeError("LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY must be set")
    if host:
        os.environ["LANGFUSE_HOST"] = host
    return get_client()


def sync_score_configs(
    client: Any, configs: list[ScoreConfigDefinition]
) -> tuple[int, int]:
    """Create or update score configs by name."""
    existing = _existing_score_configs_by_name(client)
    created = 0
    updated = 0

    for config in configs:
        existing_config = existing.get(config.name)
        if existing_config is None:
            client.api.score_configs.create(
                name=config.name,
                data_type=_langfuse_data_type(config.data_type),
                min_value=config.min_value,
                max_value=config.max_value,
                description=config.description,
            )
            created += 1
            print(f"Created score config: {config.name}")
            continue

        config_id = getattr(existing_config, "id")
        client.api.score_configs.update(
            config_id,
            name=config.name,
            min_value=config.min_value,
            max_value=config.max_value,
            description=config.description,
            is_archived=False,
        )
        updated += 1
        print(f"Updated score config: {config.name}")

    return created, updated


def _existing_score_configs_by_name(client: Any) -> dict[str, Any]:
    response = client.api.score_configs.get(limit=100)
    data = getattr(response, "data", []) or []
    return {config.name: config for config in data if getattr(config, "name", None)}


def _langfuse_data_type(data_type: str) -> ScoreConfigDataType:
    mapping = {
        ScoreDataType.NUMERIC: ScoreConfigDataType.NUMERIC,
        ScoreDataType.BOOLEAN: ScoreConfigDataType.BOOLEAN,
        ScoreDataType.CATEGORICAL: ScoreConfigDataType.CATEGORICAL,
        ScoreDataType.TEXT: ScoreConfigDataType.TEXT,
    }
    return mapping[data_type]


def _langfuse_categories(
    categories: tuple[tuple[float, str], ...],
) -> list[ConfigCategory] | None:
    if not categories:
        return None
    return [ConfigCategory(value=value, label=label) for value, label in categories]


def _default_categories(data_type: str) -> tuple[tuple[float, str], ...]:
    if data_type == ScoreDataType.BOOLEAN:
        return ((0.0, "fail"), (1.0, "pass"))
    return ()


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync Langfuse score configs")
    parser.add_argument("--host", help="Langfuse host; defaults to LANGFUSE_HOST")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    configs = canonical_score_configs()
    if args.dry_run:
        for config in configs:
            print(f"Would sync score config: {config.name} ({config.data_type})")
        print(f"Total: {len(configs)} score configs")
        return 0

    client = get_langfuse_client(args.host or os.getenv("LANGFUSE_HOST"))
    created, updated = sync_score_configs(client, configs)
    client.flush()
    print(f"Score configs synced: created={created}, updated={updated}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
