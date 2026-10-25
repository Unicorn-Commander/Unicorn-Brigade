"""REST API for the autonomy catalogue (/api/v1/autonomy) — P-00092.

One place listing every agent job that runs on its own: Brigade's own scheduled
runs and the loops outside Brigade that register and report here. The logic
lives in ``app.services.autonomy`` (pure, unit-tested); these routes load rows,
call it, and persist.

Auth
----
* Reads and human writes: ``require_operator`` (same as /scheduled-runs).
  Non-admin operators see Brigade items through the scheduled-runs
  ``_own_filter``; outside jobs are visible to every operator in the org.
* Reporting (``PUT /jobs/{key}``, ``POST /jobs/{key}/runs``):
  ``require_autonomy_reporter`` — an operator/admin, or a key carrying the
  ``autonomy:report`` permission (which grants nothing else).

Tenancy
-------
Exactly like /scheduled-runs: the request session from ``get_session`` is bound
to the caller's org by the auth dependency and every query runs under row-level
security. The two new tables are additionally filtered on
``org_id = current_org_id()`` (the api_keys S9 pattern) so a single-role dev
database that bypasses RLS still never mixes orgs. Each write does all of its
reads and writes in the request's ONE transaction and commits once at the end —
nothing reads after the commit, when the pooled connection may no longer carry
the org (see ``ensure_org_context``).
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field, ValidationInfo, field_validator
from sqlalchemy import delete, desc, func, select
from sqlalchemy.exc import IntegrityError

from app.api.scheduled_run_routes import _own_filter
from app.auth.middleware import AuthUser, require_autonomy_reporter, require_operator
from app.db.database import AsyncSession, ensure_org_context, get_session
from app.db.models import (
    Agent,
    AutonomousJob,
    AutonomousJobRun,
    ScheduledRun,
    ScheduledRunHistory,
    gen_uuid,
)
from app.services import autonomy as svc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/autonomy", tags=["autonomy"])

ExternalRunner = Literal["cron", "systemd", "launchd", "claude-routine", "continuous", "other"]
RunStatus = Literal["running", "success", "error", "timeout", "skipped"]
_INT4_MAX = 2_147_483_647


def _strip_optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    return value or None


class AutonomousJobUpsert(BaseModel):
    """Register or update an outside job (``PUT /autonomy/jobs/{key}``)."""

    name: str = Field(..., min_length=1, max_length=255)
    responsibility: str = Field(..., min_length=1, max_length=2000)
    agentId: Optional[str] = Field(None, max_length=255)
    host: str = Field(..., min_length=1, max_length=120)
    runner: ExternalRunner
    # timezone is declared BEFORE schedule so the schedule validator can see it.
    timezone: str = Field("UTC", min_length=1, max_length=64)
    schedule: Optional[str] = Field(None, max_length=120)
    scheduleNote: Optional[str] = Field(None, max_length=255)
    # command / runbookUrl carry no Field constraints ON PURPOSE: a 422 from
    # pydantic echoes the offending input back, and these are exactly the fields
    # a secret lands in by mistake. The route checks them (secret first, then
    # length) and answers with a message that never repeats the value.
    command: Optional[str] = None
    runbookUrl: Optional[str] = None
    owner: Optional[str] = Field(None, max_length=255)
    # Free-text observations (max 2000, same secret check as command; checked
    # in the route for the same no-echo reason).
    notes: Optional[str] = None
    enabled: bool = True

    @field_validator("name", "responsibility", "host")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("agentId", "scheduleNote", "command", "runbookUrl", "owner", "notes")
    @classmethod
    def _blank_is_none(cls, value: Optional[str]) -> Optional[str]:
        return _strip_optional(value)

    @field_validator("timezone")
    @classmethod
    def _valid_timezone(cls, value: str) -> str:
        return svc.validate_timezone(value)

    @field_validator("schedule")
    @classmethod
    def _valid_schedule(cls, value: Optional[str], info: ValidationInfo) -> Optional[str]:
        value = _strip_optional(value)
        if value is None:
            return None
        # Whether a cron parses does not depend on its zone; if the timezone
        # itself was invalid it is reported on its own field.
        return svc.validate_schedule(value, info.data.get("timezone") or "UTC")


class RunReportBody(BaseModel):
    """Report one run (``POST /autonomy/jobs/{key}/runs``).

    ``summary`` (2000) and ``error`` (4000) are clipped and secret-masked rather
    than rejected: refusing a failure report because its error is long would
    lose the failure."""

    status: RunStatus
    runId: Optional[str] = Field(None, max_length=120)
    startedAt: Optional[datetime] = None
    finishedAt: Optional[datetime] = None
    summary: Optional[str] = None
    error: Optional[str] = None
    durationMs: Optional[int] = Field(None, ge=0, le=_INT4_MAX)

    @field_validator("runId")
    @classmethod
    def _blank_run_id(cls, value: Optional[str]) -> Optional[str]:
        return _strip_optional(value)

    def to_report(self) -> svc.RunReport:
        return svc.RunReport(
            status=self.status,
            run_id=self.runId,
            started_at=self.startedAt,
            finished_at=self.finishedAt,
            summary=self.summary,
            error=self.error,
            duration_ms=self.durationMs,
        )


# ── data access (thin; the route tests swap these for in-memory fakes) ──

def _utcnow() -> datetime:
    return datetime.now(UTC)


def _is_uuid(value) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except (TypeError, ValueError, AttributeError):
        return False


async def _find_job(session: AsyncSession, key: str) -> Optional[AutonomousJob]:
    stmt = select(AutonomousJob).where(
        AutonomousJob.key == key,
        AutonomousJob.org_id == func.current_org_id(),
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def _get_agent(session: AsyncSession, agent_id: Optional[str]) -> Optional[Agent]:
    if not agent_id:
        return None
    return await session.get(Agent, agent_id)


async def _load_agents(session: AsyncSession, agent_ids) -> dict:
    ids = sorted({a for a in agent_ids if a})
    if not ids:
        return {}
    rows = (await session.execute(select(Agent).where(Agent.id.in_(ids)))).scalars().all()
    return {a.id: a for a in rows}


async def _load_brigade_runs(session: AsyncSession, user: AuthUser) -> list:
    stmt = select(ScheduledRun).order_by(desc(ScheduledRun.created_at))
    own = _own_filter(user)
    if own is not None:
        if not _is_uuid(own):
            # owner_user_id is a uuid; a caller whose id is not one (an agent
            # key) owns no Brigade schedule — and must not 500 the catalogue.
            return []
        stmt = stmt.where(ScheduledRun.owner_user_id == own)
    return list((await session.execute(stmt)).scalars().all())


async def _load_last_durations(session: AsyncSession, run_ids) -> dict:
    """scheduled_run id -> duration (ms) of its latest FINISHED history row."""
    ids = [r for r in run_ids if r]
    if not ids:
        return {}
    stmt = (
        select(
            ScheduledRunHistory.scheduled_run_id,
            ScheduledRunHistory.started_at,
            ScheduledRunHistory.finished_at,
        )
        .where(
            ScheduledRunHistory.scheduled_run_id.in_(ids),
            ScheduledRunHistory.finished_at.is_not(None),
        )
        .distinct(ScheduledRunHistory.scheduled_run_id)
        .order_by(ScheduledRunHistory.scheduled_run_id, desc(ScheduledRunHistory.started_at))
    )
    out = {}
    for run_id, started_at, finished_at in (await session.execute(stmt)).all():
        if started_at is not None and finished_at is not None:
            out[str(run_id)] = max(0, int((finished_at - started_at).total_seconds() * 1000))
    return out


async def _load_external_jobs(session: AsyncSession) -> list:
    stmt = select(AutonomousJob).where(AutonomousJob.org_id == func.current_org_id())
    return list((await session.execute(stmt)).scalars().all())


async def _find_run(session: AsyncSession, job_id: str, run_id: str) -> Optional[AutonomousJobRun]:
    stmt = (
        select(AutonomousJobRun)
        .where(AutonomousJobRun.job_id == job_id, AutonomousJobRun.run_id == run_id)
        .order_by(desc(AutonomousJobRun.started_at), desc(AutonomousJobRun.created_at))
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def _list_runs(session: AsyncSession, job_id: str, limit: int) -> list:
    stmt = (
        select(AutonomousJobRun)
        .where(AutonomousJobRun.job_id == job_id)
        .order_by(desc(AutonomousJobRun.started_at), desc(AutonomousJobRun.created_at))
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


async def _prune_runs(session: AsyncSession, job_id: str, keep_id: str) -> None:
    """Keep the newest ``MAX_RUNS_PER_JOB`` reports of a job (by arrival)."""
    newest = (
        select(AutonomousJobRun.id)
        .where(AutonomousJobRun.job_id == job_id)
        .order_by(desc(AutonomousJobRun.created_at), desc(AutonomousJobRun.id))
        .limit(svc.MAX_RUNS_PER_JOB)
    )
    await session.execute(
        delete(AutonomousJobRun)
        .where(
            AutonomousJobRun.job_id == job_id,
            AutonomousJobRun.id != keep_id,
            AutonomousJobRun.id.not_in(newest),
        )
        .execution_options(synchronize_session=False)
    )


def _require_job(job: Optional[AutonomousJob], key: str) -> AutonomousJob:
    if job is None:
        raise HTTPException(status_code=404, detail=svc.unknown_job_detail(key))
    return job


# ── endpoints ─────────────────────────────────────────────────────

@router.get("")
async def get_autonomy_catalogue(
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """Every agent job that runs on its own, most urgent first."""
    now = _utcnow()
    runs = await _load_brigade_runs(session, user)
    jobs = await _load_external_jobs(session)
    agents = await _load_agents(
        session, [r.agent_id for r in runs] + [j.agent_id for j in jobs]
    )
    durations = await _load_last_durations(session, [str(r.id) for r in runs])
    items = [
        svc.build_brigade_item(
            r, agents.get(r.agent_id), now, last_duration_ms=durations.get(str(r.id))
        )
        for r in runs
    ]
    items += [svc.build_external_item(j, agents.get(j.agent_id), now) for j in jobs]
    items = svc.sort_catalogue(items)
    return {
        "items": items,
        "counts": svc.catalogue_counts(items),
        "generatedAt": svc.iso_z(now.replace(microsecond=0)),
    }


@router.put("/jobs/{key}")
async def register_autonomous_job(
    key: str,
    body: AutonomousJobUpsert,
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_autonomy_reporter)] = None,
):
    """Register an outside job, or update its definition. Idempotent.

    Accepts an operator, or a key carrying the ``autonomy:report`` permission.
    Required: name, responsibility, host, runner. On first registration absent
    optional fields take their defaults (timezone UTC, enabled true); after that
    only the fields sent are changed, so a script may re-register on every run::

        curl -fsS -X PUT "$BRIGADE_URL/api/v1/autonomy/jobs/build-log-refresh" \
          -H "X-API-Key: $BRIGADE_REPORTER_KEY" -H 'Content-Type: application/json' \
          -d '{"name":"Build Log refresh","agentId":"cpl-colophon","responsibility":"...",
               "host":"bigboy","runner":"cron","schedule":"0 6,14,22 * * *","timezone":"UTC"}'

    ``schedule`` is a standard 5-field crontab line (day-of-week 0/7 = Sunday).
    ``command`` names the entry point and must never carry a secret.
    """
    if not svc.is_valid_key(key):
        raise HTTPException(status_code=422, detail=svc.KEY_RULE)
    for problem in (
        svc.command_problem(body.command),
        svc.runbook_url_problem(body.runbookUrl),
        svc.notes_problem(body.notes),
    ):
        if problem:
            raise HTTPException(status_code=422, detail=problem)

    await ensure_org_context(session)
    agent = None
    if body.agentId is not None:
        agent = await _get_agent(session, body.agentId)
        if agent is None:
            raise HTTPException(
                status_code=422, detail=f"No agent '{body.agentId}' in Brigade's roster."
            )

    job = await _find_job(session, key)
    creating = job is None
    now = _utcnow()
    stamp = svc.to_naive_utc(now)
    values = svc.plan_job_upsert(body.model_dump(), body.model_fields_set, creating=creating)
    if creating:
        job = AutonomousJob(id=gen_uuid(), key=key, created_at=stamp, updated_at=stamp, **values)
        session.add(job)
    else:
        for column, value in values.items():
            setattr(job, column, value)
        job.updated_at = stamp
    if agent is None and job.agent_id:
        agent = await _get_agent(session, job.agent_id)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Job '{key}' was registered by another request at the same moment; send the PUT again.",
        ) from None
    logger.info(
        "autonomy: %s outside job %s (by %s)", "registered" if creating else "updated", key, user.id
    )
    return {"created": creating, "item": svc.build_external_item(job, agent, now)}


@router.delete("/jobs/{key}", status_code=204)
async def delete_autonomous_job(
    key: str,
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """Remove an outside job and its run history."""
    await ensure_org_context(session)
    job = _require_job(await _find_job(session, key), key)
    await session.delete(job)
    await session.commit()
    logger.info("autonomy: deleted outside job %s (by %s)", key, user.id)
    return Response(status_code=204)


@router.post("/jobs/{key}/runs", status_code=201)
async def report_autonomous_run(
    key: str,
    body: RunReportBody,
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_autonomy_reporter)] = None,
):
    """Report one run of a registered outside job.

    ``running`` opens a run; a terminal status (success, error, timeout,
    skipped) with the same ``runId`` closes it, else records a finished run::

        curl -fsS -X POST "$BRIGADE_URL/api/v1/autonomy/jobs/build-log-refresh/runs" \
          -H "X-API-Key: $BRIGADE_REPORTER_KEY" -H 'Content-Type: application/json' \
          -d '{"status":"success","summary":"3 new day stories"}'
    """
    await ensure_org_context(session)
    job = _require_job(await _find_job(session, key), key)
    matched = await _find_run(session, job.id, body.runId) if body.runId else None
    now = _utcnow()
    stamp = svc.to_naive_utc(now)
    outcome = svc.apply_run_report(body.to_report(), matched, now=now)

    if outcome.matched:
        run = matched
        for column, value in outcome.run_values.items():
            setattr(run, column, value)
    else:
        run = AutonomousJobRun(id=gen_uuid(), job_id=job.id, created_at=stamp, **outcome.run_values)
        session.add(run)
    for column, value in outcome.job_updates.items():
        setattr(job, column, value)
    job.updated_at = stamp
    if not outcome.matched:
        await session.flush()
        await _prune_runs(session, job.id, keep_id=run.id)
    agent = await _get_agent(session, job.agent_id)
    await session.commit()
    return {"run": run.to_dict(), "item": svc.build_external_item(job, agent, now)}


@router.get("/jobs/{key}/runs")
async def list_autonomous_runs(
    key: str,
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """A job's reported runs, newest first."""
    job = _require_job(await _find_job(session, key), key)
    runs = await _list_runs(session, job.id, limit)
    return {"runs": [r.to_dict() for r in runs]}
