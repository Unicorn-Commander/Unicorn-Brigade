"""
Empirical RS256 round-trip + security gate for Brigade federation.

The go/no-go: a Brigade-minted RS256 JWT must verify under the SAME python-jose
call the FastAPI verifier apps use (`algorithms=["RS256"]`), and must be
rejected for the wrong audience, wrong key, expired, wrong issuer, and alg=none.
The audience-binding case is the single most important security property (it is
what stops a token minted for app A from being replayed against app B).

Run from the repo root:  python -m pytest app/federation/test_federation_crypto.py -v
"""
import base64
import os
import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

# Provision a deterministic test signing key in the env BEFORE importing the
# federation modules, so the lazy KeyStore loads it on first use.
_PRIV = rsa.generate_private_key(public_exponent=65537, key_size=2048)
os.environ["BRIGADE_JWT_PRIVATE_KEY"] = _PRIV.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
).decode("ascii")
os.environ["BRIGADE_JWT_KID"] = "brigade-test-rsa-01"
os.environ["BRIGADE_ISSUER"] = "https://brigade.unicorncommander.ai"

from jose import jwt as jose_jwt  # noqa: E402
from jose.exceptions import JWTError  # noqa: E402

from app.federation.keys import get_keystore  # noqa: E402
from app.federation.mint import issuer, mint_app_jwt  # noqa: E402

ISS = issuer()


def _public_jwk() -> dict:
    keys = get_keystore().public_jwks()["keys"]
    assert keys, "JWKS should publish the signing key"
    jwk = keys[0]
    assert "d" not in jwk and "p" not in jwk and "q" not in jwk, "JWKS must not leak private params"
    assert jwk["kty"] == "RSA" and jwk["alg"] == "RS256"
    return jwk


def _b64url_uint(value: int) -> str:
    length = (value.bit_length() + 7) // 8 or 1
    return base64.urlsafe_b64encode(value.to_bytes(length, "big")).rstrip(b"=").decode("ascii")


def test_roundtrip_jose_rs256():
    """Brigade-signed RS256 token verifies under the apps' python-jose call."""
    tok = mint_app_jwt(sub="u-123", aud="project-ops", org_id="org-9",
                       scopes=["read:projects", "write:tasks"])
    claims = jose_jwt.decode(tok, _public_jwk(), algorithms=["RS256"],
                             audience="project-ops", issuer=ISS)
    assert claims["sub"] == "u-123"
    assert claims["org_id"] == "org-9"
    assert claims["scopes"] == ["read:projects", "write:tasks"]
    assert claims["iss"] == ISS
    assert claims["aud"] == "project-ops"
    assert claims["exp"] > claims["iat"] and claims["nbf"] <= claims["iat"]
    assert claims["jti"]


def test_kid_header_present():
    tok = mint_app_jwt(sub="u-1", aud="project-ops", scopes=[])
    hdr = jose_jwt.get_unverified_header(tok)
    assert hdr["alg"] == "RS256"
    assert hdr["kid"] == "brigade-test-rsa-01"


def test_audience_binding_rejected():
    """SECURITY-CRITICAL: a project-ops token must 401 at a crisis-ops verifier."""
    tok = mint_app_jwt(sub="u-1", aud="project-ops", scopes=[])
    with pytest.raises(JWTError):
        jose_jwt.decode(tok, _public_jwk(), algorithms=["RS256"],
                        audience="crisis-ops", issuer=ISS)


def test_wrong_key_rejected():
    tok = mint_app_jwt(sub="u-1", aud="project-ops", scopes=[])
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048).public_key().public_numbers()
    bad = {"kty": "RSA", "alg": "RS256", "use": "sig", "kid": "brigade-test-rsa-01",
           "n": _b64url_uint(other.n), "e": _b64url_uint(other.e)}
    with pytest.raises(JWTError):
        jose_jwt.decode(tok, bad, algorithms=["RS256"], audience="project-ops", issuer=ISS)


def test_expired_rejected():
    tok = mint_app_jwt(sub="u-1", aud="project-ops", scopes=[], ttl_seconds=1)
    time.sleep(2)
    with pytest.raises(JWTError):
        jose_jwt.decode(tok, _public_jwk(), algorithms=["RS256"], audience="project-ops", issuer=ISS)


def test_issuer_mismatch_rejected():
    tok = mint_app_jwt(sub="u-1", aud="project-ops", scopes=[])
    with pytest.raises(JWTError):
        jose_jwt.decode(tok, _public_jwk(), algorithms=["RS256"],
                        audience="project-ops", issuer="https://evil.example.com")


def test_alg_confusion_none_rejected():
    """A verifier pinned to RS256 must never accept alg=none."""
    tok = mint_app_jwt(sub="u-1", aud="project-ops", scopes=[])
    with pytest.raises(Exception):
        jose_jwt.decode(tok, _public_jwk(), algorithms=["none"], audience="project-ops", issuer=ISS)


def test_mint_requires_sub_and_aud():
    with pytest.raises(ValueError):
        mint_app_jwt(sub="", aud="project-ops")
    with pytest.raises(ValueError):
        mint_app_jwt(sub="u-1", aud="")
