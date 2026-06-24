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
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.db.database import async_session
from app.db.models import Agent, ScheduledRun, ScheduledRunHistory
from app.llm.tool_resolver import get_tools_for_agent
from app.llm.ops_center_client import DEFAULT_MODEL

logger = logging.getLogger(__name__)


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

    # ── lifecycle ──────────────────────────────────────────────

    async def start(self) -> None:
        if self.scheduler is not None:
            return
        self.scheduler = AsyncIOScheduler(timezone="UTC")
        self.scheduler.start()
        await self.reload_all()
        logger.info("BrigadeScheduler started")

    async def shutdown(self) -> None:
        if self.scheduler is None:
            return
        try:
            self.scheduler.shutdown(wait=False)
        except Exception as e:
            logger.warning("Scheduler shutdown error: %s", e)
        self.scheduler = None
        logger.info("BrigadeScheduler stopped")

    # ── job registration ──────────────────────────────────────

    async def reload_all(self) -> int:
        """Read every enabled ScheduledRun and (re)register it. Returns count."""
        if self.scheduler is None:
            return 0
        async with async_session() as session:
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
        """Sync the scheduler with a single row's current state."""
        if self.scheduler is None:
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
        if self.scheduler is None:
            return
        try:
            self.scheduler.remove_job(str(run_id))
        except Exception:
            pass

    # ── execution ─────────────────────────────────────────────

    async def trigger_now(self, scheduled_run_id: str) -> str:
        """Run a job immediately. Returns the history row id."""
        return await self._fire(scheduled_run_id=scheduled_run_id, manual=True)

    async def _fire(self, scheduled_run_id: str, manual: bool = False) -> str:
        """The actual execution path, called by APScheduler or trigger_now."""
        history_id: Optional[str] = None
        try:
            async with async_session() as session:
                run = await session.get(ScheduledRun, scheduled_run_id)
                if run is None:
                    logger.warning("ScheduledRun %s vanished before fire", scheduled_run_id)
                    return ""
                if not run.enabled and not manual:
                    logger.info("ScheduledRun %s disabled, skipping", scheduled_run_id)
                    return ""

                history = ScheduledRunHistory(
                    scheduled_run_id=run.id,
                    started_at=datetime.utcnow(),
                    status="running",
                )
                session.add(history)
                await session.commit()
                history_id = str(history.id)

                agent = await session.get(Agent, run.agent_id)
                if agent is None:
                    await self._finalize(
                        history_id, "error", error=f"agent {run.agent_id} not found"
                    )
                    await self._update_run_status(run.id, "error", "agent missing")
                    return history_id

                agent_dict = agent.to_dict()
                prompt = run.prompt
                user_id = str(run.owner_user_id) if run.owner_user_id else "scheduler"
                timeout = max(5, int(run.max_runtime_seconds or 300))

            # Execute outside the session — chat path may be slow.
            try:
                result = await asyncio.wait_for(
                    self._invoke_agent(agent_dict, prompt, user_id),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                await self._finalize(
                    history_id,
                    "timeout",
                    error=f"exceeded max_runtime_seconds={timeout}",
                )
                await self._update_run_status(scheduled_run_id, "timeout",
                                              f"timed out after {timeout}s")
                return history_id
            except Exception as e:
                logger.exception("Scheduled run %s failed", scheduled_run_id)
                await self._finalize(history_id, "error", error=str(e))
                await self._update_run_status(scheduled_run_id, "error", str(e)[:500])
                return history_id

            content = (result.get("content") or "")[:4000]
            tool_calls = result.get("toolCalls") or []
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

    async def _invoke_agent(self, agent: dict, message: str, user_id: str) -> dict:
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
        async with async_session() as session:
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
        async with async_session() as session:
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
