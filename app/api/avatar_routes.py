"""Admin controls for reviewed Brigade agent-avatar mappings."""

from __future__ import annotations

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select, update

from app.agent_avatars import (
    build_avatar_coverage,
    canonical_avatar_path,
    plan_verified_avatar_updates,
    validate_explicit_avatar_url,
)
from app.auth.middleware import AuthUser, require_admin
from app.db.database import admin_session
from app.db.models import Agent

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/admin/agent-avatars",
    tags=["admin-agent-avatars"],
)


class ApplyVerifiedAvatarsRequest(BaseModel):
    """Explicit null-only application of reviewed avatar mappings."""

    dryRun: bool = True
    agentIds: list[str] | None = Field(
        default=None,
        description="Optional reviewed agent IDs; omit to apply every safe candidate.",
    )


class BindAgentAvatarRequest(BaseModel):
    """Explicit admin binding of an avatar URL to a roster agent.

    ``avatarUrl`` is required when setting a binding. Pass ``null`` (JSON null)
    to clear an existing binding. Brigade never invents a URL from the agent
    name or rank — identity-owner evidence only.
    """

    agentId: str = Field(..., min_length=1, max_length=128)
    avatarUrl: Optional[str] = Field(
        default=None,
        description=(
            "Same-origin path (e.g. /avatars/majik.webp) or absolute https URL. "
            "Omit/null clears the binding. Use useVerified=true to store the "
            "reviewed canonical path for a verified agent without typing it."
        ),
    )
    useVerified: bool = Field(
        default=False,
        description=(
            "When true, bind the reviewed canonical path for agentId from the "
            "verified manifest. Rejects unmapped IDs instead of guessing."
        ),
    )


async def _owner_roster() -> list[dict[str, object]]:
    """Read the full roster outside tenant RLS for a master-admin report."""

    async with admin_session() as session:
        result = await session.execute(
            select(Agent.id, Agent.avatar_url).order_by(Agent.id)
        )
        return [
            {"id": agent_id, "avatarUrl": avatar_url}
            for agent_id, avatar_url in result.all()
        ]


@router.get("/coverage")
async def avatar_coverage(
    user: Annotated[AuthUser, Depends(require_admin)] = None,
):
    """Report verified, custom, available, and unresolved roster bindings."""

    return build_avatar_coverage(await _owner_roster())


@router.post("/apply-verified")
async def apply_verified_avatars(
    request: ApplyVerifiedAvatarsRequest,
    user: Annotated[AuthUser, Depends(require_admin)] = None,
):
    """Apply reviewed mappings to empty rows without replacing custom URLs.

    ``dryRun`` defaults to true. Reviewed mappings live in source control with
    evidence and asset hashes; this endpoint never accepts an arbitrary URL.
    """

    roster = await _owner_roster()
    try:
        planned = plan_verified_avatar_updates(roster, request.agentIds)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if request.dryRun or not planned:
        return {
            "dryRun": request.dryRun,
            "planned": planned,
            "applied": [],
            "coverage": build_avatar_coverage(roster),
        }

    applied: list[dict[str, str]] = []
    async with admin_session() as session:
        for item in planned:
            result = await session.execute(
                update(Agent)
                .where(
                    Agent.id == item["agentId"],
                    or_(
                        Agent.avatar_url.is_(None),
                        func.btrim(Agent.avatar_url) == "",
                    ),
                )
                .values(avatar_url=item["avatarUrl"])
            )
            if result.rowcount:
                applied.append(item)
        await session.commit()

    logger.info(
        "Admin %s applied %d reviewed agent-avatar mappings: %s",
        getattr(user, "email", None) or getattr(user, "id", "admin"),
        len(applied),
        ",".join(item["agentId"] for item in applied),
    )
    refreshed = await _owner_roster()
    return {
        "dryRun": False,
        "planned": planned,
        "applied": applied,
        "coverage": build_avatar_coverage(refreshed),
    }


@router.post("/bind")
async def bind_agent_avatar(
    request: BindAgentAvatarRequest,
    user: Annotated[AuthUser, Depends(require_admin)] = None,
):
    """Explicitly set or clear an agent's ``avatar_url``.

    Registration (``POST /api/v1/agents``) already accepts ``avatarUrl`` on
    create; this endpoint is the admin path for binding an existing row after
    registration without a full agent PUT. Never infers from name/rank.
    """

    agent_id = request.agentId.strip()
    if not agent_id:
        raise HTTPException(status_code=422, detail="agentId is required")

    if request.useVerified:
        path = canonical_avatar_path(agent_id)
        if path is None:
            raise HTTPException(
                status_code=422,
                detail=f"No reviewed avatar mapping for: {agent_id}",
            )
        target_url: str | None = path
    else:
        # JSON null / omitted / blank → clear. Explicit non-empty → validate.
        if request.avatarUrl is None or not str(request.avatarUrl).strip():
            target_url = None
        else:
            try:
                target_url = validate_explicit_avatar_url(request.avatarUrl)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc

    async with admin_session() as session:
        result = await session.execute(select(Agent).where(Agent.id == agent_id))
        agent = result.scalar_one_or_none()
        if agent is None:
            raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")
        previous = agent.avatar_url
        agent.avatar_url = target_url
        await session.commit()
        bound = {
            "id": agent.id,
            "avatarUrl": agent.avatar_url,
            "previousAvatarUrl": previous,
        }

    logger.info(
        "Admin %s bound agent-avatar %s: %s -> %s",
        getattr(user, "email", None) or getattr(user, "id", "admin"),
        agent_id,
        previous,
        target_url,
    )
    return {
        "agentId": bound["id"],
        "avatarUrl": bound["avatarUrl"],
        "previousAvatarUrl": bound["previousAvatarUrl"],
        "verifiedAvatarUrl": canonical_avatar_path(agent_id),
    }
