#!/usr/bin/env python
"""Run Langfuse dataset experiment locally.

This runs a task function against each dataset item and evaluates with
local evaluators (deterministic + optional LLM-as-judge).

Usage:
    python evaluators/run_langfuse_dataset_experiment.py \
        --dataset hotel-insights-core-v1 \
        --experiment-name fellowship-trajectory-v1 \
        --host http://localhost:3000

Environment (for local/self-hosted Langfuse):
    LANGFUSE_PUBLIC_KEY=pk-lf-local-dev
    LANGFUSE_SECRET_KEY=***
    LANGFUSE_HOST=http://localhost:3000
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from langfuse import get_client
from langfuse.experiment import LocalExperimentItem

from evals.helpers import load_dataset
from evals.trajectory import expected_tool_sequence_from_dataset
from evals.scoring import ScoreName


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


async def task_function(item: LocalExperimentItem) -> dict[str, Any]:
    """Task function that runs the agent graph for a dataset item.

    In a real implementation, this would invoke the actual LangGraph.
    For now, returns a mock trajectory for structural testing.
    """
    input_data = item.get("input", {}) if isinstance(item, dict) else item.input
    query = input_data.get("query", "")

    # TODO: Replace with actual graph invocation
    # from src.app.bootstrap.container import build_container
    # from src.app.application.services.chat_service import ChatService
    # container = await build_container(...)
    # result = await container.chat_service.process_chat(query=query, ...)
    # state = result.get("state")  # Need to expose state from chat_service

    # Return mock for structural validation
    return {
        "query": query,
        "mock_trajectory": [
            {
                "tool": "query_hotel_performance",
                "args": {"metric": "sentiment"},
                "agent": "aragorn",
            },
            {"tool": "analyze_competitors", "args": {}, "agent": "elrond"},
            {"tool": "summarize_insights", "args": {}, "agent": "bilbo"},
            {
                "tool": "safe_guardrail_response",
                "args": {"approved": True},
                "agent": "faramir",
            },
        ],
    }


def trajectory_match_evaluator(output: dict, expected: dict) -> dict:
    """Evaluate trajectory match against expected output from dataset."""
    expected_output = expected.get("expected_output", {}) if expected else {}

    # Extract expected tool sequence
    expected_sequence = expected_tool_sequence_from_dataset(expected_output)

    # Get actual trajectory from task output
    actual_trajectory = output.get("mock_trajectory", [])
    actual_tools = [step.get("tool") for step in actual_trajectory if step.get("tool")]

    # Simple subset match (all expected tools present)
    missing = [t for t in expected_sequence if t not in actual_tools]
    extra = [t for t in actual_tools if t not in expected_sequence]

    match = len(missing) == 0

    return {
        "score": float(match),
        "metadata": {
            "expected_tools": expected_sequence,
            "actual_tools": actual_tools,
            "missing_tools": missing,
            "extra_tools": extra,
        },
    }


def required_agents_coverage_evaluator(output: dict, expected: dict) -> dict:
    """Evaluate whether required agents were invoked."""
    expected_output = expected.get("expected_output", {}) if expected else {}
    required = set(expected_output.get("required_agents", []))
    forbidden = set(expected_output.get("forbidden_agents", []))

    actual_trajectory = output.get("mock_trajectory", [])
    actual_agents = set(
        step.get("agent") for step in actual_trajectory if step.get("agent")
    )

    covered = required & actual_agents
    violated = forbidden & actual_agents

    coverage = len(covered) / len(required) if required else 1.0
    forbidden_violated = len(violated) > 0

    return {
        "scores": {
            ScoreName.REQUIRED_AGENTS_COVERAGE: coverage,
            ScoreName.FORBIDDEN_AGENTS_AVOIDANCE: not forbidden_violated,
        },
        "metadata": {
            "required_agents": list(required),
            "forbidden_agents": list(forbidden),
            "actual_agents": list(actual_agents),
            "covered": list(covered),
            "violated": list(violated),
        },
    }


def topic_coverage_evaluator(output: dict, expected: dict) -> dict:
    """Evaluate topic coverage in final answer (mock)."""
    expected_output = expected.get("expected_output", {}) if expected else {}
    required_topics = expected_output.get("must_mention_topics", [])

    # In real implementation, check final_answer text
    final_answer = output.get("final_answer", "")

    mentioned = [t for t in required_topics if t.lower() in final_answer.lower()]
    coverage = len(mentioned) / len(required_topics) if required_topics else 1.0

    return {
        "score": coverage,
        "metadata": {
            "required_topics": required_topics,
            "mentioned_topics": mentioned,
        },
    }


def run_local_evaluators(output: dict, expected: dict) -> list[dict]:
    """Run all local deterministic evaluators, return list of score dicts."""
    results = []

    # Trajectory match
    traj_result = trajectory_match_evaluator(output, expected)
    results.append(
        {
            "name": ScoreName.TRAJECTORY_MATCH,
            "value": traj_result["score"],
            "data_type": "BOOLEAN",
            "metadata": traj_result["metadata"],
        }
    )

    # Required agents coverage
    agents_result = required_agents_coverage_evaluator(output, expected)
    for score_name, score_value in agents_result["scores"].items():
        results.append(
            {
                "name": score_name,
                "value": score_value,
                "data_type": "NUMERIC" if isinstance(score_value, float) else "BOOLEAN",
                "metadata": agents_result["metadata"],
            }
        )

    # Topic coverage
    topic_result = topic_coverage_evaluator(output, expected)
    results.append(
        {
            "name": ScoreName.TOPIC_COVERAGE,
            "value": topic_result["score"],
            "data_type": "NUMERIC",
            "metadata": topic_result["metadata"],
        }
    )

    return results


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Langfuse dataset experiment locally"
    )
    parser.add_argument("--dataset", required=True, help="Dataset name")
    parser.add_argument("--experiment-name", required=True, help="Experiment run name")
    parser.add_argument(
        "--host", help="Langfuse host (default: from LANGFUSE_HOST env)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Run locally, don't send to Langfuse"
    )
    parser.add_argument(
        "--max-concurrency", type=int, default=5, help="Max concurrent tasks"
    )
    args = parser.parse_args()

    # Load dataset items
    items_data = load_dataset(args.dataset)
    experiment_items = [
        LocalExperimentItem(
            input=item.get("input", {}),
            expected_output=item.get("expected_output", {}),
            metadata=item.get("metadata", {}),
        )
        for item in items_data
    ]

    if args.dry_run:
        print(
            f"DRY RUN: Would run experiment '{args.experiment_name}' on dataset '{args.dataset}'"
        )
        print(f"Items: {len(experiment_items)}")
        for item in experiment_items[:3]:
            item_id = item.get("metadata", {}).get("scenario", "unknown")  # type: ignore[union-attr]
            query = item.get("input", {}).get("query", "")[:60]
            print(f"  - {item_id}: {query}...")
        return 0

    client = get_langfuse_client(args.host)

    print(f"Running experiment '{args.experiment_name}' on dataset '{args.dataset}'...")
    print(f"Items: {len(experiment_items)}")

    def task(item: LocalExperimentItem) -> dict:
        return asyncio.run(task_function(item))

    def evaluator_fn(output: dict, expected: dict) -> list:
        scores = run_local_evaluators(output, expected)
        return [
            {
                "name": s["name"],
                "value": s["value"],
                "data_type": s["data_type"],
                "metadata": s["metadata"],
            }
            for s in scores
        ]

    result = client.run_experiment(
        name=args.dataset,
        run_name=args.experiment_name,
        task=task,
        evaluators=[evaluator_fn],
        data=experiment_items,
        max_concurrency=args.max_concurrency,
    )

    print("\nExperiment completed!")
    print(f"Run ID: {result.run_id}")
    print(f"Items processed: {len(result.results)}")

    # Print summary
    scores_summary = {}
    for r in result.results:
        for score in r.scores:
            name = score.name
            if name not in scores_summary:
                scores_summary[name] = []
            scores_summary[name].append(score.value)

    print("\nScore summary:")
    for name, values in scores_summary.items():
        if values and isinstance(values[0], (int, float)):
            avg = sum(values) / len(values)
            print(f"  {name}: {avg:.3f} (n={len(values)})")
        elif values and isinstance(values[0], bool):
            passed = sum(1 for v in values if v)
            print(f"  {name}: {passed}/{len(values)} passed")

    client.flush()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
