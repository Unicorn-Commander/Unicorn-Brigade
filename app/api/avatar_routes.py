"""Admin controls for reviewed Brigade agent-avatar mappings."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select, update

from app.agent_avatars import (
    build_avatar_coverage,
    plan_verified_avatar_updates,
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
