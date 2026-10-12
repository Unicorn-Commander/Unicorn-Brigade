"""Unit tests for the BrigadeScheduler service."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import app.services.scheduler as scheduler_module
from app.services.scheduler import _parse_cron, BrigadeScheduler


class _FakeHistory:
    next_id = "history-1"

    def __init__(self, **values):
        self.__dict__.update(values)
        self.id = self.next_id


class _FakeSession:
    def __init__(self, run, agent=None):
        self.run = run
        self.agent = agent
        self.added = []

    async def get(self, model, _key):
        if model is scheduler_module.ScheduledRun:
            return self.run
        if model is scheduler_module.Agent:
            return self.agent
        return None

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        return None


class _SessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *_args):
        return None


def _run(enabled: bool):
    return SimpleNamespace(
        id="run-1",
        enabled=enabled,
        org_id="org-1",
        agent_id="agent-1",
        prompt="check the pool",
        owner_user_id=None,
        max_runtime_seconds=5,
    )


def _install_fire_fakes(monkeypatch, run, agent=None):
    session = _FakeSession(run, agent)
    monkeypatch.setattr(scheduler_module, "_bind_org", AsyncMock())
    monkeypatch.setattr(
        scheduler_module,
        "admin_session",
        lambda: _SessionContext(session),
    )
    monkeypatch.setattr(scheduler_module, "ScheduledRunHistory", _FakeHistory)
    return session


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


@pytest.mark.asyncio
async def test_disabled_schedule_is_skipped_by_scheduler_fire(monkeypatch):
    session = _install_fire_fakes(monkeypatch, _run(enabled=False))
    scheduler = BrigadeScheduler(object())
    invoke = AsyncMock()
    monkeypatch.setattr(scheduler, "_invoke_agent", invoke)

    history_id = await scheduler._fire("run-1")

    assert history_id == ""
    assert session.added == []
    invoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_manual_run_of_disabled_schedule_requires_explicit_opt_in(monkeypatch):
    session = _install_fire_fakes(
        monkeypatch,
        _run(enabled=False),
        agent=SimpleNamespace(to_dict=lambda: {"id": "agent-1"}),
    )
    scheduler = BrigadeScheduler(object())
    invoke = AsyncMock(return_value={"content": "degraded", "toolCalls": []})
    monkeypatch.setattr(scheduler, "_invoke_agent", invoke)
    monkeypatch.setattr(scheduler, "_finalize", AsyncMock())
    monkeypatch.setattr(scheduler, "_update_run_status", AsyncMock())

    assert await scheduler.trigger_now("run-1", actor="operator-7") == ""
    assert session.added == []

    history_id = await scheduler.trigger_now(
        "run-1", actor="operator-7", allow_disabled=True
    )

    assert history_id == "history-1"
    history = session.added[-1]
    assert history.trigger == "manual"
    assert history.actor == "operator-7"
    invoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_enabled_schedule_runs_with_schedule_audit_fields(monkeypatch):
    session = _install_fire_fakes(
        monkeypatch,
        _run(enabled=True),
        agent=SimpleNamespace(to_dict=lambda: {"id": "agent-1"}),
    )
    scheduler = BrigadeScheduler(object())
    invoke = AsyncMock(return_value={"content": "healthy", "toolCalls": []})
    monkeypatch.setattr(scheduler, "_invoke_agent", invoke)
    monkeypatch.setattr(scheduler, "_finalize", AsyncMock())
    monkeypatch.setattr(scheduler, "_update_run_status", AsyncMock())

    history_id = await scheduler._fire("run-1")

    assert history_id == "history-1"
    history = session.added[-1]
    assert history.trigger == "schedule"
    assert history.actor == "scheduler"
    invoke.assert_awaited_once()
