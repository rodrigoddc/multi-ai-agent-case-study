"""Pytest configuration and fixtures for evals tests."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import pytest


@pytest.fixture(scope="session")
def eval_datasets_dir() -> Path:
    """Return path to evals/datasets directory."""
    return Path(__file__).resolve().parents[1] / "evals" / "datasets"


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest with custom markers for evals."""
    config.addinivalue_line("markers", "evals: marks tests as evaluation tests")
    config.addinivalue_line(
        "markers", "evals_dataset_shape: marks dataset shape validation tests"
    )
    config.addinivalue_line(
        "markers", "evals_trajectory: marks trajectory projection tests"
    )
    config.addinivalue_line(
        "markers", "evals_local_langfuse: marks tests requiring local Langfuse"
    )


__all__ = ["eval_datasets_dir"]
