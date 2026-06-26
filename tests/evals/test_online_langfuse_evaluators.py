"""Tests for sampled online Langfuse evaluator worker."""

from __future__ import annotations

import json
from types import SimpleNamespace

from evaluators.run_online_langfuse_evaluators import (
    APP_TRACE_TAG,
    ONLINE_EVAL_CANDIDATE_TAG,
    ONLINE_EVAL_POLICY,
    ONLINE_EVALUATED_TAG,
    no_internal_agent_leakage_evaluator,
    online_eval_filter,
    safe_empty_data_evaluator,
    trace_mapper,
)
from evaluators.sync_langfuse_llm_judge_evaluators import (
    EXAMPLE_EVALUATION_RULE,
    FINAL_ANSWER_QUALITY_EVALUATOR,
    evaluation_rule_payload,
    evaluator_payload,
)


def test_online_eval_filter_targets_sampled_app_traces() -> None:
    filters = json.loads(online_eval_filter(tags=["insights_query"]))

    assert {
        "type": "arrayOptions",
        "column": "tags",
        "operator": "all of",
        "value": [APP_TRACE_TAG, ONLINE_EVAL_CANDIDATE_TAG, "insights_query"],
    } in filters
    assert {
        "type": "boolean",
        "column": "metadata",
        "key": "eval_candidate",
        "operator": "=",
        "value": True,
    } in filters
    assert {
        "type": "stringObject",
        "column": "metadata",
        "key": "eval_policy",
        "operator": "=",
        "value": ONLINE_EVAL_POLICY,
    } in filters
    assert {
        "type": "arrayOptions",
        "column": "tags",
        "operator": "none of",
        "value": [ONLINE_EVALUATED_TAG],
    } in filters


def test_trace_mapper_preserves_trace_metadata_and_existing_scores() -> None:
    item = SimpleNamespace(
        id="trace-1",
        input={"query": "How is RevPAR?"},
        output={"final_answer": "RevPAR is improving."},
        metadata={"route": "insights_query"},
        tags=[APP_TRACE_TAG, ONLINE_EVAL_CANDIDATE_TAG],
        scores=[SimpleNamespace(name="response_completeness")],
        observations=[SimpleNamespace(name="gandalf"), SimpleNamespace(name="elrond")],
    )

    mapped = trace_mapper(item=item)
    metadata = mapped.metadata or {}

    assert mapped.input == {"query": "How is RevPAR?"}
    assert mapped.output == {"final_answer": "RevPAR is improving."}
    assert metadata["trace_id"] == "trace-1"
    assert metadata["scores"] == ["response_completeness"]
    assert metadata["observation_names"] == ["gandalf", "elrond"]


def test_online_evaluators_score_empty_data_and_agent_leakage() -> None:
    empty_score = safe_empty_data_evaluator(
        input=None, output="No data available", metadata={}
    )
    leakage_score = no_internal_agent_leakage_evaluator(
        input=None, output="Elrond found RevPAR issues.", metadata={}
    )

    assert empty_score.value is False
    assert leakage_score.value is False
    assert (leakage_score.metadata or {})["leaked_names"] == ["elrond"]


def test_llm_judge_evaluator_payload_creates_numeric_final_answer_quality() -> None:
    payload = evaluator_payload(FINAL_ANSWER_QUALITY_EVALUATOR)

    assert payload["type"] == "llm_as_judge"
    assert payload["name"] == "final_answer_quality"
    assert "{{input}}" in payload["prompt"]
    assert "{{output}}" in payload["prompt"]
    assert "{{metadata}}" in payload["prompt"]
    assert payload["outputDefinition"] == {
        "dataType": "NUMERIC",
        "score": {
            "description": "Numeric quality score from 0.0 to 1.0 for the final user-facing answer."
        },
        "reasoning": {
            "description": "Concise reason for the score, including grounding and clarity issues."
        },
    }


def test_llm_judge_rule_filters_on_tool_name_tag() -> None:
    payload = evaluation_rule_payload(EXAMPLE_EVALUATION_RULE)

    assert payload["target"] == "observation"
    assert payload["enabled"] is True
    assert payload["evaluator"] == {
        "name": "final_answer_quality",
        "scope": "project",
        "type": "llm_as_judge",
    }
    assert {
        "type": "arrayOptions",
        "column": "tags",
        "operator": "any of",
        "value": ["tool:call_agent"],
    } in payload["filter"]
    assert {"variable": "input", "source": "input"} in payload["mapping"]
    assert {"variable": "output", "source": "output"} in payload["mapping"]
    assert {"variable": "metadata", "source": "metadata"} in payload["mapping"]
