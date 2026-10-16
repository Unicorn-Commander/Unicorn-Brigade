"""Regression tests for aware UTC finance queries and business periods."""

from datetime import datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from app.agents.financial_analysis import (
    Budget,
    FinancialAnalysisAgent,
    ReportPeriod,
    Transaction,
)


NEW_YORK = ZoneInfo("America/New_York")


def _agent():
    return FinancialAnalysisAgent(llm_client=object())


def test_mixed_legacy_naive_and_aware_transactions_query_without_type_error():
    agent = _agent()
    legacy = Transaction(
        amount=Decimal("10.00"),
        description="legacy transaction",
        date=datetime(2026, 10, 16, 13, 30, tzinfo=timezone.utc),
    )
    # Simulate a row loaded from the legacy naive-UTC representation.
    legacy.date = datetime(2026, 10, 16, 13, 30)
    aware = Transaction(
        amount=Decimal("20.00"),
        description="aware transaction",
        date=datetime(2026, 10, 16, 14, 30, tzinfo=timezone.utc),
    )
    agent._transactions = {legacy.id: legacy, aware.id: aware}

    results = agent.list_transactions(
        start_date="2026-10-16",
        end_date="2026-10-16",
    )

    assert {transaction.description for transaction in results} == {
        "legacy transaction",
        "aware transaction",
    }
    assert all(transaction.date.tzinfo is not None for transaction in results)
    assert all(transaction.date.utcoffset() == timezone.utc.utcoffset(None) for transaction in results)

    local_wall_time_results = agent.list_transactions(
        start_date="2026-10-16T09:00",
        end_date="2026-10-16T10:00",
    )
    assert [transaction.description for transaction in local_wall_time_results] == [
        "legacy transaction"
    ]


@pytest.mark.asyncio
async def test_new_naive_transaction_input_is_business_time_before_utc_storage():
    result = await _agent().record_transaction(
        amount=10,
        description="year-end expense",
        category="office",
        date="2026-12-31T21:00",
    )

    assert result["transaction"]["date"] == "2027-01-01T02:00:00+00:00"


@pytest.mark.parametrize(
    ("period", "expected_start", "expected_end"),
    [
        (
            ReportPeriod.MONTHLY,
            datetime(2026, 12, 1, 5, tzinfo=timezone.utc),
            datetime(2027, 1, 1, 5, tzinfo=timezone.utc),
        ),
        (
            ReportPeriod.WEEKLY,
            datetime(2026, 12, 28, 5, tzinfo=timezone.utc),
            datetime(2027, 1, 4, 5, tzinfo=timezone.utc),
        ),
        (
            ReportPeriod.QUARTERLY,
            datetime(2026, 10, 1, 4, tzinfo=timezone.utc),
            datetime(2027, 1, 1, 5, tzinfo=timezone.utc),
        ),
        (
            ReportPeriod.YEARLY,
            datetime(2026, 1, 1, 5, tzinfo=timezone.utc),
            datetime(2027, 1, 1, 5, tzinfo=timezone.utc),
        ),
    ],
)
def test_finance_periods_use_new_york_calendar_boundaries(
    period, expected_start, expected_end
):
    agent = _agent()
    reference = datetime(2027, 1, 1, 2, tzinfo=timezone.utc)

    start, end = agent._get_period_dates(period, reference)

    assert (start, end) == (expected_start, expected_end)
    assert start.tzinfo is timezone.utc
    assert end.tzinfo is timezone.utc


@pytest.mark.asyncio
async def test_december_31_evening_transaction_counts_in_december_budget():
    agent = _agent()
    transaction = Transaction(
        amount=Decimal("100.00"),
        description="year-end expense",
        date=datetime(2026, 12, 31, 21, 0, tzinfo=NEW_YORK),
    )
    agent._transactions[transaction.id] = transaction
    budget = Budget(
        name="December budget",
        amount=Decimal("100.00"),
        period=ReportPeriod.MONTHLY,
        start_date=datetime(2027, 1, 1, 2, tzinfo=timezone.utc),
    )
    agent._budgets[budget.id] = budget

    period_start, period_end = agent._get_period_dates(
        ReportPeriod.MONTHLY, budget.start_date
    )
    status = await agent.check_budget_status()

    assert period_start <= transaction.date < period_end
    assert status["budgets"][0]["current_spend"] == 100.0
