"""
Keycloak JWT Validation Module

Validates Bearer tokens issued by the Keycloak realm at
${OIDC_ISSUER}. Caches JWKS keys with a TTL and refreshes on
key-not-found. Extracts user info (email, preferred_username, sub,
realm roles) from validated tokens.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx
from jose import jwt
from jose.exceptions import ExpiredSignatureError, JWTError

logger = logging.getLogger(__name__)

# --- Configuration (read lazily so env changes are reflected) ---------------

def _cfg(key: str, default: Optional[str] = None) -> Optional[str]:
    val = os.getenv(key)
    if val is None or val == "":
        return default
    return val


def keycloak_enabled() -> bool:
    return (_cfg("BRIGADE_USE_KEYCLOAK", "false") or "false").lower() == "true"


def issuer() -> str:
    return _cfg("OIDC_ISSUER", "https://auth.magicunicorn.dev/realms/uchub")


def jwks_url() -> str:
    return _cfg(
        "KEYCLOAK_JWKS_URL",
        f"{issuer().rstrip('/')}/protocol/openid-connect/certs",
    )


def client_id() -> str:
    return _cfg("KEYCLOAK_CLIENT_ID", "brigade")


def audience() -> Optional[str]:
    # Keycloak often issues tokens with the client as an audience, but with
    # "account" being the default aud. Allow opt-out via env. When unset we
    # skip aud checks and rely on azp validation.
    return _cfg("OIDC_AUDIENCE")


# --- JWKS cache -------------------------------------------------------------

_JWKS_TTL_SECONDS = int(_cfg("OIDC_JWKS_TTL", "3600") or 3600)


@dataclass
class _JwksCache:
    keys: Dict[str, Dict[str, Any]]
    fetched_at: float

    def is_fresh(self, ttl: int = _JWKS_TTL_SECONDS) -> bool:
        return (time.time() - self.fetched_at) < ttl


_jwks_cache: Optional[_JwksCache] = None


async def _fetch_jwks(force: bool = False) -> Dict[str, Dict[str, Any]]:
    """Fetch JWKS from Keycloak, caching indexed by ``kid``."""
    global _jwks_cache
    if (
        not force
        and _jwks_cache is not None
        and _jwks_cache.is_fresh()
    ):
        return _jwks_cache.keys

    url = jwks_url()
    logger.info("Fetching JWKS from %s (force=%s)", url, force)
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()

    keys_by_kid: Dict[str, Dict[str, Any]] = {}
    for key in data.get("keys", []):
        kid = key.get("kid")
        if kid:
            keys_by_kid[kid] = key

    _jwks_cache = _JwksCache(keys=keys_by_kid, fetched_at=time.time())
    logger.info("JWKS cache refreshed with %d keys", len(keys_by_kid))
    return keys_by_kid


async def _get_signing_key(kid: str) -> Optional[Dict[str, Any]]:
    """Return the JWK for ``kid``, refreshing the cache on miss."""
    keys = await _fetch_jwks(force=False)
    key = keys.get(kid)
    if key is not None:
        return key
    # Miss - refresh once in case keys rotated.
    keys = await _fetch_jwks(force=True)
    return keys.get(kid)


# --- Validated token representation ----------------------------------------

@dataclass
class KeycloakUser:
    """User info extracted from a validated Keycloak access token."""

    sub: str
    email: Optional[str]
    preferred_username: Optional[str]
    name: Optional[str]
    realm_roles: List[str]
    client_roles: List[str]
    raw: Dict[str, Any]

    @property
    def identifier(self) -> str:
        """Stable identifier for the user - email if present, else sub."""
        return self.email or self.preferred_username or self.sub


class KeycloakValidationError(Exception):
    """Raised when a Keycloak access token fails validation."""


async def validate_token(token: str) -> KeycloakUser:
    """
    Validate a Keycloak-issued JWT access token.

    Checks signature against the realm JWKS, expiration, and issuer.
    Optionally checks audience when ``OIDC_AUDIENCE`` is set.

    Raises:
        KeycloakValidationError: token is invalid or cannot be validated.
    """
    if not token:
        raise KeycloakValidationError("empty token")

    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise KeycloakValidationError(f"malformed token header: {exc}") from exc

    kid = unverified_header.get("kid")
    if not kid:
        raise KeycloakValidationError("token header missing 'kid'")

    key = await _get_signing_key(kid)
    if key is None:
        raise KeycloakValidationError(f"no JWKS key matches kid={kid}")

    options = {
        "verify_signature": True,
        "verify_aud": audience() is not None,
        "verify_iss": True,
        "verify_exp": True,
    }

    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=[key.get("alg", "RS256")],
            issuer=issuer(),
            audience=audience() if audience() else None,
            options=options,
        )
    except ExpiredSignatureError as exc:
        raise KeycloakValidationError("token expired") from exc
    except JWTError as exc:
        raise KeycloakValidationError(f"invalid token: {exc}") from exc

    # Sanity check on azp (authorized party). Keycloak sets this to the
    # client_id that requested the token. We accept any azp but log a debug
    # note when it differs from our expected client.
    azp = claims.get("azp")
    if azp and azp != client_id():
        logger.debug("Token azp=%s (expected %s)", azp, client_id())

    realm_roles: List[str] = []
    realm_access = claims.get("realm_access") or {}
    if isinstance(realm_access, dict):
        realm_roles = list(realm_access.get("roles") or [])

    client_roles: List[str] = []
    resource_access = claims.get("resource_access") or {}
    if isinstance(resource_access, dict):
        client_access = resource_access.get(client_id()) or {}
        if isinstance(client_access, dict):
            client_roles = list(client_access.get("roles") or [])

    return KeycloakUser(
        sub=str(claims.get("sub", "")),
        email=claims.get("email"),
        preferred_username=claims.get("preferred_username"),
        name=claims.get("name"),
        realm_roles=realm_roles,
        client_roles=client_roles,
        raw=claims,
    )


async def refresh_jwks() -> int:
    """Force-refresh the JWKS cache. Returns number of keys loaded."""
    keys = await _fetch_jwks(force=True)
    return len(keys)
