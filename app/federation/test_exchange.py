"""
Security gate for the RFC 8693 token-exchange endpoint (app/federation/exchange.py).

These tests pin the exchange's authorization decisions WITHOUT network (the pure
`authorize_and_build_mint`) and prove the minted token is a real, audience-bound,
least-privilege delegation token (mint → jose verify, the same floor as
test_federation_crypto). The subject-token signature/issuer verification is
exercised live against Keycloak after deploy; here we test what we can prove
deterministically: the authorization logic and the crypto binding of the output.

Run:  python -m pytest app/federation/test_exchange.py -v
"""
import base64
import os

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

# Deterministic signing key BEFORE importing the federation modules.
_PRIV = rsa.generate_private_key(public_exponent=65537, key_size=2048)
os.environ["BRIGADE_JWT_PRIVATE_KEY"] = _PRIV.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
).decode("ascii")
os.environ["BRIGADE_JWT_KID"] = "brigade-test-rsa-01"
os.environ["BRIGADE_ISSUER"] = "https://brigade.unicorncommander.ai"

from jose import jwt as jose_jwt  # noqa: E402

from app.federation.keys import get_keystore  # noqa: E402
from app.federation.mint import issuer, mint_app_jwt  # noqa: E402
from app.federation.exchange import (  # noqa: E402
    ExchangeError,
    _scopes_of,
    authorize_and_build_mint,
)

ISS = issuer()
WS = "019e50a3-d995-723f-ab66-0f765f92c0f4"  # CO's magic-unicorn-inc tenant


def _public_jwk() -> dict:
    return get_keystore().public_jwks()["keys"][0]


def _subject(*, azp="customer-ops", scope="contacts:read contacts:write email profile", workspace=None, sub="svc-customer-ops"):
    c = {"sub": sub, "azp": azp, "scope": scope}
    if workspace:
        c["workspace_id"] = workspace
    return c


ALLOW = dict(allow_actors=["customer-ops"], allow_audiences=["contact-ops"])


# --- the pure authorization logic ------------------------------------------ #

def test_happy_path_builds_least_privilege_mint():
    out = authorize_and_build_mint(
        subject_claims=_subject(),
        actor_claims=None,
        audience="contact-ops",
        requested_scope="contacts:read contacts:write",
        workspace_id_param=WS,
        **ALLOW,
    )
    assert out["aud"] == "contact-ops"
    assert out["sub"] == "svc-customer-ops"
    assert out["workspace_id"] == WS
    assert out["scopes"] == ["contacts:read", "contacts:write"]  # OIDC scopes dropped
    assert out["act"] == {"sub": "svc-customer-ops", "client_id": "customer-ops"}


def test_audience_not_allowlisted_is_denied():
    with pytest.raises(ExchangeError) as e:
        authorize_and_build_mint(
            subject_claims=_subject(), actor_claims=None, audience="accounting-ops",
            requested_scope=None, workspace_id_param=WS, **ALLOW,
        )
    assert e.value.status == 403 and e.value.error == "access_denied"


def test_actor_not_allowlisted_is_denied():
    with pytest.raises(ExchangeError) as e:
        authorize_and_build_mint(
            subject_claims=_subject(azp="rogue-app"), actor_claims=None, audience="contact-ops",
            requested_scope=None, workspace_id_param=WS, **ALLOW,
        )
    assert e.value.status == 403


def test_requested_scope_exceeding_subject_is_escalation_denied():
    with pytest.raises(ExchangeError) as e:
        authorize_and_build_mint(
            subject_claims=_subject(scope="contacts:read"),  # subject lacks write
            actor_claims=None, audience="contact-ops",
            requested_scope="contacts:read contacts:write",
            workspace_id_param=WS, **ALLOW,
        )
    assert e.value.status == 403 and "exceed" in e.value.description


def test_missing_workspace_is_rejected():
    with pytest.raises(ExchangeError) as e:
        authorize_and_build_mint(
            subject_claims=_subject(),  # no workspace claim
            actor_claims=None, audience="contact-ops",
            requested_scope=None, workspace_id_param=None,  # and none supplied
            **ALLOW,
        )
    assert e.value.status == 400


def test_subject_workspace_claim_wins_over_param():
    out = authorize_and_build_mint(
        subject_claims=_subject(workspace="ws-from-claim"),
        actor_claims=None, audience="contact-ops",
        requested_scope=None, workspace_id_param="ws-from-param", **ALLOW,
    )
    assert out["workspace_id"] == "ws-from-claim"


def test_actor_token_overrides_subject_azp():
    # subject is a user token; actor is the calling app's credential.
    out = authorize_and_build_mint(
        subject_claims={"sub": "user-7", "azp": "some-spa", "scope": "contacts:write", "workspace_id": WS},
        actor_claims={"sub": "svc-customer-ops", "azp": "customer-ops"},
        audience="contact-ops", requested_scope="contacts:write", workspace_id_param=None, **ALLOW,
    )
    assert out["sub"] == "user-7"  # delegation preserves the end-user
    assert out["act"]["client_id"] == "customer-ops"  # the actor is the app


def test_default_deny_when_no_allowlists_configured():
    with pytest.raises(ExchangeError) as e:
        authorize_and_build_mint(
            subject_claims=_subject(), actor_claims=None, audience="contact-ops",
            requested_scope=None, workspace_id_param=WS,
            allow_actors=[], allow_audiences=[],  # nothing configured = deny
        )
    assert e.value.status == 403


def test_scopes_of_drops_oidc_and_reads_both_shapes():
    assert _scopes_of({"scope": "openid email contacts:read"}) == {"contacts:read"}
    assert _scopes_of({"scopes": ["profile", "contacts:write"]}) == {"contacts:write"}


# --- the minted token is a real, audience-bound delegation token ----------- #

def test_exchanged_token_round_trips_and_is_audience_bound():
    out = authorize_and_build_mint(
        subject_claims=_subject(workspace=WS), actor_claims=None, audience="contact-ops",
        requested_scope="contacts:read contacts:write", workspace_id_param=None, **ALLOW,
    )
    token = mint_app_jwt(**out)
    claims = jose_jwt.decode(token, _public_jwk(), algorithms=["RS256"], audience="contact-ops", issuer=ISS)
    assert claims["aud"] == "contact-ops"
    assert claims["workspace_id"] == WS
    assert claims["act"]["client_id"] == "customer-ops"
    assert set(claims["scopes"]) == {"contacts:read", "contacts:write"}
    assert "org_id" not in claims  # the retired claim never appears

    # The single most important property: a token for contact-ops is REJECTED at
    # another app's verifier (audience binding / anti-replay).
    with pytest.raises(Exception):
        jose_jwt.decode(token, _public_jwk(), algorithms=["RS256"], audience="accounting-ops", issuer=ISS)
