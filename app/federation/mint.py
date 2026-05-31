"""
Brigade federation JWT minting (RS256).

Mints short-lived RS256 JWTs that Brigade attaches as `Authorization: Bearer`
on outbound calls to a federated UC app's REST API. Claims and lifetime follow
BRIGADE-FEDERATION-SPEC.md. Signed with the current key from KeyStore; the `kid`
header lets the target app select the right public key from Brigade's JWKS.

Brigade signs (it is never a Brigade-JWT verifier): inbound app-to-Brigade auth
stays on the existing X-API-Key path.
"""
from __future__ import annotations

import logging
import os
import secrets
import time
from typing import Sequence

from jose import jwt

from app.federation.keys import ALG, get_keystore

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 300  # 5 minutes per spec
_MAX_TTL_SECONDS = 3600


def issuer() -> str:
    return os.getenv("BRIGADE_ISSUER", "https://brigade.unicorncommander.ai").rstrip("/")


def mint_app_jwt(
    *,
    sub: str,
    aud: str,
    org_id: str | None = None,
    scopes: Sequence[str] | None = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> str:
    """
    Mint an RS256 JWT scoped to a single target app.

    sub      target-app user id (from Brigade's user_id_per_app mapping)
    aud      target app's expected_audience (e.g. "project-ops") - binds the
             token to ONE app; this is the anti-replay property
    org_id   target-app org id (optional)
    scopes   scopes for the invoked tool, already intersected with the tier
    """
    if not sub:
        raise ValueError("mint_app_jwt: sub is required")
    if not aud:
        raise ValueError("mint_app_jwt: aud is required")
    if not (0 < ttl_seconds <= _MAX_TTL_SECONDS):
        raise ValueError(f"mint_app_jwt: ttl_seconds must be in (0, {_MAX_TTL_SECONDS}]")

    key = get_keystore().signing_key()
    now = int(time.time())
    claims = {
        "iss": issuer(),
        "aud": aud,
        "sub": str(sub),
        "iat": now,
        "nbf": now,
        "exp": now + int(ttl_seconds),
        "jti": secrets.token_urlsafe(16),
        "scopes": list(scopes or []),
    }
    if org_id is not None:
        claims["org_id"] = str(org_id)

    token = jwt.encode(
        claims,
        key.private_pem,
        algorithm=ALG,
        headers={"kid": key.kid, "typ": "JWT"},
    )
    logger.debug(
        "Minted federation JWT aud=%s sub=%s kid=%s jti=%s ttl=%ss",
        aud, sub, key.kid, claims["jti"], ttl_seconds,
    )
    return token
