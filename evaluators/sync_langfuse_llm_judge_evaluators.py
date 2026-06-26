#!/usr/bin/env python
"""Sync Langfuse LLM-as-judge evaluators and example rules.

This provisions at least one real Langfuse UI evaluator through the unstable
public evaluator API. Score configs alone are not enough for the Evaluators page.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from evals.scoring import ScoreName

DEFAULT_TIMEOUT_SECONDS = 30.0
TOOL_TAG_PREFIX = "tool:"


@dataclass(frozen=True, slots=True)
class LlmJudgeEvaluatorDefinition:
    """Langfuse LLM-as-judge evaluator definition."""

    name: str
    prompt: str
    score_description: str
    reasoning_description: str
    model_provider: str | None = None
    model: str | None = None


@dataclass(frozen=True, slots=True)
class LlmJudgeRuleDefinition:
    """Langfuse LLM-as-judge evaluation rule definition."""

    name: str
    evaluator_name: str
    tool_name: str
    enabled: bool = True
    sampling: float = 1.0


FINAL_ANSWER_QUALITY_EVALUATOR = LlmJudgeEvaluatorDefinition(
    name=ScoreName.FINAL_ANSWER_QUALITY,
    prompt=(
        "You are evaluating a hotel analytics assistant response.\n\n"
        "User input:\n{{input}}\n\n"
        "Assistant output:\n{{output}}\n\n"
        "Trace or observation metadata:\n{{metadata}}\n\n"
        "Score from 0.0 to 1.0 using this rubric:\n"
        "- 1.0: directly answers the user, is grounded in provided hotel/weather evidence, "
        "does not expose internal agent names, and states assumptions clearly.\n"
        "- 0.5: partially useful but misses important context, has weak grounding, or is unclear.\n"
        "- 0.0: empty, unsafe, off-topic, fabricated, or leaks internal implementation details.\n"
        "Return only the structured score and concise reasoning."
    ),
    score_description="Numeric quality score from 0.0 to 1.0 for the final user-facing answer.",
    reasoning_description="Concise reason for the score, including grounding and clarity issues.",
)

EXAMPLE_EVALUATION_RULE = LlmJudgeRuleDefinition(
    name="final_answer_quality_on_call_agent_tool",
    evaluator_name=ScoreName.FINAL_ANSWER_QUALITY,
    tool_name="call_agent",
)


def evaluator_payload(definition: LlmJudgeEvaluatorDefinition) -> dict[str, Any]:
    """Build the unstable evaluator API payload."""
    payload: dict[str, Any] = {
        "type": "llm_as_judge",
        "name": definition.name,
        "prompt": definition.prompt,
        "outputDefinition": {
            "dataType": "NUMERIC",
            "score": {"description": definition.score_description},
            "reasoning": {"description": definition.reasoning_description},
        },
    }
    if definition.model_provider and definition.model:
        payload["modelConfig"] = {
            "provider": definition.model_provider,
            "model": definition.model,
        }
    return payload


def evaluation_rule_payload(definition: LlmJudgeRuleDefinition) -> dict[str, Any]:
    """Build an example observation-level evaluation rule payload."""
    tool_tag = f"{TOOL_TAG_PREFIX}{definition.tool_name}"
    return {
        "name": definition.name,
        "evaluator": {
            "name": definition.evaluator_name,
            "scope": "project",
            "type": "llm_as_judge",
        },
        "target": "observation",
        "enabled": definition.enabled,
        "sampling": definition.sampling,
        "filter": [
            {
                "type": "arrayOptions",
                "column": "tags",
                "operator": "any of",
                "value": [tool_tag],
            }
        ],
        "mapping": [
            {"variable": "input", "source": "input"},
            {"variable": "output", "source": "output"},
            {"variable": "metadata", "source": "metadata"},
        ],
    }


def langfuse_api_client(host: str | None = None) -> httpx.Client:
    """Create an authenticated Langfuse public API client."""
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    if not public_key or not secret_key:
        raise RuntimeError("LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY must be set")
    base_url = (host or os.getenv("LANGFUSE_HOST") or "http://localhost:3000").rstrip(
        "/"
    )
    return httpx.Client(
        base_url=base_url,
        auth=(public_key, secret_key),
        timeout=DEFAULT_TIMEOUT_SECONDS,
    )


def sync_llm_judge_evaluator(
    client: httpx.Client, definition: LlmJudgeEvaluatorDefinition
) -> dict[str, Any]:
    """Create a new evaluator version in Langfuse."""
    response = client.post(
        "/api/public/unstable/evaluators",
        json=evaluator_payload(definition),
    )
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, dict) else {}


def sync_evaluation_rule(
    client: httpx.Client, definition: LlmJudgeRuleDefinition
) -> dict[str, Any]:
    """Create an example evaluation rule in Langfuse."""
    response = client.post(
        "/api/public/unstable/evaluation-rules",
        json=evaluation_rule_payload(definition),
    )
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, dict) else {}


def build_final_answer_quality_evaluator() -> LlmJudgeEvaluatorDefinition:
    """Return the example evaluator with optional explicit model config from env."""
    provider = os.getenv("LANGFUSE_EVALUATOR_PROVIDER")
    model = os.getenv("LANGFUSE_EVALUATOR_MODEL")
    if provider and model:
        return LlmJudgeEvaluatorDefinition(
            name=FINAL_ANSWER_QUALITY_EVALUATOR.name,
            prompt=FINAL_ANSWER_QUALITY_EVALUATOR.prompt,
            score_description=FINAL_ANSWER_QUALITY_EVALUATOR.score_description,
            reasoning_description=FINAL_ANSWER_QUALITY_EVALUATOR.reasoning_description,
            model_provider=provider,
            model=model,
        )
    return FINAL_ANSWER_QUALITY_EVALUATOR


def main() -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Sync Langfuse LLM-as-judge evaluators and example rules"
    )
    parser.add_argument("--host", help="Langfuse host; defaults to LANGFUSE_HOST")
    parser.add_argument("--skip-rule", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    evaluator = build_final_answer_quality_evaluator()
    rule = EXAMPLE_EVALUATION_RULE
    if args.dry_run:
        print(f"Would create evaluator: {evaluator.name}")
        if not args.skip_rule:
            print(f"Would create evaluation rule: {rule.name}")
        return 0

    with langfuse_api_client(args.host) as client:
        created_evaluator = sync_llm_judge_evaluator(client, evaluator)
        print(
            "LLM-as-judge evaluator synced: "
            f"name={created_evaluator.get('name', evaluator.name)} "
            f"id={created_evaluator.get('id', 'unknown')}"
        )
        if args.skip_rule:
            return 0
        created_rule = sync_evaluation_rule(client, rule)
        print(
            "Evaluation rule synced: "
            f"name={created_rule.get('name', rule.name)} "
            f"id={created_rule.get('id', 'unknown')} "
            f"tool_tag={TOOL_TAG_PREFIX}{rule.tool_name}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
