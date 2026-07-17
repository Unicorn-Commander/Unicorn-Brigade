"""BR-2.1 organization lifecycle API — org CRUD, per-org roles, invite-by-email.

The multi-USER half of tenancy. Thin HTTP wrappers over ``app/db/org_service.py``
(the proof drives that same service layer). Authorization is two-layered:
  * the GLOBAL role gate in ``get_current_user`` only requires that the caller be
    authenticated for any ``/orgs`` path (see app/auth/roles.get_minimum_role_for_method);
  * the PER-ORG gate lives here — owner/admin may rename the org and manage
    invites; members are read-only — resolved fresh against ``org_memberships``.

RLS split for invitations
-------------------------
``organizations`` / ``org_memberships`` carry no RLS (they define tenancy), so
their reads/writes are authz'd purely in-app against the caller's memberships.
``invitations`` IS org-isolated (ENABLE + FORCE). So create/list/revoke require
the caller to be ACTING UNDER the target org (``X-Org-Id`` == path org) — that
binds the GUC the invitations policy filters on — while ACCEPT is inherently
cross-tenant (the invitee is not a member yet) and runs on ``admin_session``.
"""
import logging
from typing import Optional, List, Annotated

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session, admin_session
from app.auth.middleware import get_current_user, AuthUser
from app.db import org_service as svc

logger = logging.getLogger(__name__)
router = APIRouter()


# ── request models ──────────────────────────────────────────────────────────────

class CreateOrgRequest(BaseModel):
    name: str
    slug: Optional[str] = None

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = (v or "").strip()
        if len(v) < 2:
            raise ValueError("Name must be at least 2 characters")
        if len(v) > 120:
            raise ValueError("Name must be at most 120 characters")
        return v


class UpdateOrgRequest(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None


class CreateInviteRequest(BaseModel):
    email: EmailStr
    role: Optional[str] = svc.ORG_ROLE_MEMBER

    @field_validator("role")
    @classmethod
    def _role(cls, v: Optional[str]) -> str:
        v = (v or svc.ORG_ROLE_MEMBER).strip().lower()
        # owner is not invitable; only admin/member may be granted by invite.
        if v not in (svc.ORG_ROLE_ADMIN, svc.ORG_ROLE_MEMBER):
            raise ValueError("role must be 'admin' or 'member'")
        return v


class AcceptInviteRequest(BaseModel):
    token: str


# ── shared authz helpers ────────────────────────────────────────────────────────

async def _uid(session: AsyncSession, current_user: AuthUser) -> str:
    """Resolve the caller's ``users.id`` or 400 (org ops need a real account)."""
    uid = await svc.resolve_user_row_id(session, current_user)
    if not uid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Organization operations require a user account. Service and "
                "master-admin keys have no personal org (per-service-key org "
                "scoping is deferred to BR-2.4)."
            ),
        )
    return uid


async def _require_member(session: AsyncSession, uid: str, org_id: str) -> str:
    role = await svc.get_membership_role(session, uid, org_id)
    if role is None:
        # 404, not 403 — don't reveal the existence of orgs the caller can't see.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return role


async def _require_manager(session: AsyncSession, uid: str, org_id: str) -> str:
    role = await _require_member(session, uid, org_id)
    if not svc.can_manage_org(role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an organization owner or admin can perform this action",
        )
    return role


def _require_active_org(current_user: AuthUser, org_id: str) -> None:
    """Invitation management runs on the RLS-subject session, so the caller must
    be ACTING UNDER the target org (its GUC bound) for the policy to admit the
    row. Tell them to switch if not."""
    if str(current_user.org_id) != str(org_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Set X-Org-Id to this organization to manage its invitations",
        )


# ── org CRUD ────────────────────────────────────────────────────────────────────

@router.post("/orgs", status_code=201)
async def create_org(
    body: CreateOrgRequest,
    session: AsyncSession = Depends(get_session),
    current_user: Annotated[AuthUser, Depends(get_current_user)] = None,
):
    """Create a new organization; the caller becomes its owner."""
    uid = await _uid(session, current_user)
    org = await svc.create_org(session, uid, body.name, body.slug)
    await session.commit()
    logger.info("BR-2.1 org %s created by user %s", org.id, uid)
    out = org.to_dict()
    out["role"] = svc.ORG_ROLE_OWNER
    return out


@router.get("/orgs")
async def list_my_orgs(
    session: AsyncSession = Depends(get_session),
    current_user: Annotated[AuthUser, Depends(get_current_user)] = None,
):
    """List every org the caller belongs to (with their per-org role)."""
    uid = await _uid(session, current_user)
    return {"orgs": await svc.list_user_orgs(session, uid)}


@router.get("/orgs/current")
async def get_active_org(
    session: AsyncSession = Depends(get_session),
    current_user: Annotated[AuthUser, Depends(get_current_user)] = None,
):
    """The org the caller is currently ACTING UNDER (from X-Org-Id or the default
    home org), plus their role in it."""
    if not current_user.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active organization")
    org = await svc.get_org(session, current_user.org_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    out = org.to_dict()
    out["role"] = current_user.org_role
    return out


@router.get("/orgs/{org_id}")
async def get_org(
    org_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: Annotated[AuthUser, Depends(get_current_user)] = None,
):
    """Fetch an org the caller belongs to (any member)."""
    uid = await _uid(session, current_user)
    role = await _require_member(session, uid, org_id)
    org = await svc.get_org(session, org_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    out = org.to_dict()
    out["role"] = role
    return out


@router.patch("/orgs/{org_id}")
async def update_org(
    org_id: str,
    body: UpdateOrgRequest,
    session: AsyncSession = Depends(get_session),
    current_user: Annotated[AuthUser, Depends(get_current_user)] = None,
):
    """Rename an org / change its slug. Owner or admin only."""
    uid = await _uid(session, current_user)
    role = await _require_manager(session, uid, org_id)
    if body.name is None and body.slug is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No updates provided")
    try:
        org = await svc.update_org(session, org_id, name=body.name, slug=body.slug)
    except ValueError as e:
        detail = "Slug already in use" if str(e) == "slug_taken" else "Invalid slug"
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    await session.commit()
    out = org.to_dict()
    out["role"] = role
    return out


@router.get("/orgs/{org_id}/members")
async def list_members(
    org_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: Annotated[AuthUser, Depends(get_current_user)] = None,
):
    """List the members of an org the caller belongs to."""
    uid = await _uid(session, current_user)
    await _require_member(session, uid, org_id)
    return {"members": await svc.list_org_members(session, org_id)}


# ── invitations ─────────────────────────────────────────────────────────────────

@router.post("/orgs/{org_id}/invitations", status_code=201)
async def create_invite(
    org_id: str,
    body: CreateInviteRequest,
    session: AsyncSession = Depends(get_session),
    current_user: Annotated[AuthUser, Depends(get_current_user)] = None,
):
    """Invite an email into the org (owner/admin). Returns the invite incl. its
    one-time token so the caller can deliver it.

    Email delivery is a STUB in BR-2.1: we log the token rather than sending mail.
    Wiring Email-Ops / Postmark to actually send the invite link is a follow-up.
    """
    uid = await _uid(session, current_user)
    await _require_manager(session, uid, org_id)
    _require_active_org(current_user, org_id)
    inv = await svc.create_invitation(
        session, org_id, body.email, role=body.role, invited_by=uid
    )
    await session.commit()
    # --- email send stub -------------------------------------------------------
    logger.info(
        "BR-2.1 EMAIL-STUB: would send invite for org %s to %s (role=%s) — "
        "token=%s… (delivery not yet wired)",
        org_id, inv.email, inv.role, inv.token[:8],
    )
    return {**inv.to_dict(include_token=True), "emailDelivery": "stub"}


@router.get("/orgs/{org_id}/invitations")
async def list_invites(
    org_id: str,
    status_filter: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    current_user: Annotated[AuthUser, Depends(get_current_user)] = None,
):
    """List invitations for the org (owner/admin). Tokens are NOT included."""
    uid = await _uid(session, current_user)
    await _require_manager(session, uid, org_id)
    _require_active_org(current_user, org_id)
    invs = await svc.list_invitations(session, org_id, status=status_filter)
    return {"invitations": [i.to_dict() for i in invs]}


@router.delete("/orgs/{org_id}/invitations/{invitation_id}")
async def revoke_invite(
    org_id: str,
    invitation_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: Annotated[AuthUser, Depends(get_current_user)] = None,
):
    """Revoke a pending invitation (owner/admin)."""
    uid = await _uid(session, current_user)
    await _require_manager(session, uid, org_id)
    _require_active_org(current_user, org_id)
    inv = await svc.revoke_invitation(session, org_id, invitation_id)
    if inv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    await session.commit()
    return inv.to_dict()


@router.post("/orgs/invitations/accept")
async def accept_invite(
    body: AcceptInviteRequest,
    session: AsyncSession = Depends(get_session),
    current_user: Annotated[AuthUser, Depends(get_current_user)] = None,
):
    """Accept an invitation by token — joins the caller to the org (idempotent).

    Runs on ``admin_session`` because the accepting user is not yet a member of
    the target org, so their request-session GUC is bound elsewhere and the
    invitations RLS policy would hide the row (the scheduler's cross-tenant
    precedent).
    """
    uid = await _uid(session, current_user)
    async with admin_session() as s:
        result, inv = await svc.accept_invitation(s, body.token, uid)
        if result in ("ok", "expired"):
            await s.commit()  # persist membership grant / the pending→expired flip
        else:
            await s.rollback()

    if result == "ok":
        return {
            "status": "accepted",
            "orgId": str(inv.org_id),
            "role": inv.role,
            "userId": uid,
        }
    if result == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    if result == "expired":
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Invitation has expired")
    if result == "revoked":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invitation was revoked")
    # already_used
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Invitation has already been used by another account",
    )
