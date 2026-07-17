"""BR-1.1 (P-00129) — canonical user_id unification tests.

Runs entirely against a THROWAWAY SQLite DB created under a temp dir — it never
touches prod/dogfood Postgres. Exercises the two halves of BR-1.1:

  * ``remap_forked_keycloak_rows`` — the batch migration SQL (portable form that
    prod runs on Postgres), proving forked rows unify with no data loss and that
    a re-run is a no-op (idempotent).
  * ``resolve_canonical_user_id`` — the middleware resolver, proving a Keycloak
    principal and a personal API key resolve to the SAME local ``users.id`` for
    one human, that the legacy email-keyed row is claimed by its sub, and that
    the collision / brand-new-user edges behave.
  * ``GraphitiMemoryManager._read_group_ids`` — the memory dual-read alias,
    proving a cutover SSO user's pre-BR-1.1 agent memory (keyed by the raw sub)
    stays reachable: retrieval reads BOTH the canonical ``{local_id}__{agent}``
    and legacy ``{sub}__{agent}`` namespaces while writes stay canonical-only.
    Pure string logic — needs no Graphiti/FalkorDB, so it runs in this env.

Run directly:  python -m app.tests.test_br11_identity_canonical
Or via pytest: pytest app/tests/test_br11_identity_canonical.py
"""

import asyncio
import os
import tempfile
import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.database import Base
from app.db.models import BuilderSession, Conversation, User
from app.db.migrations import remap_forked_keycloak_rows
from app.auth.middleware import resolve_canonical_user_id


async def _fresh_db():
    """Create a throwaway on-disk SQLite DB with the full schema. Returns
    (engine, sessionmaker, path). Caller disposes + unlinks."""
    fd, path = tempfile.mkstemp(prefix="br11_scratch_", suffix=".sqlite")
    os.close(fd)
    engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False), path


async def _count(session, table):
    r = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
    return r.scalar_one()


def _norm(v):
    """Canonicalize an id for comparison. The throwaway SQLite renders the
    postgresql.UUID type asymmetrically (ORM -> dashed, raw SQL -> no dashes);
    on prod Postgres both forms are the identical canonical dashed string. Fold
    UUID formatting so we compare identity, not text. Non-UUIDs
    ('anonymous', downstream pass-through ids) pass through untouched."""
    try:
        return str(uuid.UUID(str(v)))
    except (ValueError, TypeError):
        return v


async def _scenario_batch_remap(log):
    """Two synthetic identities that fork today unify via the batch migration."""
    engine, Session, path = await _fresh_db()
    try:
        kc_sub = str(uuid.uuid4())          # the Keycloak sub (distinct from local id)
        downstream = "projops-passthrough-42"  # opaque downstream id, must survive

        async with Session() as s:
            # Legacy email-keyed row (auto-provisioned pre-BR-1.1: no keycloak_id).
            u = User(email="alice@x.com", name="alice",
                     password_hash="NOLOGIN-SSO-ONLY", role="operator",
                     apps=[], is_active=True)
            s.add(u)
            await s.commit()
        async with Session() as s:
            # The canonical id is whatever the DB stores — the value the API-key
            # path (a fresh SELECT then str(user.id)) and the remap (SELECT u.id)
            # both key on. Read it fresh, exactly like the real auth paths do.
            local_id = str((await s.execute(select(User))).scalar_one().id)

        async with Session() as s:
            # Forked ownership: one conv written by the KC-bearer path (user_id =
            # sub), one by the API-key path (user_id = local id) — SAME human.
            s.add(Conversation(id=str(uuid.uuid4()), user_id=kc_sub, title="via-sso"))
            s.add(Conversation(id=str(uuid.uuid4()), user_id=local_id, title="via-apikey"))
            s.add(Conversation(id=str(uuid.uuid4()), user_id="anonymous", title="anon"))
            s.add(Conversation(id=str(uuid.uuid4()), user_id=downstream, title="downstream"))
            s.add(BuilderSession(id=str(uuid.uuid4()), user_id=kc_sub))
            await s.commit()

        total_before = None
        async with Session() as s:
            total_before = (await _count(s, "conversations"),
                            await _count(s, "builder_sessions"))
            # Prove the API-key path (str(user.id)) agrees with the remap's
            # SELECT-id source — the invariant BR-1.1 relies on.
            raw_id = (await s.execute(text("SELECT id FROM users"))).scalar_one()
            assert _norm(raw_id) == _norm(local_id), "str(user.id) must equal the stored users.id"
            # A login (or operator backfill) has stamped keycloak_id = sub.
            u = (await s.execute(select(User).where(User.id == local_id))).scalar_one()
            u.keycloak_id = kc_sub
            await s.commit()

        # Run the batch migration exactly as prod would.
        async with Session() as s:
            await remap_forked_keycloak_rows(s)
            await s.commit()

        async with Session() as s:
            rows = (await s.execute(select(Conversation.title, Conversation.user_id))).all()
            by_title = {t: uid for t, uid in rows}
            bsub = (await s.execute(select(BuilderSession.user_id))).scalars().all()
            total_after = (await _count(s, "conversations"),
                           await _count(s, "builder_sessions"))

        assert _norm(by_title["via-sso"]) == _norm(local_id), "sub-keyed conv must remap to local id"
        assert _norm(by_title["via-apikey"]) == _norm(local_id), "already-canonical conv unchanged"
        assert by_title["anon"] == "anonymous", "'anonymous' must be untouched"
        assert by_title["downstream"] == downstream, "downstream pass-through must survive"
        assert [_norm(x) for x in bsub] == [_norm(local_id)], "builder session sub-keyed row must remap"
        assert total_before == total_after, "no rows created or lost"
        assert _norm(by_title["via-sso"]) == _norm(by_title["via-apikey"]), "the fork is unified"

        # Idempotency: a second pass changes nothing.
        async with Session() as s:
            await remap_forked_keycloak_rows(s)
            await s.commit()
        async with Session() as s:
            rows2 = (await s.execute(select(Conversation.title, Conversation.user_id))).all()
        assert {t: u for t, u in rows2} == by_title, "remap must be idempotent"

        log.append(f"[batch] local_id={local_id[:8]} sub={kc_sub[:8]} -> unified; "
                   f"downstream+anon preserved; idempotent OK")
    finally:
        await engine.dispose()
        os.unlink(path)


async def _scenario_resolver(log):
    """KC-bearer and API-key resolve to the SAME local id; claim + edges."""
    engine, Session, path = await _fresh_db()
    try:
        kc_sub = str(uuid.uuid4())

        async with Session() as s:
            u = User(email="bob@x.com", name="bob",
                     password_hash="NOLOGIN-SSO-ONLY", role="viewer",
                     apps=["librechat"], is_active=True)  # keycloak_id NULL
            s.add(u)
            await s.commit()
        async with Session() as s:
            local_id = str((await s.execute(select(User))).scalar_one().id)
        async with Session() as s:
            s.add(Conversation(id=str(uuid.uuid4()), user_id=kc_sub, title="bob-sso"))
            await s.commit()

        # KC-bearer path resolves the canonical id.
        async with Session() as s:
            kc_resolved = await resolve_canonical_user_id(
                s, kc_sub=kc_sub, email="Bob@x.com",   # mixed case → normalized
                derived_apps=["projectops"], realm_role="operator")

        # API-key path id is simply str(users.id).
        async with Session() as s:
            u = (await s.execute(select(User).where(User.email == "bob@x.com"))).scalar_one()
            apikey_id = str(u.id)
            claimed_sub = u.keycloak_id
            merged_apps = u.apps
            synced_role = u.role
            conv_owner = (await s.execute(
                select(Conversation.user_id).where(Conversation.title == "bob-sso"))
            ).scalar_one()

        assert _norm(kc_resolved) == _norm(local_id), "resolver must return the local users.id, not the sub"
        assert _norm(kc_resolved) == _norm(apikey_id), "KC-bearer and API-key MUST yield the same id"
        assert kc_resolved != kc_sub, "resolver must NOT return the raw Keycloak sub"
        assert claimed_sub == kc_sub, "legacy email row must be claimed by the sub"
        assert _norm(conv_owner) == _norm(local_id), "lazy remap must relabel the sub-keyed conv"
        assert set(merged_apps) == {"librechat", "projectops"}, "apps merge additively"
        assert synced_role == "operator", "role syncs from Keycloak"

        # Edge: brand-new user (no keycloak_id match, no email row) → provisioned.
        new_sub = str(uuid.uuid4())
        async with Session() as s:
            new_id = await resolve_canonical_user_id(
                s, kc_sub=new_sub, email="carol@x.com",
                derived_apps=[], realm_role="viewer")
        async with Session() as s:
            carol = (await s.execute(select(User).where(User.email == "carol@x.com"))).scalar_one()
        # Compare as UUIDs: on the throwaway SQLite the just-created object holds
        # the dashed python default while a fresh SELECT returns the normalized
        # form — the SAME identity (on prod Postgres both are the canonical
        # dashed string, so this equality is exact there).
        assert uuid.UUID(new_id) == uuid.UUID(str(carol.id)), "new user provisioned to a stable id"
        assert carol.keycloak_id == new_sub, "new user bound to its sub"

        # Edge: collision — same email presents a DIFFERENT sub. Keep original binding.
        async with Session() as s:
            collide_id = await resolve_canonical_user_id(
                s, kc_sub=str(uuid.uuid4()), email="bob@x.com",
                derived_apps=[], realm_role="operator")
        async with Session() as s:
            u2 = (await s.execute(select(User).where(User.email == "bob@x.com"))).scalar_one()
        assert _norm(collide_id) == _norm(local_id), "collision still resolves the same human's row"
        assert u2.keycloak_id == kc_sub, "collision must NOT overwrite the existing sub binding"

        # Edge: emailless token with no prior binding → degraded (None), caller keeps sub.
        async with Session() as s:
            degraded = await resolve_canonical_user_id(
                s, kc_sub=str(uuid.uuid4()), email=None,
                derived_apps=[], realm_role="viewer")
        assert degraded is None, "emailless + unknown sub cannot mint a row"

        log.append(f"[resolver] KC id == API-key id == {local_id[:8]}; claim+merge+role OK; "
                   f"new-user/collision/emailless edges OK")
    finally:
        await engine.dispose()
        os.unlink(path)


def _scenario_memory_alias(log):
    """BR-1.1 memory dual-read: a cutover SSO user's pre-BR-1.1 agent memory —
    stored in Graphiti under a group_id keyed by the raw Keycloak sub — stays
    reachable AFTER the id cutover with no data movement. Retrieval reads both
    the canonical and legacy namespaces; writes stay canonical-only, so the sub
    namespace only drains via reads and never accretes new memory.

    Pure ``_group_id`` / ``_read_group_ids`` string logic — Graphiti/FalkorDB are
    not importable in this env, but the manager degrades to ``graphiti=None`` and
    these methods stay callable, which is exactly the alias surface under test."""
    from app.memory.graphiti_manager import GraphitiMemoryManager

    m = GraphitiMemoryManager()  # graphiti absent -> self.graphiti None; pure methods still work
    local_id = "11111111-2222-3333-4444-555555555555"  # canonical local users.id
    sub = "kc|abcd-legacy-sub"                          # pre-BR-1.1 Keycloak sub
    agent = "col-finance"

    write_group = m._group_id(local_id, agent)

    # 1. Dual-read covers BOTH namespaces, canonical first.
    read_groups = m._read_group_ids(local_id, agent, legacy_user_id=sub)
    assert write_group in read_groups, "reads must cover the canonical write namespace"
    assert m._group_id(sub, agent) in read_groups, "reads must ALSO cover the legacy sub namespace"
    assert len(read_groups) == 2, "exactly canonical + legacy"
    assert read_groups[0] == write_group, "canonical namespace is read first"

    # 2. Writes are canonical-only: the write namespace is the local-id group and
    #    is never the legacy group — new memory can only land under the local id.
    assert write_group == m._group_id(local_id, agent)
    assert write_group != m._group_id(sub, agent), "write namespace must differ from the legacy one"

    # 3. Nothing to alias -> a single (canonical) namespace, identical to pre-alias.
    assert m._read_group_ids(local_id, agent, legacy_user_id=None) == [write_group], \
        "None sub -> single namespace"
    assert m._read_group_ids(local_id, agent, legacy_user_id=local_id) == [write_group], \
        "sub == canonical id -> single namespace"

    # 4. Case scoping is preserved on BOTH namespaces (memory can't bleed cases).
    cg = m._read_group_ids(local_id, agent, case_id="case-9", legacy_user_id=sub)
    assert cg == [m._group_id(local_id, agent, "case-9"), m._group_id(sub, agent, "case-9")], \
        "case segment applied to both canonical + legacy groups"

    # 5. A legacy id that slugs to the SAME group is deduped to a single read.
    assert m._read_group_ids("a.b", agent, legacy_user_id="a/b") == [m._group_id("a.b", agent)], \
        "slug collision must not double-read the same namespace"

    log.append(f"[memory] read={read_groups}; write-only={write_group}; "
               f"None/equal->single; case+dedupe OK")


async def _run_all():
    log = []
    await _scenario_batch_remap(log)
    await _scenario_resolver(log)
    _scenario_memory_alias(log)
    return log


# ---- pytest entrypoints ----

@pytest.mark.asyncio
async def test_batch_remap_unifies_forked_rows():
    await _scenario_batch_remap([])


@pytest.mark.asyncio
async def test_resolver_unifies_kc_and_apikey():
    await _scenario_resolver([])


def test_memory_dual_read_alias():
    """Sync — the alias is pure string logic, no DB/event-loop needed."""
    _scenario_memory_alias([])


def test_authuser_carries_keycloak_id():
    """The dual-read plumbing hinges on AuthUser exposing the legacy sub."""
    from app.auth.middleware import AuthUser
    from app.auth.roles import UserRole
    # Default None: master-admin / agent keys have no bound sub -> no alias.
    assert AuthUser(id="x", role=UserRole.VIEWER).keycloak_id is None
    # Threaded by the KC-bearer and user-API-key paths.
    au = AuthUser(id="local-1", role=UserRole.VIEWER, user_id="local-1", keycloak_id="kc-sub-9")
    assert au.keycloak_id == "kc-sub-9"


if __name__ == "__main__":
    out = asyncio.run(_run_all())
    print("BR-1.1 identity-canonical test — PASS")
    for line in out:
        print("  " + line)
