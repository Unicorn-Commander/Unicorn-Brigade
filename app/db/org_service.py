"""BR-2.1 org-lifecycle service layer — the multi-USER half of tenancy.

Pure, session-in async functions for the org lifecycle: personal-org
auto-provision, org CRUD, per-org role lookup, active-org resolution, and
invite-by-email create/accept. The API routes (``app/api/org_routes.py``) and
the auth middleware (``app/auth/middleware._bind_org_context``) are thin wrappers
over these; the proof script (``scripts/prove_org_lifecycle.py``) drives the very
same functions, so what is proven is what ships.

Tenancy notes carried by these functions
-----------------------------------------
* ``organizations`` / ``org_memberships`` are the tenancy-DEFINING tables and
  deliberately carry NO RLS (an org cannot be isolated by its own org_id — that
  is circular). Authorization over them is therefore APP-LAYER: every read/write
  is scoped to the caller's memberships by the callers of these functions.
* ``invitations`` DOES carry org-isolation RLS (ENABLE + FORCE). create/list/
  revoke run on the RLS-subject request session (bound to the active org);
  ACCEPT is inherently cross-tenant (the invitee is not a member yet) and must
  run on the RLS-exempt ``admin_session`` — the scheduler's precedent.

None of these functions COMMIT — they ``flush`` so ids populate and compose into
the caller's transaction. Callers own the commit/rollback boundary.
"""
from __future__ import annotations

import re
import uuid
import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Organization, OrgMembership, Invitation, User

logger = logging.getLogger(__name__)

# Per-org role vocabulary. Global (users.role) stays as-is; this is the ADDITIVE
# per-org layer BR-2.1 introduces.
ORG_ROLE_OWNER = "owner"
ORG_ROLE_ADMIN = "admin"
ORG_ROLE_MEMBER = "member"
VALID_ORG_ROLES = (ORG_ROLE_OWNER, ORG_ROLE_ADMIN, ORG_ROLE_MEMBER)
# Roles that may manage the org (rename, invite, revoke). Members are read-only.
MANAGER_ROLES = (ORG_ROLE_OWNER, ORG_ROLE_ADMIN)

# Default invitation lifetime (7 days).
INVITE_TTL_HOURS = 168


# ── slug helpers ───────────────────────────────────────────────────────────────

def slugify(value: str) -> str:
    """Lowercase, ascii, hyphenated slug fragment (<=48 chars). Empty on junk."""
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value[:48]


async def unique_org_slug(session: AsyncSession, base: str) -> str:
    """A slug not currently taken. Tries ``base``, ``base-2`` … then a uuid tail.

    ``organizations.slug`` is UNIQUE, so two users whose emails share a local part
    (alice@x / alice@y) can't both be 'alice' — the numeric suffix (then the uuid
    fallback) keeps it collision-free without failing the insert.
    """
    base = slugify(base) or "org"
    for i in range(0, 50):
        candidate = base if i == 0 else f"{base}-{i + 1}"
        exists = await session.execute(
            select(Organization.id).where(Organization.slug == candidate)
        )
        if exists.scalar_one_or_none() is None:
            return candidate
    return f"{base}-{uuid.uuid4().hex[:8]}"


def _personal_org_name(name: Optional[str], email: Optional[str]) -> str:
    label = (name or "").strip() or (email or "").strip() or "My"
    return f"{label}'s Brigade"


# ── personal-org auto-provision ─────────────────────────────────────────────────

async def ensure_personal_org(
    session: AsyncSession,
    user_id: str,
    *,
    name: Optional[str] = None,
    email: Optional[str] = None,
) -> Optional[Organization]:
    """Guarantee the user has a home org, creating a personal one if they have NONE.

    Founder-default (Aaron pre-approved): every user gets a personal org on
    signup, owner role. Idempotent + conservative: if the user ALREADY has any
    membership (e.g. an existing user backfilled into the shared 'early-access'
    org by migration 20260626_01), we do NOT mint a second org — that would hide
    the data they already accreted under their current home. Returns the org that
    was created, or None when the user already had a home.

    Safe on the request session: organizations/org_memberships carry no RLS, and
    this runs before the GUC is bound, so no policy is in play.
    """
    existing = await session.execute(
        select(OrgMembership.id).where(OrgMembership.user_id == user_id).limit(1)
    )
    if existing.scalar_one_or_none() is not None:
        return None

    base = (email.split("@")[0] if email else None) or name or "user"
    slug = await unique_org_slug(session, base)
    org = Organization(
        name=_personal_org_name(name, email),
        slug=slug,
        plan_tier="free",
        api_calls_limit=0,
        metadata_={"personal": True},
    )
    session.add(org)
    await session.flush()  # populate org.id
    session.add(OrgMembership(org_id=org.id, user_id=user_id, role=ORG_ROLE_OWNER))
    await session.flush()
    logger.info("BR-2.1 provisioned personal org %s (slug=%s) for user %s",
                org.id, org.slug, user_id)
    return org


# ── membership / role reads ─────────────────────────────────────────────────────

async def get_membership_role(
    session: AsyncSession, user_id: str, org_id: str
) -> Optional[str]:
    """The caller's per-org role in ``org_id``, or None if not a member.

    This is the per-org authz primitive BR-2.1 adds: routes gate owner/admin-only
    actions on ``get_membership_role(...) in MANAGER_ROLES``.
    """
    r = await session.execute(
        select(OrgMembership.role).where(
            OrgMembership.user_id == user_id,
            OrgMembership.org_id == org_id,
        )
    )
    return r.scalar_one_or_none()


def can_manage_org(role: Optional[str]) -> bool:
    """Owner/admin may rename the org, invite, and revoke. Member is read-only."""
    return role in MANAGER_ROLES


async def resolve_home_org(
    session: AsyncSession, user_id: str
) -> Optional[tuple[str, str]]:
    """The user's DEFAULT active org as ``(org_id, role)``, or None if orgless.

    Prefers the personal org (``metadata.personal == true``) so a user who also
    belongs to team orgs still lands in their own space by default; otherwise the
    earliest membership (which, for a backfilled user, is the 'early-access' org
    that holds their existing data).
    """
    rows = (await session.execute(
        select(OrgMembership.org_id, OrgMembership.role, Organization.metadata_)
        .join(Organization, Organization.id == OrgMembership.org_id)
        .where(OrgMembership.user_id == user_id)
        .order_by(OrgMembership.created_at.asc())
    )).all()
    if not rows:
        return None
    for org_id, role, meta in rows:
        if isinstance(meta, dict) and meta.get("personal"):
            return str(org_id), role
    org_id, role, _ = rows[0]
    return str(org_id), role


async def list_user_orgs(session: AsyncSession, user_id: str) -> list[dict]:
    """Every org the caller belongs to, each annotated with their role."""
    rows = (await session.execute(
        select(Organization, OrgMembership.role)
        .join(OrgMembership, OrgMembership.org_id == Organization.id)
        .where(OrgMembership.user_id == user_id)
        .order_by(OrgMembership.created_at.asc())
    )).all()
    out = []
    for org, role in rows:
        d = org.to_dict()
        d["role"] = role
        out.append(d)
    return out


async def list_org_members(session: AsyncSession, org_id: str) -> list[dict]:
    """Members of ``org_id`` with their user email/name + per-org role."""
    rows = (await session.execute(
        select(OrgMembership, User)
        .join(User, User.id == OrgMembership.user_id)
        .where(OrgMembership.org_id == org_id)
        .order_by(OrgMembership.created_at.asc())
    )).all()
    out = []
    for m, user in rows:
        out.append({
            "userId": str(user.id),
            "email": user.email,
            "name": user.name,
            "role": m.role,
            "joinedAt": m.created_at.isoformat() + "Z" if m.created_at else None,
        })
    return out


# ── org CRUD ────────────────────────────────────────────────────────────────────

async def get_org(session: AsyncSession, org_id: str) -> Optional[Organization]:
    r = await session.execute(select(Organization).where(Organization.id == org_id))
    return r.scalar_one_or_none()


async def create_org(
    session: AsyncSession,
    owner_user_id: str,
    name: str,
    slug: Optional[str] = None,
    plan_tier: str = "free",
) -> Organization:
    """Create a team org and make the caller its owner. Slug is derived + uniqued."""
    final_slug = await unique_org_slug(session, slug or name)
    org = Organization(
        name=name.strip(),
        slug=final_slug,
        plan_tier=plan_tier,
        api_calls_limit=0,
        metadata_={},
    )
    session.add(org)
    await session.flush()
    session.add(OrgMembership(org_id=org.id, user_id=owner_user_id, role=ORG_ROLE_OWNER))
    await session.flush()
    return org


async def update_org(
    session: AsyncSession,
    org_id: str,
    name: Optional[str] = None,
    slug: Optional[str] = None,
) -> Optional[Organization]:
    """Rename an org and/or change its slug. Returns None if the org is gone.

    Raises ValueError('slug_taken') when the requested slug is used by ANOTHER org.
    """
    org = await get_org(session, org_id)
    if org is None:
        return None
    if name is not None:
        org.name = name.strip()
    if slug is not None:
        s = slugify(slug)
        if not s:
            raise ValueError("invalid_slug")
        clash = await session.execute(
            select(Organization.id).where(
                Organization.slug == s, Organization.id != org_id
            )
        )
        if clash.scalar_one_or_none() is not None:
            raise ValueError("slug_taken")
        org.slug = s
    org.updated_at = datetime.utcnow()
    await session.flush()
    return org


# ── invitations ─────────────────────────────────────────────────────────────────

async def create_invitation(
    session: AsyncSession,
    org_id: str,
    email: str,
    role: str = ORG_ROLE_MEMBER,
    invited_by: Optional[str] = None,
    ttl_hours: int = INVITE_TTL_HOURS,
) -> Invitation:
    """Mint a pending, expiring invite bearing a fresh secret token.

    ``owner`` is never invitable (an org has exactly the one owner who created
    it); anything outside {admin, member} is clamped to member. Runs on the
    RLS-subject request session bound to ``org_id`` → WITH CHECK passes.
    """
    role = role if role in (ORG_ROLE_ADMIN, ORG_ROLE_MEMBER) else ORG_ROLE_MEMBER
    inv = Invitation(
        org_id=org_id,
        email=(email or "").strip().lower(),
        role=role,
        token=secrets.token_urlsafe(32),
        status="pending",
        invited_by=invited_by,
        expires_at=datetime.utcnow() + timedelta(hours=ttl_hours),
    )
    session.add(inv)
    await session.flush()
    return inv


async def list_invitations(
    session: AsyncSession, org_id: str, status: Optional[str] = None
) -> list[Invitation]:
    q = select(Invitation).where(Invitation.org_id == org_id)
    if status:
        q = q.where(Invitation.status == status)
    q = q.order_by(Invitation.created_at.desc())
    return list((await session.execute(q)).scalars().all())


async def revoke_invitation(
    session: AsyncSession, org_id: str, invitation_id: str
) -> Optional[Invitation]:
    """Revoke a still-pending invite. Returns the invite, or None if not found."""
    r = await session.execute(
        select(Invitation).where(
            Invitation.id == invitation_id, Invitation.org_id == org_id
        )
    )
    inv = r.scalar_one_or_none()
    if inv is None:
        return None
    if inv.status == "pending":
        inv.status = "revoked"
        inv.updated_at = datetime.utcnow()
        await session.flush()
    return inv


async def accept_invitation(
    session: AsyncSession, token: str, user_id: str
) -> tuple[str, Optional[Invitation]]:
    """Accept an invite by token, minting an OrgMembership for ``user_id``.

    Returns ``(status, invitation)`` where status is one of:
      ok | not_found | expired | revoked | already_used

    Idempotent: a second accept by the SAME user returns ``ok`` without creating
    a duplicate membership (org_memberships has a UNIQUE(org_id,user_id)). Expiry
    is checked and flips a stale pending invite to 'expired'.

    MUST run on a cross-tenant session (``admin_session``): the invitee is not yet
    a member of the org, so their request-session GUC is bound to a DIFFERENT org
    and the invitations RLS policy would hide this row.
    """
    r = await session.execute(select(Invitation).where(Invitation.token == token))
    inv = r.scalar_one_or_none()
    if inv is None:
        return "not_found", None

    now = datetime.utcnow()

    if inv.status == "revoked":
        return "revoked", inv
    if inv.status == "expired":
        return "expired", inv
    if inv.status == "pending" and inv.expires_at is not None and inv.expires_at < now:
        inv.status = "expired"
        inv.updated_at = now
        await session.flush()
        return "expired", inv

    already = await get_membership_role(session, user_id, str(inv.org_id))

    if inv.status == "accepted":
        # Idempotent for the same accepting user; a different user replaying a
        # consumed token is refused.
        if already is not None and str(inv.accepted_by) == str(user_id):
            return "ok", inv
        return "already_used", inv

    # pending + unexpired → grant membership (idempotent on the unique constraint)
    if already is None:
        session.add(OrgMembership(org_id=inv.org_id, user_id=user_id, role=inv.role))
    inv.status = "accepted"
    inv.accepted_by = user_id
    inv.accepted_at = now
    inv.updated_at = now
    await session.flush()
    logger.info("BR-2.1 invite %s accepted by user %s into org %s (role=%s)",
                inv.id, user_id, inv.org_id, inv.role)
    return "ok", inv


async def resolve_user_row_id(session: AsyncSession, auth_user) -> Optional[str]:
    """Map an ``AuthUser`` onto its ``users.id``, or None for keyless identities.

    Mirrors user_routes._resolve_db_user_id: AuthUser.user_id is already the
    canonical users.id for keycloak/session/user-API-key auth; otherwise fall
    back to an email match. The master-admin key ("admin") and agent service keys
    have no users row → None (org ops require a real user account).
    """
    candidate = str(getattr(auth_user, "user_id", None) or auth_user.id or "")
    try:
        uuid.UUID(candidate)
        row = await session.execute(select(User.id).where(User.id == candidate))
        found = row.scalar_one_or_none()
        if found:
            return str(found)
    except (ValueError, TypeError):
        pass
    if getattr(auth_user, "email", None):
        row = await session.execute(
            select(User.id).where(User.email == auth_user.email.lower())
        )
        found = row.scalar_one_or_none()
        if found:
            return str(found)
    return None
