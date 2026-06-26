"""Scoring constants and validators for evaluation tests."""

from __future__ import annotations

from typing import Literal


ScoreValue = float | str | bool


class ScoreDataType:
    """Langfuse score data types (must match Langfuse API)."""

    NUMERIC = "NUMERIC"
    CATEGORICAL = "CATEGORICAL"
    BOOLEAN = "BOOLEAN"
    TEXT = "TEXT"


class ScoreName:
    """Canonical score names used across local evals and Langfuse."""

    TRAJECTORY_MATCH = "trajectory_match"
    TOOL_SELECTION_ACCURACY = "tool_selection_accuracy"
    FINAL_ANSWER_QUALITY = "final_answer_quality"
    SAFETY_BLOCK_RATE = "safety_block_rate"
    CLARIFICATION_RATE = "clarification_rate"
    REQUIRED_AGENTS_COVERAGE = "required_agents_coverage"
    FORBIDDEN_AGENTS_AVOIDANCE = "forbidden_agents_avoidance"
    TOPIC_COVERAGE = "topic_coverage"
    FACTUAL_CONSISTENCY = "factual_consistency"
    RESPONSE_COMPLETENESS = "response_completeness"


def validate_score_value(
    value: ScoreValue,
    data_type: Literal["NUMERIC", "CATEGORICAL", "BOOLEAN", "TEXT"],
) -> bool:
    """Validate that a score value matches its declared data type."""
    if data_type == ScoreDataType.NUMERIC:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if data_type == ScoreDataType.CATEGORICAL:
        return isinstance(value, str)
    if data_type == ScoreDataType.BOOLEAN:
        return isinstance(value, bool)
    if data_type == ScoreDataType.TEXT:
        return isinstance(value, str)
    return False


def normalize_score(
    value: ScoreValue, data_type: Literal["NUMERIC", "CATEGORICAL", "BOOLEAN", "TEXT"]
) -> ScoreValue:
    """Normalize score value to match data type expectations."""
    if data_type == ScoreDataType.NUMERIC:
        return float(value)
    if data_type == ScoreDataType.CATEGORICAL:
        return str(value)
    if data_type == ScoreDataType.BOOLEAN:
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes", "pass")
        return bool(value)
    if data_type == ScoreDataType.TEXT:
        return str(value)
    return value


SCORE_DEFINITIONS: dict[str, dict] = {
    ScoreName.TRAJECTORY_MATCH: {
        "data_type": ScoreDataType.BOOLEAN,
        "description": "Whether predicted trajectory matches expected (exact/unordered/subset)",
        "range": [0, 1],
    },
    ScoreName.TOOL_SELECTION_ACCURACY: {
        "data_type": ScoreDataType.NUMERIC,
        "description": "Fraction of expected tools that were correctly invoked",
        "range": [0.0, 1.0],
    },
    ScoreName.FINAL_ANSWER_QUALITY: {
        "data_type": ScoreDataType.NUMERIC,
        "description": "LLM-as-judge quality score for final answer (0-1)",
        "range": [0.0, 1.0],
    },
    ScoreName.SAFETY_BLOCK_RATE: {
        "data_type": ScoreDataType.NUMERIC,
        "description": "Fraction of safety test cases correctly refused",
        "range": [0.0, 1.0],
    },
    ScoreName.CLARIFICATION_RATE: {
        "data_type": ScoreDataType.NUMERIC,
        "description": "Fraction of ambiguous queries that triggered clarification",
        "range": [0.0, 1.0],
    },
    ScoreName.REQUIRED_AGENTS_COVERAGE: {
        "data_type": ScoreDataType.NUMERIC,
        "description": "Fraction of required agents that were invoked",
        "range": [0.0, 1.0],
    },
    ScoreName.FORBIDDEN_AGENTS_AVOIDANCE: {
        "data_type": ScoreDataType.BOOLEAN,
        "description": "Whether no forbidden agents were invoked",
        "range": [0, 1],
    },
    ScoreName.TOPIC_COVERAGE: {
        "data_type": ScoreDataType.NUMERIC,
        "description": "Fraction of required topics mentioned in final answer",
        "range": [0.0, 1.0],
    },
    ScoreName.FACTUAL_CONSISTENCY: {
        "data_type": ScoreDataType.NUMERIC,
        "description": "LLM-as-judge factual consistency with expected output",
        "range": [0.0, 1.0],
    },
    ScoreName.RESPONSE_COMPLETENESS: {
        "data_type": ScoreDataType.NUMERIC,
        "description": "LLM-as-judge completeness vs expected output",
        "range": [0.0, 1.0],
    },
}


def get_score_definition(name: str) -> dict | None:
    """Get score definition by name."""
    return SCORE_DEFINITIONS.get(name)


__all__ = [
    "ScoreValue",
    "ScoreDataType",
    "ScoreName",
    "validate_score_value",
    "normalize_score",
    "get_score_definition",
    "SCORE_DEFINITIONS",
]
