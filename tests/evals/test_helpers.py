"""Tests for eval helpers module."""

from __future__ import annotations

import pytest

from evals.helpers import (
    DATASETS_DIR,
    load_dataset,
    dataset_item_input,
    dataset_item_expected_output,
    dataset_item_metadata,
    list_datasets,
)


class TestListDatasets:
    """Test list_datasets function."""

    def test_returns_list_of_stems(self) -> None:
        """Returns dataset names without .jsonl extension."""
        datasets = list_datasets()
        assert isinstance(datasets, list)
        assert all(isinstance(d, str) for d in datasets)
        # Should have our 5 datasets
        expected = {
            "hotel-insights-core-v1",
            "hotel-insights-safety-v1",
            "hotel-insights-clarification-v1",
            "hotel-insights-weather-v1",
            "hotel-insights-mixed-v1",
        }
        assert expected.issubset(set(datasets))


class TestLoadDataset:
    """Test load_dataset function."""

    def test_loads_core_dataset(self) -> None:
        """Loads hotel-insights-core-v1 successfully."""
        items = load_dataset("hotel-insights-core-v1")
        assert isinstance(items, list)
        assert len(items) == 4
        assert all(isinstance(item, dict) for item in items)

    def test_loads_safety_dataset(self) -> None:
        """Loads hotel-insights-safety-v1 successfully."""
        items = load_dataset("hotel-insights-safety-v1")
        assert len(items) == 5

    def test_loads_clarification_dataset(self) -> None:
        """Loads hotel-insights-clarification-v1 successfully."""
        items = load_dataset("hotel-insights-clarification-v1")
        assert len(items) == 4

    def test_loads_weather_dataset(self) -> None:
        """Loads hotel-insights-weather-v1 successfully."""
        items = load_dataset("hotel-insights-weather-v1")
        assert len(items) == 4

    def test_loads_mixed_dataset(self) -> None:
        """Loads hotel-insights-mixed-v1 successfully."""
        items = load_dataset("hotel-insights-mixed-v1")
        assert len(items) == 4

    def test_raises_on_missing_dataset(self) -> None:
        """Raises FileNotFoundError for non-existent dataset."""
        with pytest.raises(FileNotFoundError):
            load_dataset("non-existent-dataset")

    def test_items_have_required_fields(self) -> None:
        """Each loaded item has id, input, expected_output, metadata."""
        items = load_dataset("hotel-insights-core-v1")
        for item in items:
            assert "id" in item
            assert "input" in item
            assert "expected_output" in item
            assert "metadata" in item


class TestDatasetItemExtractors:
    """Test dataset item field extractors."""

    def test_dataset_item_input(self) -> None:
        """Extracts input dict from item."""
        items = load_dataset("hotel-insights-core-v1")
        item = items[0]
        input_data = dataset_item_input(item)
        assert isinstance(input_data, dict)
        assert "query" in input_data
        assert "user_id" in input_data
        assert "thread_id" in input_data

    def test_dataset_item_expected_output(self) -> None:
        """Extracts expected_output dict from item."""
        items = load_dataset("hotel-insights-core-v1")
        item = items[0]
        expected = dataset_item_expected_output(item)
        assert isinstance(expected, dict)
        assert "required_agents" in expected
        assert "forbidden_agents" in expected

    def test_dataset_item_metadata(self) -> None:
        """Extracts metadata dict from item."""
        items = load_dataset("hotel-insights-core-v1")
        item = items[0]
        metadata = dataset_item_metadata(item)
        assert isinstance(metadata, dict)
        assert "scenario" in metadata
        assert "category" in metadata
        assert "version" in metadata


class TestDatasetsDir:
    """Test DATASETS_DIR constant."""

    def test_points_to_correct_path(self) -> None:
        """DATASETS_DIR points to evals/datasets."""
        assert DATASETS_DIR.name == "datasets"
        assert DATASETS_DIR.parent.name == "evals"


pytestmark = [
    pytest.mark.evals,
]
