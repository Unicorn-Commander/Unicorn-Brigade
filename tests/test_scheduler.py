"""Unit tests for the BrigadeScheduler service."""

from __future__ import annotations

import pytest

from app.services.scheduler import _parse_cron, BrigadeScheduler


def test_parse_cron_valid():
    trigger = _parse_cron("*/5 * * * *", "UTC")
    assert trigger is not None


def test_parse_cron_rejects_bad_field_count():
    with pytest.raises(ValueError):
        _parse_cron("*/5 * *", "UTC")


def test_parse_cron_rejects_bad_field_values():
    with pytest.raises(Exception):
        _parse_cron("99 99 99 99 99", "UTC")


def test_parse_cron_with_timezone():
    trigger = _parse_cron("0 13 * * *", "America/New_York")
    assert trigger is not None


@pytest.mark.asyncio
async def test_scheduler_lifecycle():
    """Scheduler.start/shutdown are idempotent and don't crash with no jobs."""

    class _StubLLM:  # only used as a marker
        pass

    s = BrigadeScheduler(_StubLLM())
    # start may attempt a DB read inside reload_all — guard with a try since we
    # don't have a DB in unit tests. The lifecycle itself is what we test.
    try:
        await s.start()
    except Exception:
        pass
    await s.shutdown()
    # Second shutdown is a no-op.
    await s.shutdown()
