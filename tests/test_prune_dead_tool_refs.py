"""Pure diff tests for the dead agent-tool reference utility."""

from __future__ import annotations

import pytest

from scripts.prune_dead_tool_refs import compute_tool_diff


@pytest.fixture
def sibling_agent_records():
    return [
        {
            "id": "accounting-ops-cfo",
            "tools": [
                "flag_for_cpa_review",
                "get_balance_sheet",
                "get_cash_position",
                "get_p_and_l",
                "get_runway",
                "get_trial_balance",
                "list_pending_approvals",
                "list_recent_transactions",
                "memory",
            ],
        },
        {
            "id": "customer-ops-lead",
            "tools": [
                "draft_followup",
                "get_customer_360",
                "list_customer_invoices",
                "list_customers",
                "pipeline_board",
                "record_customer_engagement",
                "triage_customer",
                "memory",
            ],
        },
        {
            "id": "librarian",
            "tools": [
                "knowledge.deep_read",
                "knowledge.doc_history",
                "knowledge.find_file",
                "knowledge.get_doc",
                "knowledge.ground",
                "knowledge.list_docs",
                "knowledge.list_sources",
                "knowledge.record_metric",
                "knowledge.search",
                "knowledge.upsert_doc",
                "memory",
            ],
        },
    ]


def test_compute_tool_diff_removes_only_dead_names(sibling_agent_records):
    known = {"memory"}

    for agent in sibling_agent_records:
        original = {"id": agent["id"], "tools": list(agent["tools"])}
        diff = compute_tool_diff(agent, known)

        assert diff.before == original["tools"]
        assert diff.after == ["memory"]
        assert all(name != "memory" for name in diff.missing)
        assert agent == original


def test_compute_tool_diff_preserves_order_and_known_duplicates():
    diff = compute_tool_diff(
        {"tools": ["memory", "dead", "datetime", "memory"]},
        {"memory", "datetime"},
    )

    assert diff.missing == ["dead"]
    assert diff.after == ["memory", "datetime", "memory"]
