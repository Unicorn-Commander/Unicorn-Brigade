"""Unit tests for the BR-4 Postgres advisory-lock leader election primitives.

These are the DEPENDENCY-LIGHT, no-DB assertions (key derivation + initial
instance state). The full two-instance "only one leader / follower no-op /
takeover on death" behaviour is proven against a REAL ephemeral Postgres by
scripts/prove_durable_state.py (run via scripts/run_durable_state_proof.sh),
since it is inherently a cross-connection database property.
"""

from __future__ import annotations

import pytest

from app.services.leader_election import PgAdvisoryLeaderLock, lock_key_from_name


def test_lock_key_is_stable():
    """Every replica must derive the SAME key for the same logical lock name."""
    assert lock_key_from_name("brigade_scheduler") == lock_key_from_name("brigade_scheduler")


def test_lock_key_is_signed_64bit():
    """pg advisory locks take a signed bigint — the key must fit in int64."""
    for name in ("brigade_scheduler", "x", "another-lock", "🦄"):
        k = lock_key_from_name(name)
        assert isinstance(k, int)
        assert -(2**63) <= k < 2**63


def test_distinct_names_distinct_keys():
    assert lock_key_from_name("brigade_scheduler") != lock_key_from_name("other_service")


def test_new_instance_holds_nothing():
    """A freshly constructed lock holds nothing until try_acquire succeeds."""
    lock = PgAdvisoryLeaderLock(
        "postgresql+asyncpg://unused:unused@localhost:1/none",
        lock_key_from_name("brigade_scheduler"),
    )
    assert lock.held is False
    assert lock.lock_key == lock_key_from_name("brigade_scheduler")


@pytest.mark.asyncio
async def test_try_acquire_is_safe_when_db_unreachable():
    """try_acquire must NEVER raise — an unreachable DB yields 'not leader' (the
    safe posture: if we cannot confirm leadership we must not fire jobs) rather
    than an exception that would crash scheduler startup."""
    lock = PgAdvisoryLeaderLock(
        "postgresql+asyncpg://unused:unused@127.0.0.1:1/none",
        lock_key_from_name("brigade_scheduler_unit"),
    )
    got = await lock.try_acquire()
    assert got is False
    assert lock.held is False
    await lock.release()  # also must not raise
