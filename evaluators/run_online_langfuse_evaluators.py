#!/usr/bin/env python
"""Run deterministic online evaluators against sampled Langfuse traces.

This is the full-local online evaluation worker. It reads traces tagged and
marked by the app as online-eval candidates, runs deterministic evaluators, and
writes Langfuse scores back to the matching trace.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from langfuse import Evaluation, EvaluatorInputs, get_client

from evals.scoring import ScoreDataType, ScoreName

APP_TRACE_TAG = "multi-ai-agents-case-study"
ONLINE_EVAL_CANDIDATE_TAG = "online-eval-candidate"
ONLINE_EVALUATED_TAG = "online-evaluated"
ONLINE_EVAL_POLICY = "online-v1"
DEFAULT_TRACE_FIELDS = "core,io,scores,observations"


def langfuse_client(host: str | None = None) -> Any:
    """Create a Langfuse client using environment credentials."""
    if not os.getenv("LANGFUSE_PUBLIC_KEY") or not os.getenv("LANGFUSE_SECRET_KEY"):
        raise RuntimeError("LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY must be set")
    if host:
        os.environ["LANGFUSE_HOST"] = host
    return get_client()


def online_eval_filter(*, tags: Sequence[str] | None = None) -> str:
    """Build Langfuse API filter for app-sampled online-eval traces."""
    required_tags = [APP_TRACE_TAG, ONLINE_EVAL_CANDIDATE_TAG, *(tags or [])]
    return json.dumps(
        [
            {
                "type": "arrayOptions",
                "column": "tags",
                "operator": "all of",
                "value": required_tags,
            },
            {
                "type": "boolean",
                "column": "metadata",
                "key": "eval_candidate",
                "operator": "=",
                "value": True,
            },
            {
                "type": "stringObject",
                "column": "metadata",
                "key": "eval_policy",
                "operator": "=",
                "value": ONLINE_EVAL_POLICY,
            },
            {
                "type": "arrayOptions",
                "column": "tags",
                "operator": "none of",
                "value": [ONLINE_EVALUATED_TAG],
            },
        ]
    )


def trace_mapper(*, item: Any, **kwargs: Any) -> EvaluatorInputs:
    """Map a Langfuse trace into evaluator inputs."""
    metadata = dict(getattr(item, "metadata", None) or {})
    metadata["trace_id"] = getattr(item, "id", "")
    metadata["tags"] = list(getattr(item, "tags", []) or [])
    metadata["scores"] = _existing_score_names(getattr(item, "scores", []) or [])
    observations = list(getattr(item, "observations", []) or [])
    metadata["observation_names"] = [
        name
        for observation in observations
        if (name := str(getattr(observation, "name", "")).strip())
    ]
    return EvaluatorInputs(
        input=getattr(item, "input", None),
        output=getattr(item, "output", None),
        expected_output=None,
        metadata=metadata,
    )


def required_output_evaluator(
    *,
    input: Any,
    output: Any,
    expected_output: Any = None,
    metadata: dict | None = None,
) -> Evaluation:
    """Score whether the trace produced a usable output."""
    output_text = _text(output)
    return Evaluation(
        name=ScoreName.RESPONSE_COMPLETENESS,
        value=1.0 if output_text else 0.0,
        data_type=ScoreDataType.NUMERIC,
        comment="Trace has non-empty output."
        if output_text
        else "Trace output is empty.",
        metadata={"policy": ONLINE_EVAL_POLICY},
    )


def no_internal_agent_leakage_evaluator(
    *,
    input: Any,
    output: Any,
    expected_output: Any = None,
    metadata: dict | None = None,
) -> Evaluation:
    """Score whether user-facing output avoids internal fellowship names."""
    output_text = _text(output).casefold()
    leaked = [
        name
        for name in (
            "aragorn",
            "samwise",
            "elrond",
            "radagast",
            "bilbo",
            "faramir",
            "gandalf",
        )
        if name in output_text
    ]
    return Evaluation(
        name="no_internal_agent_leakage",
        value=not leaked,
        data_type=ScoreDataType.BOOLEAN,
        comment="No internal agent names leaked."
        if not leaked
        else f"Leaked: {', '.join(leaked)}",
        metadata={"policy": ONLINE_EVAL_POLICY, "leaked_names": leaked},
    )


def safe_empty_data_evaluator(
    *,
    input: Any,
    output: Any,
    expected_output: Any = None,
    metadata: dict | None = None,
) -> Evaluation:
    """Score the specific failure mode that triggered this work: empty user output."""
    output_text = _text(output).casefold()
    failed_empty = "no data available" in output_text or not output_text.strip()
    return Evaluation(
        name="no_empty_data_fallback",
        value=not failed_empty,
        data_type=ScoreDataType.BOOLEAN,
        comment="Output did not fall back to empty-data UI."
        if not failed_empty
        else "Output was empty or displayed no data available.",
        metadata={"policy": ONLINE_EVAL_POLICY},
    )


def already_scored(metadata: dict | None) -> bool:
    """Skip traces already scored by this evaluator set."""
    scores = set((metadata or {}).get("scores", []))
    expected = {
        ScoreName.RESPONSE_COMPLETENESS,
        "no_internal_agent_leakage",
        "no_empty_data_fallback",
    }
    return expected.issubset(scores)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run sampled online Langfuse evaluators"
    )
    parser.add_argument("--host", help="Langfuse host; defaults to LANGFUSE_HOST")
    parser.add_argument("--max-items", type=int, default=100)
    parser.add_argument("--fetch-batch-size", type=int, default=25)
    parser.add_argument("--max-concurrency", type=int, default=5)
    parser.add_argument(
        "--watch-interval-seconds",
        type=float,
        default=0.0,
        help="Run continuously, sleeping this many seconds between batches.",
    )
    parser.add_argument(
        "--tag",
        action="append",
        default=[],
        help="Additional trace tag filter; repeatable",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    filter_json = online_eval_filter(tags=args.tag)
    if args.dry_run:
        print(filter_json)
        return 0

    client = langfuse_client(args.host)
    while True:
        result = client.run_batched_evaluation(
            scope="traces",
            mapper=trace_mapper,
            filter=filter_json,
            fetch_batch_size=args.fetch_batch_size,
            fetch_trace_fields=DEFAULT_TRACE_FIELDS,
            max_items=args.max_items,
            max_concurrency=args.max_concurrency,
            evaluators=[
                required_output_evaluator,
                no_internal_agent_leakage_evaluator,
                safe_empty_data_evaluator,
            ],
            metadata={"policy": ONLINE_EVAL_POLICY, "mode": "online-sampled"},
            _additional_trace_tags=[ONLINE_EVALUATED_TAG],
            verbose=args.verbose,
        )
        print(
            "Online evaluation complete: "
            f"processed={result.total_items_processed}, "
            f"failed={result.total_items_failed}, "
            f"scores={result.total_scores_created}",
            flush=True,
        )
        if args.watch_interval_seconds <= 0:
            return 0
        time.sleep(args.watch_interval_seconds)
    return 0


def _existing_score_names(scores: list[Any]) -> list[str]:
    names: list[str] = []
    for score in scores:
        name = getattr(score, "name", "")
        if isinstance(name, str) and name:
            names.append(name)
    return names


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("final_answer", "answer", "output", "content"):
            if key in value:
                return _text(value[key])
    return str(value).strip()


if __name__ == "__main__":
    sys.exit(main())
