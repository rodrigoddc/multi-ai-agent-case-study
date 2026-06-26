"""Evaluation helpers for local dataset tests and Langfuse integration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DATASETS_DIR = Path("evals/datasets")


def list_datasets() -> list[str]:
    """List available dataset files (stem names without .jsonl)."""
    if not DATASETS_DIR.exists():
        return []
    return sorted(p.stem for p in DATASETS_DIR.glob("*.jsonl"))


def load_dataset(name: str) -> list[dict[str, Any]]:
    """Load a JSONL dataset by stem name (e.g., 'hotel-insights-core-v1')."""
    path = DATASETS_DIR / f"{name}.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def dataset_item_input(item: dict[str, Any]) -> dict[str, Any]:
    """Extract the input dict from a dataset item (Langfuse LocalExperimentItem compatible)."""
    return item.get("input", {})


def dataset_item_expected_output(item: dict[str, Any]) -> dict[str, Any] | None:
    """Extract the expected_output dict from a dataset item."""
    return item.get("expected_output")


def dataset_item_metadata(item: dict[str, Any]) -> dict[str, Any] | None:
    """Extract the metadata dict from a dataset item."""
    return item.get("metadata")


__all__ = [
    "DATASETS_DIR",
    "list_datasets",
    "load_dataset",
    "dataset_item_input",
    "dataset_item_expected_output",
    "dataset_item_metadata",
]
