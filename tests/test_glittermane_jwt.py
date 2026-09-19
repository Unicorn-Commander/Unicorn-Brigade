"""Glitter Mane Brigade JWT must carry the caller's email.

Glitter resolves the chart with ``payload.email or payload.sub`` and rejects
any value without ``@``. A UUID-only ``sub`` (the 2026-09-18 production mint)
returns HTTP 401 ``Not authenticated`` even when the HS256 signature is valid.

    python3 -m pytest tests/test_glittermane_jwt.py -q
"""

import pytest
from jose import jwt as jose_jwt

import app.llm.glittermane_mcp_tools as gm

SECRET = "test-glitter-jwt-secret-not-production"


@pytest.fixture(autouse=True)
def _secret(monkeypatch):
    monkeypatch.setattr(gm, "GLITTERMANE_JWT_SECRET", SECRET)
    monkeypatch.setattr(gm, "GLITTERMANE_STATIC_TOKEN", "")


def test_mint_includes_email_and_audience():
    token = gm._mint_user_jwt("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "Aaron@MagicUnicorn.tech")
    payload = jose_jwt.decode(
        token,
        SECRET,
        algorithms=["HS256"],
        audience=gm.GLITTERMANE_JWT_AUD,
        options={"require": ["exp", "aud"]},
    )
    assert payload["sub"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert payload["email"] == "aaron@magicunicorn.tech"
    assert "@" in payload["email"]
    assert payload["aud"] == gm.GLITTERMANE_JWT_AUD


def test_mint_rejects_uuid_only_sub():
    with pytest.raises(ValueError, match="email"):
        gm._mint_user_jwt("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "")


def test_auth_header_requires_email():
    assert gm._auth_header("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee") == {}
    assert gm._auth_header("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", caller_email="not-an-email") == {}
    header = gm._auth_header(
        "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        caller_email="aaron@magicunicorn.tech",
    )
    assert header["Authorization"].startswith("Bearer ")
    token = header["Authorization"].split(" ", 1)[1]
    payload = jose_jwt.get_unverified_claims(token)
    assert payload["email"] == "aaron@magicunicorn.tech"
