"""Tests for eval scoring module."""

from __future__ import annotations

import pytest

from evals.scoring import (
    ScoreDataType,
    ScoreName,
    SCORE_DEFINITIONS,
    get_score_definition,
    normalize_score,
    validate_score_value,
)


class TestScoreDataType:
    """Test ScoreDataType constants."""

    def test_constants_exist(self) -> None:
        """All score data type constants are defined."""
        assert ScoreDataType.NUMERIC == "NUMERIC"
        assert ScoreDataType.CATEGORICAL == "CATEGORICAL"
        assert ScoreDataType.BOOLEAN == "BOOLEAN"
        assert ScoreDataType.TEXT == "TEXT"


class TestScoreName:
    """Test ScoreName canonical score names."""

    def test_all_scores_defined(self) -> None:
        """All expected score names exist."""
        expected = {
            "trajectory_match",
            "tool_selection_accuracy",
            "final_answer_quality",
            "safety_block_rate",
            "clarification_rate",
            "required_agents_coverage",
            "forbidden_agents_avoidance",
            "topic_coverage",
            "factual_consistency",
            "response_completeness",
        }
        actual = {
            getattr(ScoreName, attr)
            for attr in dir(ScoreName)
            if not attr.startswith("_")
        }
        assert expected.issubset(actual)


class TestValidateScoreValue:
    """Test validate_score_value function."""

    def test_numeric_valid(self) -> None:
        """Accepts int and float for NUMERIC."""
        assert validate_score_value(0.5, ScoreDataType.NUMERIC) is True
        assert validate_score_value(1, ScoreDataType.NUMERIC) is True
        assert validate_score_value(0, ScoreDataType.NUMERIC) is True

    def test_numeric_rejects_bool(self) -> None:
        """Rejects bool for NUMERIC (bool is subclass of int)."""
        assert validate_score_value(True, ScoreDataType.NUMERIC) is False
        assert validate_score_value(False, ScoreDataType.NUMERIC) is False

    def test_numeric_rejects_string(self) -> None:
        """Rejects string for NUMERIC."""
        assert validate_score_value("0.5", ScoreDataType.NUMERIC) is False

    def test_categorical_valid_string(self) -> None:
        """Accepts string for CATEGORICAL."""
        assert validate_score_value("excellent", ScoreDataType.CATEGORICAL) is True
        assert validate_score_value("pass", ScoreDataType.CATEGORICAL) is True

    def test_categorical_rejects_numeric(self) -> None:
        """Rejects numeric for CATEGORICAL."""
        assert validate_score_value(0.5, ScoreDataType.CATEGORICAL) is False

    def test_boolean_valid(self) -> None:
        """Accepts bool for BOOLEAN."""
        assert validate_score_value(True, ScoreDataType.BOOLEAN) is True
        assert validate_score_value(False, ScoreDataType.BOOLEAN) is True

    def test_boolean_rejects_string(self) -> None:
        """Rejects string for BOOLEAN."""
        assert validate_score_value("true", ScoreDataType.BOOLEAN) is False

    def test_boolean_rejects_numeric(self) -> None:
        """Rejects numeric for BOOLEAN."""
        assert validate_score_value(1, ScoreDataType.BOOLEAN) is False

    def test_text_valid_string(self) -> None:
        """Accepts string for TEXT."""
        assert validate_score_value("some text", ScoreDataType.TEXT) is True

    def test_text_rejects_numeric(self) -> None:
        """Rejects numeric for TEXT."""
        assert validate_score_value(123, ScoreDataType.TEXT) is False


class TestNormalizeScore:
    """Test normalize_score function."""

    def test_numeric_converts_to_float(self) -> None:
        """Converts int to float for NUMERIC."""
        assert normalize_score(1, ScoreDataType.NUMERIC) == 1.0
        assert normalize_score(0.75, ScoreDataType.NUMERIC) == 0.75

    def test_categorical_ensures_string(self) -> None:
        """Ensures string for CATEGORICAL."""
        assert normalize_score("pass", ScoreDataType.CATEGORICAL) == "pass"
        # Convert non-string to string
        assert normalize_score(123, ScoreDataType.CATEGORICAL) == "123"

    def test_boolean_normalizes_valid(self) -> None:
        """Normalizes boolean values."""
        assert normalize_score(True, ScoreDataType.BOOLEAN) is True
        assert normalize_score(False, ScoreDataType.BOOLEAN) is False

    def test_boolean_converts_truthy_strings(self) -> None:
        """Converts truthy strings to True for BOOLEAN."""
        assert normalize_score("true", ScoreDataType.BOOLEAN) is True
        assert normalize_score("True", ScoreDataType.BOOLEAN) is True
        assert normalize_score("1", ScoreDataType.BOOLEAN) is True
        assert normalize_score("yes", ScoreDataType.BOOLEAN) is True
        assert normalize_score("pass", ScoreDataType.BOOLEAN) is True

    def test_boolean_converts_falsy_strings(self) -> None:
        """Converts falsy strings to False for BOOLEAN."""
        assert normalize_score("false", ScoreDataType.BOOLEAN) is False
        assert normalize_score("0", ScoreDataType.BOOLEAN) is False
        assert normalize_score("no", ScoreDataType.BOOLEAN) is False
        assert normalize_score("fail", ScoreDataType.BOOLEAN) is False

    def test_text_ensures_string(self) -> None:
        """Ensures string for TEXT."""
        assert normalize_score("some text", ScoreDataType.TEXT) == "some text"
        assert normalize_score(123, ScoreDataType.TEXT) == "123"


class TestScoreDefinitions:
    """Test SCORE_DEFINITIONS registry."""

    def test_all_score_names_have_definition(self) -> None:
        """Each ScoreName has a definition in SCORE_DEFINITIONS."""
        score_names = [
            getattr(ScoreName, attr)
            for attr in dir(ScoreName)
            if not attr.startswith("_")
        ]
        for name in score_names:
            assert name in SCORE_DEFINITIONS, f"Missing definition for {name}"

    def test_definition_has_required_fields(self) -> None:
        """Each definition has data_type, description, range."""
        for name, defn in SCORE_DEFINITIONS.items():
            assert "data_type" in defn, f"{name}: missing data_type"
            assert "description" in defn, f"{name}: missing description"
            assert "range" in defn, f"{name}: missing range"
            assert defn["data_type"] in (
                ScoreDataType.NUMERIC,
                ScoreDataType.CATEGORICAL,
                ScoreDataType.BOOLEAN,
                ScoreDataType.TEXT,
            ), f"{name}: invalid data_type"

    def test_get_score_definition(self) -> None:
        """get_score_definition returns correct definition."""
        defn = get_score_definition(ScoreName.TRAJECTORY_MATCH)
        assert defn is not None
        assert defn["data_type"] == ScoreDataType.BOOLEAN

        defn = get_score_definition(ScoreName.REQUIRED_AGENTS_COVERAGE)
        assert defn is not None
        assert defn["data_type"] == ScoreDataType.NUMERIC

    def test_get_score_definition_unknown_returns_none(self) -> None:
        """Unknown score name returns None."""
        assert get_score_definition("unknown_score") is None


pytestmark = [
    pytest.mark.evals,
]
