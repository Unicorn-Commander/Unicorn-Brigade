"""
Brigade Scheduler — persistent cron-style scheduling of agent runs.

Design notes
------------
Brigade is the source of truth: every schedule lives in the
``scheduled_runs`` table, with execution history in
``scheduled_run_history``. APScheduler is just the cron engine — on
startup we read all enabled rows and (re)register CronTriggers in an
in-memory AsyncIOScheduler. This avoids pickling jobs into APScheduler's
SQLAlchemyJobStore (which is sync-only and a poor fit for our async
SQLAlchemy + asyncpg stack), and makes the source of truth easy to
inspect and edit directly via SQL.

When a job fires, we open a fresh AsyncSession, look up the agent +
ScheduledRun, build a chat message stack the same way
``POST /api/v1/agents/{id}/chat`` does, and call ``llm_client``
directly. The configured ``owner_user_id`` is forwarded as ``user_id``
so per-user JWT propagation (project-ops MCP, etc.) sees the right
identity.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select, text

# BR-1.2/BR-1.3: the scheduler is a trusted CROSS-TENANT dispatcher — it enumerates
# and fires jobs across EVERY org. It therefore uses the admin/owner-bound session
# factory (RLS-exempt), because the runtime app-role session with no bound
# ``app.current_org_id`` and FORCE ROW LEVEL SECURITY would hide every row and the
# scheduler would load zero jobs. It still binds the per-job org GUC (``_bind_org``)
# before writing history so each write is attributed to the correct org and the
# same set_config path is exercised. Requires the admin role to be superuser or
# BYPASSRLS (it is the owner/migration role).
from app.db.database import admin_session, MIGRATION_DATABASE_URL
from app.db.models import Agent, ScheduledRun, ScheduledRunHistory
from app.llm.tool_resolver import get_tools_for_agent
from app.llm.ops_center_client import DEFAULT_MODEL
from app.integrations.metering import meter_usage
from app.observability.metrics import scheduled_run_total
from app.services.leader_election import PgAdvisoryLeaderLock, lock_key_from_name

logger = logging.getLogger(__name__)

RUN_TRIGGER_SCHEDULE = "schedule"
RUN_TRIGGER_MANUAL = "manual"
RUN_TRIGGER_IMPORT = "import"
RUN_TRIGGERS = frozenset(
    {RUN_TRIGGER_SCHEDULE, RUN_TRIGGER_MANUAL, RUN_TRIGGER_IMPORT}
)
SCHEDULED_RUN_ACTOR = "scheduler"

# BR-4: deploy-wide default cap on a scheduled run's wall-clock time, used when a
# ScheduledRun row does not set its own ``max_runtime_seconds``. Configurable via
# env so operators can tune without a code change. The per-run value still wins.
DEFAULT_SCHEDULER_MAX_RUNTIME_SECONDS: int = int(
    os.getenv("SCHEDULER_MAX_RUNTIME_SECONDS", "300") or 300
)

# BR-4 leader election. With >1 replica the in-process APScheduler would
# double-fire, so only the replica that holds the Postgres advisory lock
# registers + fires jobs. Followers keep an EMPTY scheduler running (so /readyz
# stays green) and take over automatically if the leader dies (its session lock
# is released by Postgres). All knobs env-tunable; defaults suit single- and
# multi-replica alike (a lone replica just wins the lock and behaves as before).
SCHEDULER_LEADER_LOCK_NAME: str = os.getenv("SCHEDULER_LEADER_LOCK_NAME", "brigade_scheduler")
SCHEDULER_LEADER_POLL_SECONDS: int = int(os.getenv("SCHEDULER_LEADER_POLL_SECONDS", "15") or 15)
SCHEDULER_LEADER_RELOAD_SECONDS: int = int(os.getenv("SCHEDULER_LEADER_RELOAD_SECONDS", "60") or 60)


async def _bind_org(session, org_id) -> None:
    await session.execute(
        text("SELECT set_config('app.current_org_id', :org_id, false)"),
        {"org_id": str(org_id)},
    )
    # M4: stamp the per-task orchestration context so any events emitted while this
    # scheduled job runs are attributed to its org for the SSE org filter.
    from app.orchestration.event_bus import current_org_id_var
    current_org_id_var.set(str(org_id))


async def notify_scheduled_run_failure(
    run_id: str,
    status: str,
    error: str,
    agent_id: Optional[str] = None,
) -> None:
    """Best-effort alert when a scheduled run fails or times out.

    Prefers the MonitoringAgent's Slack notifier (already wired with the
    Slack client at startup); falls back to a raw Slack incoming-webhook
    (``SCHEDULER_ALERT_WEBHOOK`` or ``SLACK_WEBHOOK_URL``) so alerting works
    even without the full monitoring stack. Never raises — a broken alert
    channel must not take down the scheduler."""
    text = (
        f":rotating_light: Brigade scheduled run *{run_id}* "
        f"({agent_id or 'unknown agent'}) ended `{status}`: {error[:500]}"
    )
    # 1) MonitoringAgent notifier, if available.
    try:
        from app.api.monitoring_routes import get_monitoring_agent

        agent = get_monitoring_agent()
        notifier = getattr(agent, "slack_client", None) if agent else None
        if notifier is not None and getattr(notifier, "is_configured", False):
            channel = os.getenv("SCHEDULER_ALERT_CHANNEL", "#alerts")
            await notifier.send_message(channel, text)
            return
    except Exception as e:  # pragma: no cover - defensive
        logger.debug("MonitoringAgent notify unavailable: %s", e)

    # 2) Raw Slack incoming-webhook fallback.
    webhook = os.getenv("SCHEDULER_ALERT_WEBHOOK") or os.getenv("SLACK_WEBHOOK_URL")
    if not webhook:
        logger.warning(
            "Scheduled run %s ended %s but no alert channel is configured "
            "(set SCHEDULER_ALERT_WEBHOOK or SLACK_WEBHOOK_URL)", run_id, status
        )
        return
    try:
        import httpx

        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(webhook, json={"text": text})
    except Exception as e:  # pragma: no cover - defensive
        logger.warning("Failed to post scheduler failure alert: %s", e)


def _record_run_outcome(outcome: str) -> None:
    """Increment the scheduled-run Prometheus counter; never raises."""
    try:
        scheduled_run_total.labels(outcome=outcome).inc()
    except Exception:  # pragma: no cover - defensive
        pass


def _parse_cron(expr: str, tz: str = "UTC") -> CronTrigger:
    """Parse a 5-field cron expression. Raises ValueError on bad input."""
    parts = expr.strip().split()
    if len(parts) != 5:
        raise ValueError(
            f"cron must be 5 fields (minute hour day month day_of_week), got: {expr!r}"
        )
    minute, hour, day, month, dow = parts
    return CronTrigger(
        minute=minute, hour=hour, day=day, month=month, day_of_week=dow, timezone=tz
    )


class BrigadeScheduler:
    """Wraps APScheduler with Brigade-aware job semantics."""

    def __init__(self, llm_client):
        self.llm_client = llm_client
        self.scheduler: Optional[AsyncIOScheduler] = None
        # BR-4 leader election state.
        self._leader: Optional[PgAdvisoryLeaderLock] = None
        self._is_leader: bool = False
        self._leader_task: Optional[asyncio.Task] = None
        self._last_reload_monotonic: float = 0.0
        self._stopping: bool = False

    @property
    def is_leader(self) -> bool:
        """True iff THIS replica currently holds the scheduler leadership lock and
        is therefore the one registering + firing cron jobs."""
        return self._is_leader

    # ── lifecycle ──────────────────────────────────────────────

    async def start(self) -> None:
        if self.scheduler is not None:
            return
        self.scheduler = AsyncIOScheduler(timezone="UTC")
        self.scheduler.start()
        self._stopping = False
        # BR-4: only the leader registers/fires. Acquire the advisory lock first;
        # reload_all() is gated on leadership so a follower registers ZERO jobs.
        self._leader = PgAdvisoryLeaderLock(
            MIGRATION_DATABASE_URL, lock_key_from_name(SCHEDULER_LEADER_LOCK_NAME)
        )
        await self._acquire_and_sync()
        # Background loop keeps trying to acquire (follower → leader takeover) and,
        # while leader, periodically re-reads the DB to pick up rows created on
        # other replicas.
        self._leader_task = asyncio.create_task(self._leader_loop())
        logger.info("BrigadeScheduler started (leader=%s)", self._is_leader)

    async def shutdown(self) -> None:
        self._stopping = True
        # Stop the leadership loop first so it can't re-acquire mid-teardown.
        if self._leader_task is not None:
            self._leader_task.cancel()
            try:
                await self._leader_task
            except asyncio.CancelledError:
                pass
            except Exception as e:  # pragma: no cover - defensive
                logger.debug("leader loop join error: %s", e)
            self._leader_task = None
        if self.scheduler is not None:
            try:
                self.scheduler.shutdown(wait=False)
            except Exception as e:
                logger.warning("Scheduler shutdown error: %s", e)
            self.scheduler = None
        # BR-4: release the advisory lock so a standby replica takes over at once
        # (a hard crash needs no release — Postgres drops the session lock).
        if self._leader is not None:
            try:
                await self._leader.release()
            except Exception as e:  # pragma: no cover - defensive
                logger.warning("leader release error: %s", e)
            self._leader = None
        self._is_leader = False
        logger.info("BrigadeScheduler stopped")

    # ── BR-4 leadership ────────────────────────────────────────

    async def _acquire_and_sync(self) -> bool:
        """(Re)attempt to acquire leadership; on a fresh WIN, register all jobs; on
        a fresh LOSS, clear them. Returns current leadership. Never raises."""
        was_leader = self._is_leader
        try:
            self._is_leader = bool(self._leader and await self._leader.try_acquire())
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("scheduler leadership check failed: %s", e)
            self._is_leader = False

        if self._is_leader and not was_leader:
            logger.info("BrigadeScheduler ACQUIRED leadership — registering jobs")
            try:
                await self.reload_all()
            except Exception as e:  # pragma: no cover - defensive
                logger.error("scheduler reload after acquiring leadership failed: %s", e)
            self._last_reload_monotonic = time.monotonic()
        elif not self._is_leader and was_leader:
            logger.warning("BrigadeScheduler LOST leadership — clearing jobs (standby)")
            self._clear_jobs()
        return self._is_leader

    def _clear_jobs(self) -> None:
        """Remove all registered jobs (used when this replica stops being leader)."""
        if self.scheduler is None:
            return
        try:
            self.scheduler.remove_all_jobs()
        except Exception:  # pragma: no cover - defensive
            pass

    async def _leader_loop(self) -> None:
        """Standby/takeover + periodic-resync loop.

        Followers poll to acquire (taking over on leader death); the leader
        periodically re-reads the DB so a schedule created/edited on ANOTHER
        replica is picked up within SCHEDULER_LEADER_RELOAD_SECONDS."""
        poll = max(1, SCHEDULER_LEADER_POLL_SECONDS)
        while not self._stopping:
            try:
                await asyncio.sleep(poll)
                if self._stopping:
                    break
                if not self._is_leader:
                    await self._acquire_and_sync()
                elif time.monotonic() - self._last_reload_monotonic >= max(
                    5, SCHEDULER_LEADER_RELOAD_SECONDS
                ):
                    await self.reload_all()
                    self._last_reload_monotonic = time.monotonic()
            except asyncio.CancelledError:
                break
            except Exception as e:  # pragma: no cover - defensive
                logger.warning("scheduler leader loop error: %s", e)

    # ── job registration ──────────────────────────────────────

    async def reload_all(self) -> int:
        """Read every enabled ScheduledRun and (re)register it. Returns count.

        BR-4: a NO-OP for a non-leader replica (returns 0 without registering any
        job) so only the leader ever fires cron jobs."""
        if self.scheduler is None:
            return 0
        if not self._is_leader:
            logger.debug("reload_all: not leader — standing by, 0 jobs registered")
            return 0
        async with admin_session() as session:
            rows = (
                await session.execute(
                    select(ScheduledRun).where(ScheduledRun.enabled.is_(True))
                )
            ).scalars().all()
        count = 0
        for row in rows:
            try:
                self._register(row)
                count += 1
            except Exception as e:
                logger.error("Failed to register scheduled_run %s: %s", row.id, e)
        logger.info("BrigadeScheduler loaded %d enabled jobs", count)
        return count

    def _register(self, run: ScheduledRun) -> None:
        if self.scheduler is None:
            raise RuntimeError("scheduler not started")
        trigger = _parse_cron(run.cron, run.timezone or "UTC")
        run_id = str(run.id)
        self.scheduler.add_job(
            self._fire,
            trigger=trigger,
            id=run_id,
            kwargs={"scheduled_run_id": run_id},
            replace_existing=True,
            misfire_grace_time=60,
            coalesce=True,
            max_instances=1,
        )

    def upsert(self, run: ScheduledRun) -> None:
        """Sync the scheduler with a single row's current state.

        BR-4: a NO-OP on a non-leader replica — the DB row is the source of truth
        and the leader picks the change up on its next periodic reload, so a
        follower never registers (and thus never fires) a job."""
        if self.scheduler is None or not self._is_leader:
            return
        run_id = str(run.id)
        if run.enabled:
            self._register(run)
        else:
            try:
                self.scheduler.remove_job(run_id)
            except Exception:
                pass

    def remove(self, run_id: str) -> None:
        # BR-4: no-op on a non-leader replica (see upsert).
        if self.scheduler is None or not self._is_leader:
            return
        try:
            self.scheduler.remove_job(str(run_id))
        except Exception:
            pass

    # ── execution ─────────────────────────────────────────────

    async def trigger_now(
        self,
        scheduled_run_id: str,
        *,
        actor: str = "unknown",
        allow_disabled: bool = False,
    ) -> str:
        """Run a job immediately. Returns the history row id.

        A disabled schedule may only be run manually when the caller has made
        that exception explicit with ``allow_disabled=True``. The API layer
        supplies the authenticated actor for the history audit row.
        """
        return await self._fire(
            scheduled_run_id=scheduled_run_id,
            manual=True,
            actor=actor,
            allow_disabled=allow_disabled,
        )

    async def _fire(
        self,
        scheduled_run_id: str,
        manual: bool = False,
        *,
        actor: str = "unknown",
        allow_disabled: bool = False,
    ) -> str:
        """The actual execution path, called by APScheduler or trigger_now.

        The enabled check stays inside the database read/transaction so a row
        disabled after registration cannot be executed by a pending APScheduler
        callback. Manual execution is the only exception, and only when the
        request explicitly opted into running a disabled schedule.
        """
        trigger = RUN_TRIGGER_MANUAL if manual else RUN_TRIGGER_SCHEDULE
        if trigger not in RUN_TRIGGERS:  # defensive guard for future callers
            raise ValueError(f"unsupported scheduled-run trigger: {trigger}")
        history_id: Optional[str] = None
        try:
            async with admin_session() as session:
                run = await session.get(ScheduledRun, scheduled_run_id)
                if run is None:
                    logger.warning("ScheduledRun %s vanished before fire", scheduled_run_id)
                    return ""
                if not run.enabled and not (manual and allow_disabled):
                    logger.info("ScheduledRun %s disabled, skipping", scheduled_run_id)
                    return ""

                await _bind_org(session, run.org_id)
                history = ScheduledRunHistory(
                    scheduled_run_id=run.id,
                    org_id=run.org_id,
                    started_at=datetime.utcnow(),
                    status="running",
                    trigger=trigger,
                    actor=(str(actor or "unknown")[:255] if manual else SCHEDULED_RUN_ACTOR),
                )
                session.add(history)
                await session.commit()
                history_id = str(history.id)

                agent = await session.get(Agent, run.agent_id)
                if agent is None:
                    _record_run_outcome("agent_missing")
                    await self._finalize(
                        history_id, "error", error=f"agent {run.agent_id} not found"
                    )
                    await self._update_run_status(run.id, "error", "agent missing")
                    await notify_scheduled_run_failure(
                        scheduled_run_id, "error",
                        f"agent {run.agent_id} not found", run.agent_id,
                    )
                    return history_id

                agent_dict = agent.to_dict()
                agent_id_for_alert = agent_dict.get("id")
                prompt = run.prompt
                user_id = str(run.owner_user_id) if run.owner_user_id else "scheduler"
                # BR-3.4: carry the run's org so the scheduled execution is metered
                # against the owning tenant (this path was previously unmetered).
                org_id_for_run = str(run.org_id) if run.org_id else None
                timeout = max(
                    5,
                    int(run.max_runtime_seconds or DEFAULT_SCHEDULER_MAX_RUNTIME_SECONDS),
                )

            # Execute outside the session — chat path may be slow.
            try:
                result = await asyncio.wait_for(
                    self._invoke_agent(agent_dict, prompt, user_id, org_id_for_run),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                _record_run_outcome("timeout")
                await self._finalize(
                    history_id,
                    "timeout",
                    error=f"exceeded max_runtime_seconds={timeout}",
                )
                await self._update_run_status(scheduled_run_id, "timeout",
                                              f"timed out after {timeout}s")
                await notify_scheduled_run_failure(
                    scheduled_run_id, "timeout",
                    f"exceeded max_runtime_seconds={timeout}", agent_id_for_alert,
                )
                return history_id
            except Exception as e:
                logger.exception("Scheduled run %s failed", scheduled_run_id)
                _record_run_outcome("error")
                await self._finalize(history_id, "error", error=str(e))
                await self._update_run_status(scheduled_run_id, "error", str(e)[:500])
                await notify_scheduled_run_failure(
                    scheduled_run_id, "error", str(e), agent_id_for_alert,
                )
                return history_id

            content = (result.get("content") or "")[:4000]
            tool_calls = result.get("toolCalls") or []
            _record_run_outcome("success")
            await self._finalize(
                history_id,
                "success",
                output_summary=content[:2000],
                tool_calls_count=len(tool_calls),
            )
            await self._update_run_status(
                scheduled_run_id, "success", content[:500] or "(empty response)"
            )
            return history_id
        except Exception as e:
            logger.exception("Scheduler _fire wrapper failed for %s", scheduled_run_id)
            if history_id:
                await self._finalize(history_id, "error", error=str(e))
            return history_id or ""

    async def _invoke_agent(
        self, agent: dict, message: str, user_id: str, org_id: Optional[str] = None
    ) -> dict:
        """Mirror of POST /api/v1/agents/{id}/chat (non-streaming, no memory)."""
        system_parts = []
        if agent.get("persona"):
            system_parts.append(agent["persona"])
        if agent.get("systemPrompt"):
            system_parts.append(agent["systemPrompt"])
        system_content = "\n\n".join(system_parts) or (
            f"You are {agent.get('displayName') or agent.get('name')}, "
            "a specialized AI agent."
        )
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": message},
        ]
        model = agent.get("model") or DEFAULT_MODEL
        temperature = agent.get("temperature", 0.7)
        max_tokens = agent.get("maxTokens", 2000)

        # Langfuse trace for the scheduled run — mirrors the interactive chat
        # path so scheduled executions show up in observability too.
        tracer = None
        try:
            from app.observability import get_tracer

            tracer = get_tracer(agent_id=agent.get("id"), user_id=user_id)
            tracer.start_trace(
                name=f"scheduled_run:{agent.get('id')}",
                input_data={"message": message, "model": model},
                metadata={"agent_name": agent.get("displayName") or agent.get("name")},
                tags=["scheduled", agent.get("domain", "general")],
            )
        except Exception as e:  # pragma: no cover - defensive
            logger.debug("Langfuse tracer unavailable for scheduled run: %s", e)
            tracer = None

        agent_tools = get_tools_for_agent(agent)
        tool_calls_log: list[dict] = []

        if agent_tools:
            def on_tool_call(tc):
                tool_calls_log.append(
                    {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                )

            def on_tool_result(tr):
                for entry in tool_calls_log:
                    if entry["id"] == tr.tool_call_id:
                        entry["result"] = tr.result
                        entry["error"] = tr.error
                        break

            response = await self.llm_client.execute_tool_loop(
                messages=messages,
                tools=agent_tools,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                user_id=user_id,
                on_tool_call=on_tool_call,
                on_tool_result=on_tool_result,
            )
        else:
            response = await self.llm_client.chat_completion(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                user_id=user_id,
            )

        content = self.llm_client.get_response_content(response) or ""

        # BR-3.4: meter the scheduled run against its OWNING ORG. Scheduled runs
        # call the LLM client directly (like the interactive path) and were
        # previously UNMETERED — no durable usage row, invisible to the per-org cap.
        try:
            _resp = response if isinstance(response, dict) else {}
            _usage = _resp.get("usage") or {}
            _sched_tokens = int(
                _usage.get("total_tokens")
                or (_usage.get("prompt_tokens") or 0) + (_usage.get("completion_tokens") or 0)
                or 0
            )
            await meter_usage(
                org_id=org_id,
                user=user_id if (user_id and user_id != "scheduler") else None,
                source="scheduled_run",
                model=_resp.get("model") or model,
                tokens=_sched_tokens,
                provider=_resp.get("provider"),
                agent_id=agent.get("id"),
                agent_name=agent.get("displayName") or agent.get("name"),
                agent_domain=agent.get("domain"),
                tools_used=[t.get("name") for t in (tool_calls_log or [])] or None,
            )
        except Exception as _me:
            logger.debug("scheduled-run meter skipped: %s", _me)

        if tracer is not None:
            try:
                tracer.log_generation(
                    name="scheduled_chat_completion",
                    model=(response.get("model") if isinstance(response, dict) else None)
                    or model,
                    input_messages=messages,
                    output=content,
                    metadata={"tool_calls": len(tool_calls_log)},
                )
                tracer.end_trace(
                    output={"content": content[:500], "tools_used": len(tool_calls_log)},
                    status="success",
                )
            except Exception:  # pragma: no cover - defensive
                pass
        return {"content": content, "toolCalls": tool_calls_log}

    # ── persistence helpers ──────────────────────────────────

    async def _finalize(
        self,
        history_id: str,
        status: str,
        output_summary: Optional[str] = None,
        error: Optional[str] = None,
        tool_calls_count: int = 0,
    ) -> None:
        async with admin_session() as session:
            org_id = (
                await session.execute(
                    select(ScheduledRunHistory.org_id).where(ScheduledRunHistory.id == history_id)
                )
            ).scalar_one_or_none()
            if org_id is not None:
                await _bind_org(session, org_id)
            row = await session.get(ScheduledRunHistory, history_id)
            if row is None:
                return
            row.status = status
            row.output_summary = output_summary
            row.error = error
            row.tool_calls_count = tool_calls_count
            row.finished_at = datetime.utcnow()
            await session.commit()

    async def _update_run_status(
        self, run_id: str, status: str, summary: Optional[str]
    ) -> None:
        async with admin_session() as session:
            org_id = (
                await session.execute(select(ScheduledRun.org_id).where(ScheduledRun.id == run_id))
            ).scalar_one_or_none()
            if org_id is not None:
                await _bind_org(session, org_id)
            run = await session.get(ScheduledRun, run_id)
            if run is None:
                return
            run.last_run_at = datetime.utcnow()
            run.last_status = status
            run.last_result_summary = (summary or "")[:2000]
            await session.commit()


# Module-level singleton wired up in app.main.lifespan.
_scheduler: Optional[BrigadeScheduler] = None


def init_scheduler(llm_client) -> BrigadeScheduler:
    global _scheduler
    _scheduler = BrigadeScheduler(llm_client)
    return _scheduler


def get_scheduler() -> Optional[BrigadeScheduler]:
    return _scheduler
