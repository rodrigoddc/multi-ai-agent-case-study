"""Dataset shape validation tests for local JSONL datasets."""

from __future__ import annotations

import json

import pytest

from evals.helpers import DATASETS_DIR, list_datasets, load_dataset


REQUIRED_ITEM_KEYS = {"id", "input", "expected_output", "metadata"}
REQUIRED_INPUT_KEYS = {"query", "user_id", "thread_id"}
REQUIRED_EXPECTED_OUTPUT_KEYS = {
    "required_agents",
    "optional_agents",
    "forbidden_agents",
    "requires_user_input",
    "review_approved",
    "must_mention_topics",
}
REQUIRED_METADATA_KEYS = {"scenario", "category", "version"}


def _validate_item_structure(item: dict, dataset_name: str, line_num: int) -> list[str]:
    """Validate a single dataset item structure. Returns list of errors."""
    errors = []

    # Check top-level keys
    missing_keys = REQUIRED_ITEM_KEYS - set(item.keys())
    if missing_keys:
        errors.append(f"Missing keys: {missing_keys}")

    # Check input structure
    input_data = item.get("input", {})
    if not isinstance(input_data, dict):
        errors.append("input must be a dict")
    else:
        missing_input = REQUIRED_INPUT_KEYS - set(input_data.keys())
        if missing_input:
            errors.append(f"input missing keys: {missing_input}")

    # Check expected_output structure
    expected = item.get("expected_output", {})
    if not isinstance(expected, dict):
        errors.append("expected_output must be a dict")
    else:
        missing_expected = REQUIRED_EXPECTED_OUTPUT_KEYS - set(expected.keys())
        if missing_expected:
            errors.append(f"expected_output missing keys: {missing_expected}")

    # Check metadata structure
    metadata = item.get("metadata", {})
    if not isinstance(metadata, dict):
        errors.append("metadata must be a dict")
    else:
        missing_meta = REQUIRED_METADATA_KEYS - set(metadata.keys())
        if missing_meta:
            errors.append(f"metadata missing keys: {missing_meta}")

    # Check agents arrays are lists of strings
    for key in ("required_agents", "optional_agents", "forbidden_agents"):
        val = expected.get(key, [])
        if not isinstance(val, list):
            errors.append(f"expected_output.{key} must be a list")
        elif not all(isinstance(a, str) for a in val):
            errors.append(f"expected_output.{key} must contain strings")

    # Check must_mention_topics is list of strings
    topics = expected.get("must_mention_topics", [])
    if not isinstance(topics, list):
        errors.append("expected_output.must_mention_topics must be a list")
    elif not all(isinstance(t, str) for t in topics):
        errors.append("expected_output.must_mention_topics must contain strings")

    # Check boolean fields
    for key in ("requires_user_input", "review_approved"):
        val = expected.get(key)
        if not isinstance(val, bool):
            errors.append(f"expected_output.{key} must be boolean")

    # Check metadata values are strings
    for key in ("scenario", "category", "version"):
        val = metadata.get(key)
        if not isinstance(val, str):
            errors.append(f"metadata.{key} must be a string")

    return errors


@pytest.mark.evals
@pytest.mark.evals_dataset_shape
class TestDatasetShape:
    """Validate all local eval datasets have correct structure."""

    def test_datasets_dir_exists(self) -> None:
        """evals/datasets directory exists."""
        assert DATASETS_DIR.exists(), f"Datasets directory not found: {DATASETS_DIR}"

    def test_at_least_one_dataset(self) -> None:
        """At least one dataset file exists."""
        datasets = list_datasets()
        assert datasets, "No dataset files found in evals/datasets/"

    def test_all_datasets_loadable(self) -> None:
        """All datasets can be loaded without JSON errors."""
        for name in list_datasets():
            items = load_dataset(name)
            assert isinstance(items, list), f"Dataset {name} did not return a list"
            assert items, f"Dataset {name} is empty"

    def test_dataset_item_structure(self) -> None:
        """Each item in each dataset has required structure."""
        all_errors: list[str] = []

        for name in list_datasets():
            items = load_dataset(name)
            for i, item in enumerate(items):
                errors = _validate_item_structure(item, name, i + 1)
                for err in errors:
                    all_errors.append(f"{name}[{i}]: {err}")

        if all_errors:
            pytest.fail(
                "\n".join(all_errors[:50])
                + (
                    f"\n... and {len(all_errors) - 50} more"
                    if len(all_errors) > 50
                    else ""
                )
            )

    def test_dataset_item_id_format(self) -> None:
        """Item IDs follow expected format: dataset-name/scenario_version."""
        all_errors: list[str] = []

        for name in list_datasets():
            items = load_dataset(name)
            for i, item in enumerate(items):
                item_id = item.get("id", "")
                if not item_id:
                    all_errors.append(f"{name}[{i}]: Missing id")
                    continue
                # Should start with dataset name
                if not item_id.startswith(f"{name}/"):
                    all_errors.append(
                        f"{name}[{i}]: id '{item_id}' should start with '{name}/'"
                    )

        if all_errors:
            pytest.fail("\n".join(all_errors))

    def test_no_duplicate_ids(self) -> None:
        """No duplicate item IDs within or across datasets."""
        seen: dict[str, tuple[str, int]] = {}
        all_errors: list[str] = []

        for name in list_datasets():
            items = load_dataset(name)
            for i, item in enumerate(items):
                item_id = item.get("id", "")
                if item_id in seen:
                    other_name, other_idx = seen[item_id]
                    all_errors.append(
                        f"Duplicate id '{item_id}': {name}[{i}] and {other_name}[{other_idx}]"
                    )
                else:
                    seen[item_id] = (name, i)

        if all_errors:
            pytest.fail("\n".join(all_errors))

    def test_core_dataset_has_expected_scenarios(self) -> None:
        """Core dataset has expected baseline scenarios."""
        items = load_dataset("hotel-insights-core-v1")
        scenario_names = [item.get("metadata", {}).get("scenario") for item in items]

        expected = [
            "hotel_underperforming_sentiment",
            "hotel_top_revpar",
            "hotel_portfolio_occupancy",
            "capability_discovery",
        ]
        for exp in expected:
            assert exp in scenario_names, f"Missing expected scenario: {exp}"

    def test_safety_dataset_covers_injection_and_offtopic(self) -> None:
        """Safety dataset covers prompt injection and off-topic."""
        items = load_dataset("hotel-insights-safety-v1")
        scenario_names = [item.get("metadata", {}).get("scenario") for item in items]

        assert any("injection" in s for s in scenario_names), (
            "Missing injection scenario"
        )
        assert any("off_topic" in s for s in scenario_names), (
            "Missing off-topic scenario"
        )

    def test_clarification_dataset_requires_user_input(self) -> None:
        """Clarification dataset items have requires_user_input=true."""
        items = load_dataset("hotel-insights-clarification-v1")
        for item in items:
            expected = item.get("expected_output", {})
            assert expected.get("requires_user_input") is True, (
                f"Clarification scenario {item.get('metadata', {}).get('scenario')} should require user input"
            )
            assert expected.get("review_approved") is False, (
                "Clarification scenarios should not be review_approved"
            )

    def test_weather_dataset_requires_radagast(self) -> None:
        """Weather dataset items require radagast agent."""
        items = load_dataset("hotel-insights-weather-v1")
        for item in items:
            expected = item.get("expected_output", {})
            required = expected.get("required_agents", [])
            assert "radagast" in required, (
                f"Weather scenario {item.get('metadata', {}).get('scenario')} missing radagast"
            )


@pytest.mark.evals
@pytest.mark.evals_dataset_shape
class TestDatasetJSONLSyntax:
    """Validate JSONL syntax of dataset files."""

    def test_all_files_valid_jsonl(self) -> None:
        """Each line in each .jsonl file parses as valid JSON."""
        for path in DATASETS_DIR.glob("*.jsonl"):
            with path.open("r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        json.loads(line)
                    except json.JSONDecodeError as e:
                        pytest.fail(f"{path.name}:{line_num}: JSON decode error: {e}")

    def test_no_trailing_whitespace(self) -> None:
        """No trailing whitespace in JSONL files."""
        for path in DATASETS_DIR.glob("*.jsonl"):
            with path.open("r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    if line.rstrip("\n") != line.rstrip():
                        pytest.fail(f"{path.name}:{line_num}: trailing whitespace")
