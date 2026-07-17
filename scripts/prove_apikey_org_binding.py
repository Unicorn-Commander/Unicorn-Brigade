"""BR-2.4 / H1 per-key org-binding isolation proof.

Drives the REAL app code end-to-end against an EPHEMERAL throwaway Postgres:
  * app.db.database.init_db  → create_all + the 20260718_01_api_key_org_binding
    migration (adds api_keys.org_id + backfill) + provision_app_role + verify.
  * app.auth.middleware.validate_api_key + _bind_org_context — the EXACT per-request
    auth+org-bind path get_current_user runs — resolving a raw API key to its org.
  * app.db.repositories.ApiKeyRepository.generate — the creation path that stamps
    the creating user's active org onto a new key.

Proves the H1 gap is CLOSED: a service/agent API key now binds the request's RLS
org (app.current_org_id) to the KEY's own org_id, so two customers' keys are
isolated instead of both collapsing onto the shared 'early-access' org.

Required assertions:
  (a) a request authenticated with key A resolves current_org_id() = org A
  (b) key A cannot read org B's rows (and vice-versa) — enforced by RLS
  (c) the admin/master key is UNCHANGED (binds early-access, not a tenant org) and
      the owner/admin session still sees ACROSS orgs (RLS-exempt system reach)

Env (set by the caller BEFORE import — engines are built at import time):
  MIGRATION_DATABASE_URL  owner/admin DSN (superuser)       — DDL + migrations
  DATABASE_URL            app-role DSN (brigade_app_login)   — RLS-subject runtime
  BRIGADE_ADMIN_KEY       master-admin key (raw)             — the (c) admin path

Exit code 0 only if every assertion holds.
"""
import asyncio
import hashlib
import os
import sys
import uuid

from sqlalchemy import text

# Import order matters: env is already set by the shell. Importing the modules
# builds `engine` (app-role) + `migration_engine` (owner) from those env vars.
import app.db.models  # noqa: F401  — registers all ORM tables on Base.metadata
from app.db.database import (
    engine,            # runtime app-role engine (DATABASE_URL) — subject to RLS
    migration_engine,  # owner/admin engine (MIGRATION_DATABASE_URL)
    async_session,     # app-role sessionmaker (a "request" session)
    init_db,
    provision_app_role,
    verify_app_role_not_bypassing,
    verify_owner_role_bypasses_rls,
)
# The REAL per-request auth + org-bind path.
from app.auth.middleware import validate_api_key, _bind_org_context
from app.auth.roles import UserRole
from app.db.repositories import ApiKeyRepository

ORG_A = str(uuid.uuid4())
ORG_B = str(uuid.uuid4())
FAILURES = []
PASSES = []


def check(label, condition, detail=""):
    tag = "PASS" if condition else "FAIL"
    (PASSES if condition else FAILURES).append(label)
    print(f"  [{tag}] {label}" + (f"  — {detail}" if detail else ""))


def sha256(raw):
    return hashlib.sha256(raw.encode()).hexdigest()


async def scalar(conn, statement, **params):
    return (await conn.execute(text(statement), params)).scalar()


async def resolve_via_middleware(raw_key):
    """Open a fresh app-role session and run the EXACT code get_current_user runs
    per request: validate_api_key → _bind_org_context. Returns (auth_user, session);
    caller reads current_org_id()/rows on the SAME session (RLS applies), then
    closes it. This drives the real middleware, not a re-implementation."""
    session = async_session()
    try:
        user = await validate_api_key(raw_key, session)
        if user is not None:
            await _bind_org_context(user, session, None)
        return user, session
    except Exception:
        await session.close()
        raise


async def main():
    print("=" * 78)
    print("PHASE 0 — init_db as owner; migration adds api_keys.org_id; verify roles")
    print("=" * 78)
    print(f"MIGRATION_DATABASE_URL (owner)    = {os.environ['MIGRATION_DATABASE_URL']}")
    print(f"DATABASE_URL           (app-role) = {os.environ['DATABASE_URL']}")
    print(f"migration_engine is engine? {migration_engine is engine} (expect False)")

    await init_db()  # create_all + all migrations (incl. 20260718_01) + provision
    await provision_app_role()
    posture = await verify_app_role_not_bypassing()
    check("runtime connects as brigade_app_login (RLS-subject)",
          bool(posture) and posture["role"] == "brigade_app_login", str(posture))
    check("runtime role rolbypassrls = false", bool(posture) and posture["bypassrls"] is False)
    check("runtime role rolsuper = false", bool(posture) and posture["super"] is False)
    owner_posture = await verify_owner_role_bypasses_rls()
    check("owner/migration role BYPASSES RLS (system cross-org reach)",
          bool(owner_posture) and (owner_posture["super"] or owner_posture["bypassrls"]),
          str(owner_posture))

    # Schema posture: api_keys.org_id EXISTS, api_keys has NO RLS (key lookup must
    # work pre-bind), and the FK to organizations is present.
    async with migration_engine.connect() as oc:
        has_col = await scalar(oc,
            "SELECT count(*) FROM information_schema.columns "
            "WHERE table_name='api_keys' AND column_name='org_id'")
        check("api_keys.org_id column exists (migration applied)", has_col == 1, f"count={has_col}")

        akrls = (await oc.execute(text(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname='api_keys'"
        ))).first()
        check("api_keys has NO RLS (key lookup runs before org is bound)",
              bool(akrls) and akrls[0] is False and akrls[1] is False,
              f"rowsecurity={akrls[0] if akrls else None} force={akrls[1] if akrls else None}")

        has_fk = await scalar(oc,
            "SELECT count(*) FROM pg_constraint WHERE conname='fk_api_keys_org_id_organizations'")
        check("api_keys.org_id FK → organizations exists", has_fk == 1, f"count={has_fk}")

        has_idx = await scalar(oc,
            "SELECT count(*) FROM pg_indexes WHERE indexname='ix_api_keys_org_id'")
        check("ix_api_keys_org_id index exists", has_idx == 1, f"count={has_idx}")

        ea = await scalar(oc, "SELECT id FROM organizations WHERE slug='early-access'")
    EARLY_ACCESS = str(ea)
    print(f"early-access org id = {EARLY_ACCESS}")

    print("\n" + "=" * 78)
    print("PHASE 1 — Seed org A + org B, each with one agent + one org-bound API key")
    print("=" * 78)
    raw_a = f"ubk-proofA-{uuid.uuid4().hex}"
    raw_b = f"ubk-proofB-{uuid.uuid4().hex}"
    key_a_id, key_b_id = "keyaproof0000001", "keybproof0000001"
    # Seed via the OWNER: agents is FORCE-RLS (owner is the sanctioned seed path);
    # api_keys has no RLS but its agent_id FK needs the agents to exist first.
    async with migration_engine.begin() as oc:
        for oid, slug in ((ORG_A, "org-a"), (ORG_B, "org-b")):
            await oc.execute(text(
                "INSERT INTO organizations (id,name,slug,plan_tier,api_calls_limit,metadata) "
                "VALUES (:id,:n,:s,'free',0,'{}'::json)"
            ), {"id": oid, "n": slug, "s": slug})
        await oc.execute(text(
            "INSERT INTO agents (id,name,org_id) VALUES ('agent-a','Agent A',:o)"), {"o": ORG_A})
        await oc.execute(text(
            "INSERT INTO agents (id,name,org_id) VALUES ('agent-b','Agent B',:o)"), {"o": ORG_B})
        for kid, agent, org, prefix, h in (
            (key_a_id, "agent-a", ORG_A, raw_a[:8], sha256(raw_a)),
            (key_b_id, "agent-b", ORG_B, raw_b[:8], sha256(raw_b)),
        ):
            await oc.execute(text(
                "INSERT INTO api_keys (id,agent_id,org_id,name,key_prefix,key_hash,permissions,rate_limit,is_active) "
                "VALUES (:id,:agent,:org,:name,:prefix,:hash,'[\"chat\",\"read\"]'::json,100,true)"
            ), {"id": kid, "agent": agent, "org": org, "name": f"key for {agent}",
                "prefix": prefix, "hash": h})
    print(f"orgs: A={ORG_A} B={ORG_B}")
    print(f"key A → org A ({raw_a[:12]}…), key B → org B ({raw_b[:12]}…)")

    print("\n" + "=" * 78)
    print("PHASE 2(a) — Key A resolves current_org_id() = ORG A (real middleware)")
    print("=" * 78)
    user_a, sess_a = await resolve_via_middleware(raw_a)
    try:
        check("key A validated to an AuthUser", user_a is not None)
        check("key A AuthUser.key_org_id == ORG A (carried from api_keys.org_id)",
              bool(user_a) and user_a.key_org_id == ORG_A, f"key_org_id={getattr(user_a,'key_org_id',None)}")
        check("key A AuthUser.org_id bound to ORG A", bool(user_a) and user_a.org_id == ORG_A,
              f"org_id={getattr(user_a,'org_id',None)}")
        guc_a = await scalar(sess_a, "SELECT current_org_id()")
        check("(a) current_org_id() = ORG A on key A's request session",
              str(guc_a) == ORG_A, f"current_org_id()={guc_a}")
        # Write a row as org A (RLS WITH CHECK passes because GUC = A).
        conv_a = str(uuid.uuid4())
        await sess_a.execute(text(
            "INSERT INTO conversations (id,user_id,org_id,title) VALUES (:id,'user-a',:o,'A conv')"
        ), {"id": conv_a, "o": ORG_A})
        await sess_a.commit()
    finally:
        await sess_a.close()

    print("\n" + "=" * 78)
    print("PHASE 2(b) — Key B sees ZERO of A's rows; key A cannot read B's rows")
    print("=" * 78)
    # Key B writes its own conversation.
    user_b, sess_b = await resolve_via_middleware(raw_b)
    try:
        check("key B AuthUser.org_id bound to ORG B", bool(user_b) and user_b.org_id == ORG_B,
              f"org_id={getattr(user_b,'org_id',None)}")
        guc_b = await scalar(sess_b, "SELECT current_org_id()")
        check("current_org_id() = ORG B on key B's request session", str(guc_b) == ORG_B, f"guc={guc_b}")
        conv_b = str(uuid.uuid4())
        await sess_b.execute(text(
            "INSERT INTO conversations (id,user_id,org_id,title) VALUES (:id,'user-b',:o,'B conv')"
        ), {"id": conv_b, "o": ORG_B})
        await sess_b.commit()
        # Under key B, A's conversation is invisible.
        n_b = await scalar(sess_b, "SELECT count(*) FROM conversations")
        check("(b) key B sees exactly its OWN 1 conversation (A's is invisible)", n_b == 1, f"count={n_b}")
        seen_a_under_b = await scalar(sess_b,
            "SELECT count(*) FROM conversations WHERE id=:id", id=conv_a)
        check("(b) key B CANNOT read org A's row", seen_a_under_b == 0, f"visible={seen_a_under_b}")
        # WITH CHECK: bound to B, cannot write a row tagged org A.
        try:
            await sess_b.execute(text(
                "INSERT INTO conversations (id,user_id,org_id,title) VALUES (:id,'evil',:o,'x')"
            ), {"id": str(uuid.uuid4()), "o": ORG_A})
            await sess_b.commit()
            check("(b) cross-org write (org A row under key B) rejected", False, "INSERT SUCCEEDED (LEAK!)")
        except Exception as e:
            await sess_b.rollback()
            check("(b) cross-org write (org A row under key B) rejected by RLS WITH CHECK",
                  "row-level security" in str(e).lower() or "violates" in str(e).lower(),
                  type(e).__name__)
    finally:
        await sess_b.close()

    # Symmetric: key A cannot read B's row.
    user_a2, sess_a2 = await resolve_via_middleware(raw_a)
    try:
        n_a = await scalar(sess_a2, "SELECT count(*) FROM conversations")
        check("(b) key A sees exactly its OWN 1 conversation (B's is invisible)", n_a == 1, f"count={n_a}")
        seen_b_under_a = await scalar(sess_a2,
            "SELECT count(*) FROM conversations WHERE id=:id", id=conv_b)
        check("(b) key A CANNOT read org B's row", seen_b_under_a == 0, f"visible={seen_b_under_a}")
    finally:
        await sess_a2.close()

    print("\n" + "=" * 78)
    print("PHASE 2(c) — Master-admin key UNCHANGED (early-access); owner sees ACROSS orgs")
    print("=" * 78)
    master_raw = os.environ.get("BRIGADE_ADMIN_KEY", "")
    check("BRIGADE_ADMIN_KEY is set for the admin-path assertion", bool(master_raw))
    user_adm, sess_adm = await resolve_via_middleware(master_raw)
    try:
        check("master-admin key validated to an ADMIN AuthUser",
              bool(user_adm) and user_adm.role == UserRole.ADMIN, f"role={getattr(user_adm,'role',None)}")
        check("master-admin key has NO per-key org binding (key_org_id is None)",
              bool(user_adm) and user_adm.key_org_id is None, f"key_org_id={getattr(user_adm,'key_org_id',None)}")
        # Admin path UNCHANGED: binds the shared early-access org, NOT a tenant org.
        check("master-admin key binds early-access (NOT ORG A/B) — admin path preserved",
              bool(user_adm) and user_adm.org_id == EARLY_ACCESS and user_adm.org_id not in (ORG_A, ORG_B),
              f"org_id={getattr(user_adm,'org_id',None)}")
    finally:
        await sess_adm.close()

    # (c) Cross-org reach is via the RLS-EXEMPT owner/admin session (the documented
    # mechanism trusted admin/system work uses — scheduler, identity remap). It sees
    # BOTH orgs' api_keys and conversations; the RLS-subject app role never can.
    async with migration_engine.connect() as oc:
        n_keys = await scalar(oc, "SELECT count(*) FROM api_keys WHERE org_id IN (:a,:b)", a=ORG_A, b=ORG_B)
        n_conv = await scalar(oc, "SELECT count(*) FROM conversations WHERE org_id IN (:a,:b)", a=ORG_A, b=ORG_B)
        distinct_orgs = await scalar(oc,
            "SELECT count(DISTINCT org_id) FROM api_keys WHERE org_id IN (:a,:b)", a=ORG_A, b=ORG_B)
    check("(c) owner/admin session enumerates api_keys across BOTH orgs (n>=2)", n_keys >= 2, f"n={n_keys}")
    check("(c) owner/admin session enumerates conversations across BOTH orgs (n>=2)", n_conv >= 2, f"n={n_conv}")
    check("(c) owner/admin session spans 2 distinct orgs (cross-org reach)", distinct_orgs == 2, f"n={distinct_orgs}")

    print("\n" + "=" * 78)
    print("PHASE 3 — Creation-stamp path: ApiKeyRepository.generate stamps active org")
    print("=" * 78)
    # Drive the REAL creation path (what apikey_routes calls) on a session bound to
    # ORG A, passing the caller's active org. Then auth with the new key and prove it
    # resolves to ORG A end-to-end (create → authenticate → isolate).
    sess_make = async_session()
    new_raw = None
    try:
        await sess_make.execute(
            text("SELECT set_config('app.current_org_id', :o, false)"), {"o": ORG_A})
        repo = ApiKeyRepository(sess_make)
        made = await repo.generate("agent-a", {"name": "stamped key", "permissions": ["chat", "read"]},
                                   org_id=ORG_A)
        new_raw = made["key"]
        check("generate() stamped the new key with ORG A", made.get("orgId") == ORG_A,
              f"orgId={made.get('orgId')}")
    finally:
        await sess_make.close()

    user_n, sess_n = await resolve_via_middleware(new_raw)
    try:
        guc_n = await scalar(sess_n, "SELECT current_org_id()")
        check("newly-created key authenticates and resolves current_org_id() = ORG A",
              bool(user_n) and user_n.org_id == ORG_A and str(guc_n) == ORG_A,
              f"org_id={getattr(user_n,'org_id',None)} guc={guc_n}")
    finally:
        await sess_n.close()

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
