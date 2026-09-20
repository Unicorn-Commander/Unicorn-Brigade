# Executed by Codex gpt-5.6-luna (lane)
"""Shared CI-only skips for optional-service test harnesses."""

import pytest

from app.memory.graphiti_manager import GRAPHITI_AVAILABLE


def pytest_collection_modifyitems(config, items):
    """Skip Graphiti benchmarks when the optional CI dependency is absent."""
    if GRAPHITI_AVAILABLE:
        return

    skip_graphiti = pytest.mark.skip(
        reason="requires graphiti-core; CI intentionally omits the optional Graphiti dependency"
    )
    prefix = "tests/test_performance.py::TestMemoryOperations::"
    for item in items:
        if item.nodeid.startswith(prefix):
            item.add_marker(skip_graphiti)
