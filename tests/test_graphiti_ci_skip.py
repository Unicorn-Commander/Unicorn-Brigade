# Executed by Grok (headless lane)
"""Prove the Graphiti CI skip keys off package absence, not app ImportError."""

from __future__ import annotations

import importlib.util
from importlib.machinery import ModuleSpec
from pathlib import Path

import pytest

import conftest as root_conftest

_MEMORY_NODE = (
    "tests/test_performance.py::TestMemoryOperations::test_memory_store_mock"
)
_OTHER_NODE = "tests/test_api.py::test_health_endpoint"
_CONFTEST = Path(__file__).resolve().parents[1] / "conftest.py"


class _FakeItem:
    def __init__(self, nodeid: str) -> None:
        self.nodeid = nodeid
        self.markers: list[pytest.MarkDecorator] = []

    def add_marker(self, marker: pytest.MarkDecorator) -> None:
        self.markers.append(marker)


def test_root_conftest_does_not_import_app_graphiti_manager() -> None:
    source = _CONFTEST.read_text()
    assert "app.memory.graphiti_manager" not in source
    assert "GRAPHITI_AVAILABLE" not in source
    assert 'find_spec("graphiti_core")' in source


def test_absent_graphiti_core_skips_only_memory_benchmarks(monkeypatch) -> None:
    real_find_spec = importlib.util.find_spec

    def _find_spec(name: str, package: str | None = None):
        if name == "graphiti_core":
            return None
        return real_find_spec(name, package)

    monkeypatch.setattr(importlib.util, "find_spec", _find_spec)
    items = [_FakeItem(_MEMORY_NODE), _FakeItem(_OTHER_NODE)]
    root_conftest.pytest_collection_modifyitems(config=None, items=items)
    assert items[0].markers, "absent graphiti_core must skip memory benchmarks"
    assert items[1].markers == []


def test_installed_graphiti_core_does_not_skip_memory_benchmarks(monkeypatch) -> None:
    """Installed-but-broken still has a spec; keep those failures visible."""
    spec = ModuleSpec("graphiti_core", loader=None)
    real_find_spec = importlib.util.find_spec

    def _find_spec(name: str, package: str | None = None):
        if name == "graphiti_core":
            return spec
        return real_find_spec(name, package)

    monkeypatch.setattr(importlib.util, "find_spec", _find_spec)
    items = [_FakeItem(_MEMORY_NODE)]
    root_conftest.pytest_collection_modifyitems(config=None, items=items)
    assert items[0].markers == []
