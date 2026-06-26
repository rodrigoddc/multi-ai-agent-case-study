#!/usr/bin/env python
"""Sync local JSONL datasets to Langfuse.

Usage:
    python evaluators/sync_langfuse_datasets.py --dataset hotel-insights-core-v1
    python evaluators/sync_langfuse_datasets.py --all
    python evaluators/sync_langfuse_datasets.py --all --host http://localhost:3000

Environment (for local/self-hosted Langfuse):
    LANGFUSE_PUBLIC_KEY=pk-lf-local-dev
    LANGFUSE_SECRET_KEY=sk-lf-local-dev
    LANGFUSE_HOST=http://localhost:3000
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from langfuse import get_client


def get_langfuse_client(host: str | None = None) -> Any:
    """Create Langfuse client with env or explicit host."""
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    if not public_key or not secret_key:
        raise RuntimeError("LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY must be set")
    client = get_client()
    if host:
        client._host = host  # type: ignore[attr-defined]
    return client


def load_local_dataset(dataset_name: str) -> list[dict]:
    """Load dataset from local JSONL file."""
    path = Path("evals/datasets") / f"{dataset_name}.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"Dataset file not found: {path}")
    items = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            items.append(json.loads(line))
    return items


def create_or_get_dataset(client, name: str, description: str | None = None):
    """Create dataset if it doesn't exist, return dataset object."""
    try:
        return client.get_dataset(name)
    except Exception:
        return client.create_dataset(
            name=name, description=description or f"Local dataset: {name}"
        )


def sync_dataset(client, dataset_name: str, items: list[dict]) -> int:
    """Sync dataset items to Langfuse. Returns count of items created/updated."""
    create_or_get_dataset(
        client,
        dataset_name,
        description=f"Auto-synced from local evals/datasets/{dataset_name}.jsonl",
    )

    count = 0
    for item in items:
        item_id = item.get("id")
        input_data = item.get("input", {})
        expected_output = item.get("expected_output", {})
        metadata = item.get("metadata", {})

        try:
            if item_id:
                # Try to upsert by ID
                client.create_dataset_item(
                    dataset_name=dataset_name,
                    id=item_id,
                    input=input_data,
                    expected_output=expected_output,
                    metadata=metadata,
                )
            else:
                client.create_dataset_item(
                    dataset_name=dataset_name,
                    input=input_data,
                    expected_output=expected_output,
                    metadata=metadata,
                )
            count += 1
        except Exception as e:
            print(f"  Warning: Failed to sync item {item_id}: {e}", file=sys.stderr)

    return count


def main():
    parser = argparse.ArgumentParser(description="Sync local datasets to Langfuse")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dataset", help="Dataset name (stem of .jsonl file)")
    group.add_argument(
        "--all", action="store_true", help="Sync all datasets in evals/datasets/"
    )
    parser.add_argument(
        "--host", help="Langfuse host (default: from LANGFUSE_HOST env)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print what would be done"
    )

    args = parser.parse_args()

    datasets_dir = Path("evals/datasets")
    if not datasets_dir.exists():
        print(f"Datasets directory not found: {datasets_dir}", file=sys.stderr)
        return 1

    if args.all:
        dataset_names = sorted(p.stem for p in datasets_dir.glob("*.jsonl"))
    else:
        dataset_names = [args.dataset]

    if not dataset_names:
        print("No datasets found", file=sys.stderr)
        return 1

    if args.dry_run:
        for name in dataset_names:
            items = load_local_dataset(name)
            print(f"Would sync {name}: {len(items)} items")
        return 0

    host = args.host or os.getenv("LANGFUSE_HOST")
    client = get_langfuse_client(host)

    total = 0
    for name in dataset_names:
        print(f"Syncing {name}...")
        items = load_local_dataset(name)
        count = sync_dataset(client, name, items)
        print(f"  {count} items synced")
        total += count

    client.flush()
    print(f"\nTotal: {total} items synced across {len(dataset_names)} dataset(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
