"""BR-2.1 org-lifecycle proof: personal-org auto-provision, invites, per-org roles.

Sibling to prove_org_rls_isolation.py. Drives the REAL app code against an
EPHEMERAL throwaway Postgres:
  * app.db.database.init_db  → create_all + all migrations (incl. the new
    20260717_01_org_invitations RLS table) + provision the NOBYPASSRLS app role.
  * app.db.org_service        → ensure_personal_org / create_org / create_invitation
    / accept_invitation / get_membership_role / update_org (the SAME functions the
    routes call).
  * app.auth.middleware._bind_org_context → the real active-org (X-Org-Id) path.

Then it proves, AS THE NOBYPASSRLS app role, the BR-2.1 scenario:
  A and B each auto-get a personal org; A invites B (member) into A's team org;
  B accepts → B is a member; B can read the team org's data under that org's GUC
  but cannot rename it (owner/admin only); B still cannot see A's OTHER (personal)
  org's data; a non-member sees zero.

Env (set by the caller BEFORE import — engines build at import time):
  MIGRATION_DATABASE_URL  owner/admin DSN (superuser)      — DDL + migrations
  DATABASE_URL            app-role DSN (brigade_app_login)  — RLS-subject runtime

Exit code 0 only if every assertion holds.
"""
import asyncio
import os
import sys
import uuid

from sqlalchemy import text

import app.db.models  # noqa: F401 — registers ORM tables on Base.metadata
from app.db.models import User
from app.db.database import (
    engine,            # runtime app-role engine (DATABASE_URL) — subject to RLS
    migration_engine,  # owner/admin engine (MIGRATION_DATABASE_URL)
    async_session,     # app-role sessionmaker (RLS-subject)
    admin_session,     # owner sessionmaker (RLS-exempt) — cross-tenant work
    init_db,
    provision_app_role,
    verify_app_role_not_bypassing,
)
from app.db import org_service as svc
from app.auth.middleware import _bind_org_context, AuthUser
from app.auth.roles import UserRole
from fastapi import HTTPException

FAILURES = []
PASSES = []


def check(label, condition, detail=""):
    tag = "PASS" if condition else "FAIL"
    (PASSES if condition else FAILURES).append(label)
    print(f"  [{tag}] {label}" + (f"  — {detail}" if detail else ""))


async def set_org(conn, org_id):
    """Exactly what middleware._bind_org_context runs to bind the RLS GUC."""
    await conn.execute(
        text("SELECT set_config('app.current_org_id', :org, false)"), {"org": org_id}
    )


async def write_conversation(org_id, user_label):
    """Insert one conversation into ``org_id`` AS THE APP ROLE bound to it."""
    async with engine.connect() as ac:
        await set_org(ac, org_id)
        cid = str(uuid.uuid4())
        await ac.execute(text(
            "INSERT INTO conversations (id,user_id,org_id,title) "
            "VALUES (:id,:u,:o,:t)"
        ), {"id": cid, "u": user_label, "o": org_id, "t": f"{user_label} conv"})
        await ac.commit()
    return cid


async def count_conversations(org_id):
    async with engine.connect() as ac:
        await set_org(ac, org_id)
        return (await ac.execute(text("SELECT count(*) FROM conversations"))).scalar()


async def main():
    print("=" * 78)
    print("PHASE 0 — init_db as owner; provision + verify NOBYPASSRLS app role")
    print("=" * 78)
    print(f"MIGRATION_DATABASE_URL (owner)   = {os.environ['MIGRATION_DATABASE_URL']}")
    print(f"DATABASE_URL           (app-role)= {os.environ['DATABASE_URL']}")

    await init_db()
    await provision_app_role()
    posture = await verify_app_role_not_bypassing()
    check("runtime role is NOBYPASSRLS brigade_app_login",
          posture and posture["role"] == "brigade_app_login"
          and posture["bypassrls"] is False and posture["super"] is False, str(posture))

    # invitations table exists with RLS ENABLE + FORCE (the new migration).
    async with migration_engine.connect() as oc:
        inv = (await oc.execute(text(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname='invitations'"
        ))).first()
        check("invitations table has RLS ENABLED", bool(inv) and inv[0] is True, str(inv))
        check("invitations table has RLS FORCED", bool(inv) and inv[1] is True, str(inv))

    print("\n" + "=" * 78)
    print("PHASE 1 — Users A, B, C; each auto-gets a PERSONAL org on provision")
    print("=" * 78)
    # Create three users (users has no RLS — owner session, ORM applies defaults).
    a_id = b_id = c_id = None
    async with admin_session() as s:
        ua = User(email="a@example.com", password_hash="x", name="Alice", role="operator", is_active=True)
        ub = User(email="b@example.com", password_hash="x", name="Bob", role="operator", is_active=True)
        uc = User(email="c@example.com", password_hash="x", name="Carol", role="operator", is_active=True)
        s.add_all([ua, ub, uc])
        await s.flush()
        a_id, b_id, c_id = str(ua.id), str(ub.id), str(uc.id)
        # Drive the REAL auto-provision function (signup path).
        oa = await svc.ensure_personal_org(s, a_id, name="Alice", email="a@example.com")
        ob = await svc.ensure_personal_org(s, b_id, name="Bob", email="b@example.com")
        oc_ = await svc.ensure_personal_org(s, c_id, name="Carol", email="c@example.com")
        await s.commit()
        a_home, b_home, c_home = str(oa.id), str(ob.id), str(oc_.id)

    print(f"A={a_id} home={a_home}\nB={b_id} home={b_home}\nC={c_id} home={c_home}")
    check("user A auto-provisioned a personal org", a_home is not None)
    check("user B auto-provisioned a personal org", b_home is not None)
    check("A's and B's personal orgs are distinct", a_home != b_home)

    async with admin_session() as s:
        check("A owns A_home", await svc.get_membership_role(s, a_id, a_home) == "owner")
        check("B owns B_home", await svc.get_membership_role(s, b_id, b_home) == "owner")
        # Idempotent: a second ensure_personal_org creates nothing (already has a home).
        again = await svc.ensure_personal_org(s, a_id, name="Alice", email="a@example.com")
        check("ensure_personal_org is idempotent (no 2nd org for A)", again is None)
        n_a_orgs = len(await svc.list_user_orgs(s, a_id))
        check("A belongs to exactly one org after re-provision", n_a_orgs == 1, f"n={n_a_orgs}")

    print("\n" + "=" * 78)
    print("PHASE 2 — A creates a TEAM org and invites B (member) via token")
    print("=" * 78)
    async with admin_session() as s:
        team = await svc.create_org(s, a_id, "Alice Team")
        await s.commit()
        a_team = str(team.id)
    check("A is owner of the new team org", None is not a_team)
    async with admin_session() as s:
        check("create_org made A owner of the team org",
              await svc.get_membership_role(s, a_id, a_team) == "owner")

    # Seed data in the team org (app role bound to team). Proves the app role writes.
    await write_conversation(a_team, "alice")
    check("app role wrote a conversation into the team org (n=1)",
          await count_conversations(a_team) == 1)

    # Create the invite AS THE APP ROLE bound to the team org (RLS WITH CHECK path):
    # an app-role ORM session bound to the team org, driving the real service fn.
    invite_token = None
    async with async_session() as s:
        await s.execute(text("SELECT set_config('app.current_org_id', :o, false)"), {"o": a_team})
        inv = await svc.create_invitation(s, a_team, "b@example.com", role="member", invited_by=a_id)
        await s.commit()
        invite_token = inv.token
    check("owner created a pending invite for B under the team GUC",
          invite_token is not None)

    # Negative: creating an invite tagged the team org while bound to B_home fails
    # the invitations WITH CHECK (cross-org write blocked by RLS).
    cross_org_blocked = False
    async with async_session() as s:
        await s.execute(text("SELECT set_config('app.current_org_id', :o, false)"), {"o": b_home})
        try:
            await svc.create_invitation(s, a_team, "x@example.com", role="member")
            await s.commit()
        except Exception as e:  # noqa: BLE001
            await s.rollback()
            cross_org_blocked = "row-level security" in str(e).lower() or "violates" in str(e).lower()
    check("cross-org invite INSERT (team-tagged, bound to B_home) blocked by RLS", cross_org_blocked)

    print("\n" + "=" * 78)
    print("PHASE 3 — B accepts the invite (admin_session, cross-tenant) → member")
    print("=" * 78)
    async with admin_session() as s:
        result, inv = await svc.accept_invitation(s, invite_token, b_id)
        await s.commit()
    check("accept_invitation returned ok", result == "ok", result)
    async with admin_session() as s:
        check("B is now a MEMBER of the team org",
              await svc.get_membership_role(s, b_id, a_team) == "member")

    # Idempotent accept: same user, same token → ok, still exactly one membership.
    async with admin_session() as s:
        result2, _ = await svc.accept_invitation(s, invite_token, b_id)
        await s.commit()
    check("re-accepting the same invite is idempotent (ok)", result2 == "ok", result2)
    async with admin_session() as s:
        n = (await s.execute(text(
            "SELECT count(*) FROM org_memberships WHERE user_id=:u AND org_id=:o"
        ), {"u": b_id, "o": a_team})).scalar()
        check("B has exactly ONE membership in the team org (no duplicate)", n == 1, f"n={n}")

    # Expiry: an already-expired invite is refused.
    async with async_session() as s:
        await s.execute(text("SELECT set_config('app.current_org_id', :o, false)"), {"o": a_team})
        expired = await svc.create_invitation(s, a_team, "late@example.com",
                                              role="member", ttl_hours=-1)
        await s.commit()
        expired_token = expired.token
    async with admin_session() as s:
        result3, _ = await svc.accept_invitation(s, expired_token, c_id)
        await s.commit()
    check("an expired invite is refused on accept", result3 == "expired", result3)
    async with admin_session() as s:
        check("expired invite did NOT grant C a membership",
              await svc.get_membership_role(s, c_id, a_team) is None)

    print("\n" + "=" * 78)
    print("PHASE 4 — Per-org roles gate management (owner/admin rename; member cannot)")
    print("=" * 78)
    async with admin_session() as s:
        a_role = await svc.get_membership_role(s, a_id, a_team)
        b_role = await svc.get_membership_role(s, b_id, a_team)
    check("A's role in team org is owner", a_role == "owner", a_role)
    check("B's role in team org is member", b_role == "member", b_role)
    check("owner can_manage_org (rename allowed)", svc.can_manage_org(a_role) is True)
    check("member canNOT manage_org (rename denied)", svc.can_manage_org(b_role) is False)

    # Owner actually renames; the change persists.
    async with admin_session() as s:
        await svc.update_org(s, a_team, name="Alice Team Renamed")
        await s.commit()
    async with admin_session() as s:
        org = await svc.get_org(s, a_team)
        check("owner rename persisted", org.name == "Alice Team Renamed", org.name)

    print("\n" + "=" * 78)
    print("PHASE 5 — RLS: member reads team data under its GUC; not A's OTHER org")
    print("=" * 78)
    # Seed a conversation in A_home (A's PERSONAL org — B is NOT a member here).
    await write_conversation(a_home, "alice-home")

    # (a) Under the TEAM GUC, the team's conversation is visible (n=1). B is
    #     entitled to bind this org, so this is exactly what B reads.
    check("team-org GUC sees the team conversation (n=1)",
          await count_conversations(a_team) == 1)
    # (b) Under B_home GUC, ZERO of A's data (neither team nor personal) is visible.
    check("B_home GUC sees ZERO conversations (none of A's data)",
          await count_conversations(b_home) == 0)
    # (c) Under A_home GUC, only A_home's conversation — team data invisible from here.
    check("A_home GUC sees only A_home's conversation (n=1)",
          await count_conversations(a_home) == 1)

    async with admin_session() as s:
        check("B is NOT a member of A's personal org (cannot reach its data)",
              await svc.get_membership_role(s, b_id, a_home) is None)
        check("non-member C is NOT a member of the team org",
              await svc.get_membership_role(s, c_id, a_team) is None)
    check("non-member C's home GUC sees ZERO team conversations",
          await count_conversations(c_home) == 0)

    print("\n" + "=" * 78)
    print("PHASE 6 — _bind_org_context: real active-org (X-Org-Id) selection")
    print("=" * 78)
    def auth(uid, email):
        return AuthUser(id=uid, role=UserRole.OPERATOR, user_id=uid, email=email,
                        auth_source="keycloak")

    # (a) B requests the team org (valid membership) → bound + role=member, and the
    #     bound session then reads the team org's data.
    async with async_session() as s:
        ub = auth(b_id, "b@example.com")
        await _bind_org_context(ub, s, requested_org_id=a_team)
        n = (await s.execute(text("SELECT count(*) FROM conversations"))).scalar()
    check("B _bind_org_context(X-Org-Id=team) binds team + role=member",
          ub.org_id == a_team and ub.org_role == "member", f"org={ub.org_id} role={ub.org_role}")
    check("B acting under team org reads the team conversation via RLS (n=1)", n == 1, f"n={n}")

    # (b) B requests A's PERSONAL org (no membership) → 403.
    denied = False
    async with async_session() as s:
        try:
            await _bind_org_context(auth(b_id, "b@example.com"), s, requested_org_id=a_home)
        except HTTPException as e:
            denied = e.status_code == 403
    check("B _bind_org_context(X-Org-Id=A_home) is refused (403)", denied)

    # (c) Non-member C requests the team org → 403.
    denied_c = False
    async with async_session() as s:
        try:
            await _bind_org_context(auth(c_id, "c@example.com"), s, requested_org_id=a_team)
        except HTTPException as e:
            denied_c = e.status_code == 403
    check("non-member C _bind_org_context(X-Org-Id=team) is refused (403)", denied_c)

    # (d) B with NO header defaults to B's personal org (owner).
    async with async_session() as s:
        ub2 = auth(b_id, "b@example.com")
        await _bind_org_context(ub2, s, requested_org_id=None)
    check("B _bind_org_context(no header) defaults to personal org as owner",
          ub2.org_id == b_home and ub2.org_role == "owner", f"org={ub2.org_id} role={ub2.org_role}")

    print("\n" + "=" * 78)
    print("PHASE 7 — Brand-new user auto-provisions a personal org ON the app role")
    print("=" * 78)
    # A user with NO org yet (a fresh signup). Its FIRST authenticated request
    # runs _bind_org_context on the NOBYPASSRLS app-role session, which must
    # create the personal org + owner membership itself (organizations /
    # org_memberships carry no RLS, so the app role can write them).
    async with admin_session() as s:
        ud = User(email="d@example.com", password_hash="x", name="Dave",
                  role="operator", is_active=True)
        s.add(ud)
        await s.flush()
        d_id = str(ud.id)
        await s.commit()
        check("new user D starts with ZERO orgs", len(await svc.list_user_orgs(s, d_id)) == 0)

    async with async_session() as s:  # RLS-subject app role
        ud_auth = auth(d_id, "d@example.com")
        await _bind_org_context(ud_auth, s, requested_org_id=None)
    check("D's first request auto-provisioned a personal org (owner) on the app role",
          ud_auth.org_id is not None and ud_auth.org_role == "owner",
          f"org={ud_auth.org_id} role={ud_auth.org_role}")
    async with admin_session() as s:
        orgs = await svc.list_user_orgs(s, d_id)
        check("D now belongs to exactly one (personal) org", len(orgs) == 1, f"n={len(orgs)}")
        check("D's org is flagged personal + owner",
              len(orgs) == 1 and orgs[0]["role"] == "owner"
              and (orgs[0].get("metadata") or {}).get("personal") is True, str(orgs[0]))

    print("\n" + "=" * 78)
    print(f"RESULT: {len(PASSES)} passed, {len(FAILURES)} failed")
    if FAILURES:
        print("FAILURES:")
        for f in FAILURES:
            print(f"   - {f}")
    print("=" * 78)
    await engine.dispose()
    await migration_engine.dispose()
    sys.exit(1 if FAILURES else 0)


if __name__ == "__main__":
    asyncio.run(main())
