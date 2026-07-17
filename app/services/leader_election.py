"""Postgres advisory-lock leader election.

Used by the Brigade scheduler (app/services/scheduler.py) to guarantee that when
two or more replicas run, only ONE of them registers + fires cron jobs — the
others stand by and take over automatically if the leader dies. Kept in its own
dependency-light module (SQLAlchemy async only, no APScheduler / LLM imports) so
it is trivially unit-testable against an ephemeral Postgres.

Why an advisory lock (not a heartbeat row + TTL): ``pg_try_advisory_lock(key)``
is SESSION-scoped — the lock is held for exactly as long as the acquiring
CONNECTION (session) is alive, and Postgres releases it the instant that session
ends (process crash, network drop, container kill). So "take over on leader
death" is automatic and needs no TTL tuning or clock assumptions: a follower's
next ``try_acquire`` simply succeeds once the dead leader's connection is gone.

The lock is held on a DEDICATED, long-lived connection from a private pool_size=1
engine (AUTOCOMMIT, so there is no lingering open transaction) — never a pooled
request connection, whose lifetime we don't control. Two lock instances in the
SAME process each open their own connection = their own PG session, so the lock
correctly arbitrates between them too (which is exactly what the tests drive).
"""

from __future__ import annotations

import hashlib
import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

logger = logging.getLogger(__name__)


def lock_key_from_name(name: str) -> int:
    """Derive a stable signed 64-bit advisory-lock key from a name.

    ``pg_try_advisory_lock`` takes a ``bigint`` (signed 64-bit). Hash the name so
    every replica derives the SAME key for the same logical lock, independent of
    any config ordering."""
    digest = hashlib.sha256(name.encode("utf-8")).digest()[:8]
    return int.from_bytes(digest, "big", signed=True)


class PgAdvisoryLeaderLock:
    """A single, best-effort, session-scoped Postgres advisory lock.

    Not reentrant across processes (that's the whole point); within a process a
    repeated ``try_acquire`` while already holding is an idempotent no-op that
    returns True.
    """

    def __init__(
        self,
        dsn: str,
        lock_key: int,
        *,
        engine: Optional[AsyncEngine] = None,
    ) -> None:
        self._dsn = dsn
        self._lock_key = int(lock_key)
        # A private, tiny engine dedicated to holding the lock connection so we
        # never starve (or get recycled by) the app's shared pools. Injectable so
        # a test can share one engine/DB across two lock instances.
        self._own_engine = engine is None
        self._engine: Optional[AsyncEngine] = engine
        self._conn: Optional[AsyncConnection] = None
        self._held = False

    @property
    def lock_key(self) -> int:
        return self._lock_key

    @property
    def held(self) -> bool:
        """Whether this instance currently believes it holds the lock."""
        return self._held

    def _ensure_engine(self) -> AsyncEngine:
        if self._engine is None:
            # NullPool is load-bearing for correct takeover semantics: the lock is
            # session-scoped, so its lifetime must equal the PHYSICAL connection's.
            # With a real pool, closing the holder connection would only return it
            # (session still alive) and the lock would linger; with NullPool,
            # closing it (graceful release) OR the process dying (crash) actually
            # ends the session, so Postgres frees the lock and a standby takes over.
            # AUTOCOMMIT: no long-open transaction sits on the holder connection.
            self._engine = create_async_engine(
                self._dsn,
                isolation_level="AUTOCOMMIT",
                poolclass=NullPool,
            )
        return self._engine

    async def try_acquire(self) -> bool:
        """Attempt to become leader. Returns True iff this instance holds the lock.

        Idempotent while held. On ANY error (DB unreachable, etc.) returns False —
        the safe posture: if we cannot CONFIRM leadership we must not fire jobs, so
        a DB outage yields "nobody leads" rather than "everybody leads"
        (double-fire)."""
        if self._held and self._conn is not None:
            # Re-confirm the held connection is still alive; if it died, drop it
            # and fall through to a fresh acquire attempt.
            try:
                await self._conn.execute(text("SELECT 1"))
                return True
            except Exception:
                logger.warning("leader lock: held connection went stale; re-acquiring")
                await self._drop_conn()

        try:
            engine = self._ensure_engine()
            conn = await engine.connect()
            got = (
                await conn.execute(
                    text("SELECT pg_try_advisory_lock(:k)"), {"k": self._lock_key}
                )
            ).scalar()
            if got:
                self._conn = conn
                self._held = True
                return True
            # Someone else holds it — release this connection, stay a follower.
            await conn.close()
            self._held = False
            return False
        except Exception as exc:  # noqa: BLE001
            logger.warning("leader lock: try_acquire failed (staying follower): %s", exc)
            await self._drop_conn()
            self._held = False
            return False

    async def release(self) -> None:
        """Release the lock (if held) and tear down the dedicated connection.

        Called on graceful shutdown. A hard crash needs none of this — Postgres
        drops the session and its advisory lock automatically."""
        if self._conn is not None:
            try:
                await self._conn.execute(
                    text("SELECT pg_advisory_unlock(:k)"), {"k": self._lock_key}
                )
            except Exception as exc:  # noqa: BLE001
                logger.debug("leader lock: unlock failed (connection likely gone): %s", exc)
        await self._drop_conn()
        self._held = False
        if self._own_engine and self._engine is not None:
            try:
                await self._engine.dispose()
            except Exception:  # pragma: no cover - defensive
                pass
            self._engine = None

    async def _drop_conn(self) -> None:
        if self._conn is not None:
            try:
                await self._conn.close()
            except Exception:  # pragma: no cover - defensive
                pass
            self._conn = None
