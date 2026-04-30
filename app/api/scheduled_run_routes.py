"""REST API for Brigade scheduled runs (/api/v1/scheduled-runs)."""

from __future__ import annotations

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, select

from app.auth.middleware import AuthUser, require_admin, require_operator
from app.auth.roles import UserRole
from app.db.database import AsyncSession, get_session
from app.db.models import Agent, ScheduledRun, ScheduledRunHistory
from app.services.scheduler import _parse_cron, get_scheduler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scheduled-runs", tags=["scheduled-runs"])


class ScheduledRunCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    agentId: str
    prompt: str
    cron: str
    timezone: str = "UTC"
    ownerUserId: Optional[str] = None
    enabled: bool = True
    maxRuntimeSeconds: int = Field(300, ge=5, le=3600)


class ScheduledRunUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    agentId: Optional[str] = None
    prompt: Optional[str] = None
    cron: Optional[str] = None
    timezone: Optional[str] = None
    ownerUserId: Optional[str] = None
    enabled: Optional[bool] = None
    maxRuntimeSeconds: Optional[int] = Field(None, ge=5, le=3600)


def _is_admin(user: AuthUser) -> bool:
    return user is not None and user.role == UserRole.ADMIN


def _own_filter(user: AuthUser):
    """Non-admins only see their own scheduled runs."""
    if _is_admin(user):
        return None
    uid = getattr(user, "user_id", None) or getattr(user, "id", None)
    return uid


def _validate_cron(expr: str, tz: str) -> None:
    try:
        _parse_cron(expr, tz or "UTC")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"invalid cron: {e}")


async def _ensure_agent_exists(session: AsyncSession, agent_id: str) -> None:
    agent = await session.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=400, detail=f"agent not found: {agent_id}")


def _ensure_owner_or_admin(user: AuthUser, run: ScheduledRun) -> None:
    if _is_admin(user):
        return
    uid = getattr(user, "user_id", None) or getattr(user, "id", None)
    if not run.owner_user_id or str(run.owner_user_id) != str(uid):
        raise HTTPException(status_code=403, detail="not the owner of this scheduled run")


# ── endpoints ─────────────────────────────────────────────────────

@router.get("")
async def list_scheduled_runs(
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    stmt = select(ScheduledRun).order_by(desc(ScheduledRun.created_at))
    own = _own_filter(user)
    if own is not None:
        stmt = stmt.where(ScheduledRun.owner_user_id == own)
    rows = (await session.execute(stmt)).scalars().all()
    return {"items": [r.to_dict() for r in rows], "total": len(rows)}


@router.post("", status_code=201)
async def create_scheduled_run(
    body: ScheduledRunCreate,
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    _validate_cron(body.cron, body.timezone)
    await _ensure_agent_exists(session, body.agentId)

    owner_id = body.ownerUserId
    if not _is_admin(user):
        # non-admins can only create for themselves
        owner_id = getattr(user, "user_id", None) or getattr(user, "id", None)

    run = ScheduledRun(
        name=body.name,
        agent_id=body.agentId,
        prompt=body.prompt,
        cron=body.cron,
        timezone=body.timezone or "UTC",
        owner_user_id=owner_id,
        enabled=body.enabled,
        max_runtime_seconds=body.maxRuntimeSeconds,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)

    sched = get_scheduler()
    if sched is not None and run.enabled:
        sched.upsert(run)

    return run.to_dict()


@router.get("/{run_id}")
async def get_scheduled_run(
    run_id: str,
    history_limit: int = Query(20, ge=0, le=200),
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    run = await session.get(ScheduledRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="scheduled run not found")
    _ensure_owner_or_admin(user, run)
    body = run.to_dict()
    if history_limit:
        rows = (
            await session.execute(
                select(ScheduledRunHistory)
                .where(ScheduledRunHistory.scheduled_run_id == run.id)
                .order_by(desc(ScheduledRunHistory.started_at))
                .limit(history_limit)
            )
        ).scalars().all()
        body["recentHistory"] = [r.to_dict() for r in rows]
    return body


@router.put("/{run_id}")
async def update_scheduled_run(
    run_id: str,
    body: ScheduledRunUpdate,
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    run = await session.get(ScheduledRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="scheduled run not found")
    _ensure_owner_or_admin(user, run)

    if body.cron is not None or body.timezone is not None:
        _validate_cron(body.cron or run.cron, body.timezone or run.timezone)
    if body.agentId is not None:
        await _ensure_agent_exists(session, body.agentId)
    if body.ownerUserId is not None and not _is_admin(user):
        raise HTTPException(status_code=403, detail="only admins can change ownerUserId")

    for field, attr in [
        ("name", "name"),
        ("agentId", "agent_id"),
        ("prompt", "prompt"),
        ("cron", "cron"),
        ("timezone", "timezone"),
        ("ownerUserId", "owner_user_id"),
        ("enabled", "enabled"),
        ("maxRuntimeSeconds", "max_runtime_seconds"),
    ]:
        value = getattr(body, field)
        if value is not None:
            setattr(run, attr, value)

    await session.commit()
    await session.refresh(run)

    sched = get_scheduler()
    if sched is not None:
        sched.upsert(run)

    return run.to_dict()


@router.delete("/{run_id}", status_code=204)
async def delete_scheduled_run(
    run_id: str,
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    run = await session.get(ScheduledRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="scheduled run not found")
    _ensure_owner_or_admin(user, run)

    sched = get_scheduler()
    if sched is not None:
        sched.remove(str(run.id))

    await session.delete(run)
    await session.commit()
    return None


@router.post("/{run_id}/run-now")
async def run_now(
    run_id: str,
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    run = await session.get(ScheduledRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="scheduled run not found")
    _ensure_owner_or_admin(user, run)

    sched = get_scheduler()
    if sched is None:
        raise HTTPException(status_code=503, detail="scheduler not running")
    history_id = await sched.trigger_now(str(run.id))
    if not history_id:
        raise HTTPException(status_code=500, detail="run failed to start")
    history = await session.get(ScheduledRunHistory, history_id)
    return history.to_dict() if history else {"id": history_id}


@router.get("/{run_id}/history")
async def list_history(
    run_id: str,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    run = await session.get(ScheduledRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="scheduled run not found")
    _ensure_owner_or_admin(user, run)

    rows = (
        await session.execute(
            select(ScheduledRunHistory)
            .where(ScheduledRunHistory.scheduled_run_id == run.id)
            .order_by(desc(ScheduledRunHistory.started_at))
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return {
        "items": [r.to_dict() for r in rows],
        "limit": limit,
        "offset": offset,
    }


@router.post("/admin/reload", dependencies=[Depends(require_admin)])
async def reload_scheduler():
    """Force the scheduler to re-read all enabled runs from DB."""
    sched = get_scheduler()
    if sched is None:
        raise HTTPException(status_code=503, detail="scheduler not running")
    count = await sched.reload_all()
    return {"reloaded": count}
