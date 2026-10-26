"""Focused coverage for organization member administration actions."""

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api import org_routes
from app.db import org_service as svc
from app.db.models import Invitation, OrgMembership

ORG_ID = "org-a"
ACTOR_ID = "user-owner"
TARGET_ID = "user-target"


class _Result:
    def __init__(self, *, scalar=None, rows=None, first=None):
        self._scalar = scalar
        self._rows = list(rows or [])
        self._first = first

    def scalar_one_or_none(self):
        return self._scalar

    def scalars(self):
        return self

    def all(self):
        return self._rows

    def first(self):
        return self._first


class _Session:
    def __init__(self, results=()):
        self.results = list(results)
        self.queries = []
        self.deleted = []
        self.flushes = 0
        self.commits = 0

    async def execute(self, query):
        self.queries.append(query)
        return self.results.pop(0)

    async def flush(self):
        self.flushes += 1

    async def delete(self, item):
        self.deleted.append(item)

    async def commit(self):
        self.commits += 1


def _membership(user_id=TARGET_ID, role=svc.ORG_ROLE_MEMBER):
    return OrgMembership(org_id=ORG_ID, user_id=user_id, role=role)


def _invitation(token="old-token", status="pending"):
    return Invitation(
        id="invite-a",
        org_id=ORG_ID,
        email="invitee@example.com",
        role=svc.ORG_ROLE_MEMBER,
        token=token,
        status=status,
        expires_at=datetime.utcnow() - timedelta(hours=1),
    )


@pytest.mark.asyncio
async def test_owner_can_change_member_role_and_query_is_org_scoped():
    member = _membership()
    session = _Session([_Result(rows=[member])])

    changed = await svc.update_member_role(session, ORG_ID, TARGET_ID, svc.ORG_ROLE_ADMIN)

    assert changed is member
    assert member.role == svc.ORG_ROLE_ADMIN
    assert session.flushes == 1
    where = str(session.queries[0])
    assert "org_memberships.org_id" in where
    assert "org_memberships.user_id" in where


@pytest.mark.asyncio
async def test_last_owner_cannot_be_demoted_or_removed():
    owner = _membership(role=svc.ORG_ROLE_OWNER)

    demotion_session = _Session([
        _Result(rows=[owner]),
    ])
    with pytest.raises(ValueError, match="last_owner"):
        await svc.update_member_role(demotion_session, ORG_ID, TARGET_ID, svc.ORG_ROLE_MEMBER)
    assert owner.role == svc.ORG_ROLE_OWNER
    assert demotion_session.flushes == 0

    removal_session = _Session([
        _Result(rows=[owner]),
    ])
    with pytest.raises(ValueError, match="last_owner"):
        await svc.remove_member(removal_session, ORG_ID, TARGET_ID)
    assert removal_session.deleted == []


@pytest.mark.asyncio
async def test_member_removal_succeeds_when_another_owner_remains():
    target = _membership()
    session = _Session([_Result(rows=[target])])

    removed = await svc.remove_member(session, ORG_ID, TARGET_ID)

    assert removed is target
    assert session.deleted == [target]
    assert session.flushes == 1


@pytest.mark.asyncio
async def test_resend_rotates_token_and_uses_create_ttl(monkeypatch):
    invitation = _invitation()
    old_expiry = invitation.expires_at
    session = _Session([_Result(scalar=invitation)])
    monkeypatch.setattr(svc.secrets, "token_urlsafe", lambda size: "new-token")

    resent = await svc.resend_invitation(
        session, ORG_ID, invitation.id, invited_by=ACTOR_ID
    )

    assert resent is invitation
    assert invitation.token == "new-token"
    assert invitation.token != "old-token"
    assert invitation.invited_by == ACTOR_ID
    assert invitation.expires_at > old_expiry
    remaining = invitation.expires_at - datetime.utcnow()
    expected = timedelta(hours=svc.INVITE_TTL_HOURS)
    assert expected - timedelta(seconds=2) <= remaining <= expected + timedelta(seconds=2)


@pytest.mark.asyncio
async def test_resend_only_accepts_pending_invites():
    session = _Session([_Result(scalar=_invitation(status="revoked"))])

    with pytest.raises(ValueError, match="not_pending"):
        await svc.resend_invitation(session, ORG_ID, "invite-a")


@pytest.mark.asyncio
async def test_old_resend_token_is_not_found_by_accept(monkeypatch):
    invitation = _invitation()
    resend_session = _Session([_Result(scalar=invitation)])
    monkeypatch.setattr(svc.secrets, "token_urlsafe", lambda size: "rotated-token")
    await svc.resend_invitation(resend_session, ORG_ID, invitation.id)

    async def execute(query):
        params = query.compile().params
        token = next((value for key, value in params.items() if "token" in key), None)
        return _Result(scalar=invitation if token == invitation.token else None)

    session = _Session()
    session.execute = execute

    result, found = await svc.accept_invitation(session, "old-token", TARGET_ID)

    assert result == "not_found"
    assert found is None


@pytest.mark.asyncio
async def test_route_owner_changes_member_role(monkeypatch):
    target = _membership()
    session = _Session()
    monkeypatch.setattr(org_routes, "_uid", lambda session, user: _async_value(ACTOR_ID))
    monkeypatch.setattr(svc, "get_membership_role", lambda session, uid, org: _async_value(svc.ORG_ROLE_OWNER))
    monkeypatch.setattr(svc, "get_org_membership", lambda session, org, user: _async_value(target))
    monkeypatch.setattr(svc, "update_member_role", lambda *args: _async_value(target))
    monkeypatch.setattr(
        svc,
        "get_org_member",
        lambda session, org, user: _async_value({"userId": TARGET_ID, "role": svc.ORG_ROLE_ADMIN}),
    )

    result = await org_routes.update_member_role(
        ORG_ID,
        TARGET_ID,
        org_routes.UpdateMemberRoleRequest(role=svc.ORG_ROLE_ADMIN),
        session=session,
        current_user=SimpleNamespace(org_id=ORG_ID),
    )

    assert result["role"] == svc.ORG_ROLE_ADMIN
    assert session.commits == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["role", "remove"])
@pytest.mark.parametrize(
    ("caller_role", "expected_status"),
    [(svc.ORG_ROLE_MEMBER, 403), (None, 404)],
)
async def test_non_manager_and_cross_org_are_refused(
    monkeypatch, action, caller_role, expected_status
):
    session = _Session()
    monkeypatch.setattr(org_routes, "_uid", lambda session, user: _async_value(ACTOR_ID))
    monkeypatch.setattr(
        svc,
        "get_membership_role",
        lambda session, uid, org: _async_value(caller_role),
    )

    if action == "role":
        call = org_routes.update_member_role(
            "org-other",
            TARGET_ID,
            org_routes.UpdateMemberRoleRequest(role=svc.ORG_ROLE_MEMBER),
            session=session,
            current_user=SimpleNamespace(org_id="org-other"),
        )
    else:
        call = org_routes.delete_member(
            "org-other",
            TARGET_ID,
            session=session,
            current_user=SimpleNamespace(org_id="org-other"),
        )

    with pytest.raises(HTTPException) as exc:
        await call
    assert exc.value.status_code == expected_status


@pytest.mark.asyncio
async def test_admin_cannot_change_or_remove_owner(monkeypatch):
    owner = _membership(user_id="owner-2", role=svc.ORG_ROLE_OWNER)
    session = _Session()
    monkeypatch.setattr(org_routes, "_uid", lambda session, user: _async_value(ACTOR_ID))
    monkeypatch.setattr(svc, "get_membership_role", lambda session, uid, org: _async_value(svc.ORG_ROLE_ADMIN))
    monkeypatch.setattr(svc, "get_org_membership", lambda session, org, user: _async_value(owner))

    with pytest.raises(HTTPException) as role_error:
        await org_routes.update_member_role(
            ORG_ID,
            owner.user_id,
            org_routes.UpdateMemberRoleRequest(role=svc.ORG_ROLE_MEMBER),
            session=session,
            current_user=SimpleNamespace(org_id=ORG_ID),
        )
    assert role_error.value.status_code == 403

    with pytest.raises(HTTPException) as remove_error:
        await org_routes.delete_member(
            ORG_ID,
            owner.user_id,
            session=session,
            current_user=SimpleNamespace(org_id=ORG_ID),
        )
    assert remove_error.value.status_code == 403


@pytest.mark.asyncio
async def test_route_resends_pending_invitation(monkeypatch):
    invitation = _invitation(token="fresh-token")
    session = _Session()
    monkeypatch.setattr(org_routes, "_uid", lambda session, user: _async_value(ACTOR_ID))
    monkeypatch.setattr(svc, "get_membership_role", lambda session, uid, org: _async_value(svc.ORG_ROLE_OWNER))
    monkeypatch.setattr(svc, "resend_invitation", lambda *args, **kwargs: _async_value(invitation))

    result = await org_routes.resend_invite(
        ORG_ID,
        invitation.id,
        session=session,
        current_user=SimpleNamespace(org_id=ORG_ID),
    )

    assert result["token"] == "fresh-token"
    assert result["emailDelivery"] == "stub"
    assert session.commits == 1


async def _async_value(value):
    return value
