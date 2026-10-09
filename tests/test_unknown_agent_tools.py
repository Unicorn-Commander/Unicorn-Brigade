"""Agent tool-list validation/reporting tests for BR-87063fd6."""

import copy

import pytest
from fastapi import HTTPException

from app.api.agent_routes import _reject_unknown_agent_tools
from app.llm.tool_resolver import UnknownToolNamesError, unknown_tool_names, validate_tool_names
from scripts.report_unknown_agent_tools import build_report


def test_unknown_tool_names_are_sorted_and_deduplicated():
    assert unknown_tool_names(["zz-never", "calculator", "aa-never", "zz-never"]) == [
        "aa-never",
        "zz-never",
    ]


def test_validate_tool_names_rejects_unknown_names_with_the_full_list():
    with pytest.raises(UnknownToolNamesError) as exc:
        validate_tool_names(["calculator", "missing-b", "missing-a"])
    assert exc.value.unknown_names == ["missing-a", "missing-b"]


def test_agent_save_validation_returns_422_with_unknown_names():
    with pytest.raises(HTTPException) as exc:
        _reject_unknown_agent_tools(["calculator", "missing-b", "missing-a"])
    assert exc.value.status_code == 422
    assert exc.value.detail["unknown_tools"] == ["missing-a", "missing-b"]


def test_unknown_agent_report_is_read_only_and_lists_records():
    agents = [
        {"id": "librarian", "name": "Librarian", "tools": ["knowledge.deep_read"]},
        {"id": "known", "name": "Known", "tools": ["calculator"]},
    ]
    before = copy.deepcopy(agents)

    report = build_report(agents, {"calculator"})

    assert report == [{
        "id": "librarian",
        "name": "Librarian",
        "unknown_tools": ["knowledge.deep_read"],
        "unknownTools": ["knowledge.deep_read"],
    }]
    assert agents == before
