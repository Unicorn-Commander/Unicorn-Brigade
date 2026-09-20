# Executed by Grok (headless lane)
"""Shared CI-only skips for optional-service test harnesses."""

from __future__ import annotations

import importlib.util

import pytest

_GRAPHITI_MEMORY_PREFIX = "tests/test_performance.py::TestMemoryOperations::"


def graphiti_core_absent() -> bool:
    """True only when the top-level graphiti_core package is not installed.

    Uses find_spec so an installed-but-broken graphiti-core (ImportError from a
    driver, client, or embedder) stays visible to the tests that import it.
    """
    return importlib.util.find_spec("graphiti_core") is None


def pytest_collection_modifyitems(config, items):
    """Skip Graphiti benchmarks when the optional CI dependency is absent."""
    if not graphiti_core_absent():
        return

    skip_graphiti = pytest.mark.skip(
        reason="requires graphiti-core; CI intentionally omits the optional Graphiti dependency"
    )
    for item in items:
        if item.nodeid.startswith(_GRAPHITI_MEMORY_PREFIX):
            item.add_marker(skip_graphiti)
