"""
Brigade federation token exchange — RFC 8693 (the app→app STS surface).

A Resource Server (e.g. Customer-Ops) that needs to call a sibling app (e.g.
Contact-Ops) trades a token it already holds for a fresh, audience-bound,
least-privilege delegation token minted by Brigade — WITHOUT ever forwarding the
original token to the sibling. This is the cross-app half of the federation
model (SUITE-IDENTITY §0.1 / D6; handoff-brigade §3.2). The customer-MCP path in
mcp_gateway.py is the other (user-driven) mint surface; this endpoint is the
app-to-app one.

    POST /api/v1/federation/token
      grant_type=urn:ietf:params:oauth:grant-type:token-exchange
      subject_token=<the caller's uchub or Brigade token>
      subject_token_type=urn:ietf:params:oauth:token-type:access_token  (optional)
      actor_token=<the calling app's service credential>                (optional)
      audience=<target app-id, e.g. contact-ops>
      scope="contacts:read contacts:write"                              (optional)
      workspace_id=<uuidv7>                                             (optional)
      resource=<target URL>                                            (optional, ignored)

Security floor (these are non-negotiable, mirrored in test_exchange.py):
  * The subject_token signature + exp + iss are verified against the TRUSTED
    issuers (multi-issuer: commander + bigboy uchub Keycloak) before anything
    else. An unverifiable / untrusted-issuer subject token is 401.
  * The ACTOR (the calling app, taken from actor_token.azp or subject_token.azp)
    must be in the actor allow-list — only named apps may exchange (403 else).
  * The AUDIENCE must be an allow-listed / registered sibling app — Brigade never
    mints for an unknown audience (403 else). The minted token is bound to that
    ONE audience (the anti-replay property; a token for A 401s at B's verifier).
  * Minted scopes are the LEAST-PRIVILEGE intersection: requested ∩ the subject
    token's own scopes. The exchange can never amplify privilege.
  * `workspace_id` is preserved from the subject token when present, else taken
    from the explicit parameter (the app-to-app / no-user case, where the trusted
    actor app asserts the tenancy). The target app still re-gates server-side.

What this endpoint does NOT do: forward the caller's token, mint for an
unverified subject, widen scope, or mint without an audience. Those are the
confused-deputy / replay failures ADR-5 forbids.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse
from jose import jwt
from jose.exceptions import ExpiredSignatureError, JWTError

from app.federation.mint import DEFAULT_TTL_SECONDS, mint_app_jwt

logger = logging.getLogger(__name__)

router = APIRouter(tags=["federation"])

GRANT_TYPE_TOKEN_EXCHANGE = "urn:ietf:params:oauth:grant-type:token-exchange"
TOKEN_TYPE_ACCESS = "urn:ietf:params:oauth:token-type:access_token"

# Standard OIDC scopes that are never propagated as app authorization scopes.
_OIDC_SCOPES = {"openid", "profile", "email", "address", "phone", "offline_access", "roles", "web-origins", "acr", "basic", "user-attributes"}


# --------------------------------------------------------------------------- #
# Config (read lazily so env changes / tests are reflected)
# --------------------------------------------------------------------------- #

def _csv(env_key: str, default: str = "") -> list[str]:
    raw = os.getenv(env_key, default) or ""
    return [s.strip() for s in raw.split(",") if s.strip()]


def trusted_issuers() -> list[str]:
    """uchub issuers whose tokens Brigade will accept as a subject_token. Both
    KC instances are peers in the same `uchub` realm (commander canonical, bigboy
    continuity)."""
    return [
        i.rstrip("/")
        for i in _csv(
            "BRIGADE_EXCHANGE_TRUSTED_ISSUERS",
            "https://auth.unicorncommander.ai/realms/uchub,https://auth.magicunicorn.dev/realms/uchub",
        )
    ]


def allowed_actors() -> list[str]:
    """The `azp` values permitted to use the exchange (default-deny: empty = none).
    Set BRIGADE_EXCHANGE_ALLOWED_ACTORS=customer-ops,project-ops,…"""
    return _csv("BRIGADE_EXCHANGE_ALLOWED_ACTORS")


def allowed_audiences() -> list[str]:
    """Target app-ids the exchange may mint for (default-deny: empty = none).
    Set BRIGADE_EXCHANGE_ALLOWED_AUDIENCES=contact-ops,accounting-ops,…"""
    return _csv("BRIGADE_EXCHANGE_ALLOWED_AUDIENCES")


def exchange_ttl() -> int:
    raw = os.getenv("BRIGADE_EXCHANGE_TTL_SECONDS")
    try:
        n = int(raw) if raw else DEFAULT_TTL_SECONDS
    except ValueError:
        n = DEFAULT_TTL_SECONDS
    return n if 0 < n <= 3600 else DEFAULT_TTL_SECONDS


# --------------------------------------------------------------------------- #
# Multi-issuer subject-token verification (per-issuer JWKS cache)
# --------------------------------------------------------------------------- #

@dataclass
class _IssuerJwks:
    keys: Dict[str, Dict[str, Any]]
    fetched_at: float

    def fresh(self, ttl: int = 3600) -> bool:
        return (time.time() - self.fetched_at) < ttl


_jwks_by_issuer: Dict[str, _IssuerJwks] = {}


class SubjectVerifyError(Exception):
    """The subject_token could not be verified (untrusted issuer / bad sig / expired)."""


async def _fetch_issuer_jwks(issuer: str, force: bool = False) -> Dict[str, Dict[str, Any]]:
    cached = _jwks_by_issuer.get(issuer)
    if not force and cached and cached.fresh():
        return cached.keys
    url = f"{issuer.rstrip('/')}/protocol/openid-connect/certs"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
    keys = {k["kid"]: k for k in data.get("keys", []) if k.get("kid")}
    _jwks_by_issuer[issuer] = _IssuerJwks(keys=keys, fetched_at=time.time())
    return keys


async def verify_subject_token(token: str) -> Dict[str, Any]:
    """Verify a subject/actor token against the trusted uchub issuers. Returns the
    verified claims. Raises SubjectVerifyError on any failure (no claim is read
    until the signature + issuer + expiry verify)."""
    if not token:
        raise SubjectVerifyError("empty token")
    try:
        header = jwt.get_unverified_header(token)
        unverified = jwt.get_unverified_claims(token)
    except JWTError as exc:
        raise SubjectVerifyError(f"malformed token: {exc}") from exc

    iss = (unverified.get("iss") or "").rstrip("/")
    trusted = trusted_issuers()
    if iss not in trusted:
        raise SubjectVerifyError(f"untrusted issuer: {iss!r}")
    kid = header.get("kid")
    if not kid:
        raise SubjectVerifyError("token header missing kid")

    keys = await _fetch_issuer_jwks(iss)
    key = keys.get(kid)
    if key is None:
        keys = await _fetch_issuer_jwks(iss, force=True)  # rotation refresh
        key = keys.get(kid)
    if key is None:
        raise SubjectVerifyError(f"no JWKS key for kid={kid} at {iss}")

    try:
        return jwt.decode(
            token,
            key,
            algorithms=[key.get("alg", "RS256")],
            issuer=iss,
            options={"verify_signature": True, "verify_aud": False, "verify_iss": True, "verify_exp": True},
        )
    except ExpiredSignatureError as exc:
        raise SubjectVerifyError("subject token expired") from exc
    except JWTError as exc:
        raise SubjectVerifyError(f"subject token invalid: {exc}") from exc


# --------------------------------------------------------------------------- #
# Pure authorization + claim assembly (network-free → unit-testable)
# --------------------------------------------------------------------------- #

class ExchangeError(Exception):
    """An RFC 6749 §5.2-style error: carries the HTTP status + the oauth error code."""

    def __init__(self, status: int, error: str, description: str):
        super().__init__(description)
        self.status = status
        self.error = error
        self.description = description


def _scopes_of(claims: Dict[str, Any]) -> set[str]:
    """The app-authorization scopes carried by a token (KC `scope` string or a
    `scopes` array), minus the standard OIDC scopes."""
    raw = claims.get("scope") or claims.get("scopes") or ""
    items = raw.split() if isinstance(raw, str) else list(raw)
    return {s for s in items if s and s not in _OIDC_SCOPES}


def authorize_and_build_mint(
    *,
    subject_claims: Dict[str, Any],
    actor_claims: Optional[Dict[str, Any]],
    audience: str,
    requested_scope: Optional[str],
    workspace_id_param: Optional[str],
    allow_actors: list[str],
    allow_audiences: list[str],
) -> Dict[str, Any]:
    """Authorize the exchange and return mint_app_jwt kwargs, or raise
    ExchangeError. PURE — no I/O — so the security logic is unit-tested directly.

    Decisions, in order:
      1. audience present + allow-listed (else invalid_request / access_denied),
      2. actor (actor_token.azp else subject.azp) allow-listed (else access_denied),
      3. workspace_id resolved (subject claim → param; else invalid_request),
      4. minted scopes = requested ∩ subject's scopes (least-privilege),
      5. sub preserved from subject; act = {sub, client_id: actor}.
    """
    if not audience:
        raise ExchangeError(400, "invalid_request", "audience is required")
    if allow_audiences and audience not in allow_audiences:
        raise ExchangeError(403, "access_denied", f"audience {audience!r} is not permitted for exchange")

    # The ACTOR is the calling app: actor_token's azp if supplied, else the
    # subject's azp (the app-to-app case where the subject IS the caller's own
    # service-account token).
    actor_source = actor_claims or subject_claims
    actor = actor_source.get("azp") or actor_source.get("client_id")
    if not actor:
        raise ExchangeError(400, "invalid_request", "could not determine the acting client (azp) of the token")
    if not allow_actors or actor not in allow_actors:
        raise ExchangeError(403, "access_denied", f"actor {actor!r} is not permitted to use token exchange")

    # Workspace: preserve the subject's claim, else accept the explicit param
    # (the trusted actor app asserts tenancy for its no-user service calls).
    workspace_id = subject_claims.get("workspace_id") or subject_claims.get("tenant_id") or workspace_id_param
    if not workspace_id:
        raise ExchangeError(
            400,
            "invalid_request",
            "no workspace: the subject token carries no workspace_id and none was supplied",
        )

    subject_scopes = _scopes_of(subject_claims)
    if requested_scope:
        requested = {s for s in requested_scope.split() if s and s not in _OIDC_SCOPES}
        granted = sorted(requested & subject_scopes)
        # Asking for a scope the subject does not hold is a privilege escalation.
        if requested - subject_scopes:
            raise ExchangeError(
                403,
                "access_denied",
                f"requested scopes exceed the subject's: {sorted(requested - subject_scopes)}",
            )
    else:
        granted = sorted(subject_scopes)

    sub = subject_claims.get("sub")
    if not sub:
        raise ExchangeError(400, "invalid_request", "subject token has no sub")

    return {
        "sub": str(sub),
        "aud": audience,
        "workspace_id": str(workspace_id),
        "act": {"sub": str(sub), "client_id": str(actor)},
        "entitlements": list(subject_claims.get("entitlements") or []) or None,
        "scopes": granted,
    }


# --------------------------------------------------------------------------- #
# The endpoint
# --------------------------------------------------------------------------- #

def _err(e: ExchangeError) -> JSONResponse:
    return JSONResponse(status_code=e.status, content={"error": e.error, "error_description": e.description})


@router.post("/api/v1/federation/token")
async def federation_token_exchange(
    request: Request,
    grant_type: str = Form(...),
    subject_token: str = Form(...),
    subject_token_type: str = Form(TOKEN_TYPE_ACCESS),
    audience: str = Form(...),
    scope: Optional[str] = Form(None),
    actor_token: Optional[str] = Form(None),
    workspace_id: Optional[str] = Form(None),
    resource: Optional[str] = Form(None),
):
    """RFC 8693 token exchange → a fresh, audience-bound delegation token."""
    if grant_type != GRANT_TYPE_TOKEN_EXCHANGE:
        return _err(ExchangeError(400, "unsupported_grant_type", f"grant_type must be {GRANT_TYPE_TOKEN_EXCHANGE}"))

    # 1) Verify the subject (and actor, if supplied) tokens — signature, issuer, exp.
    try:
        subject_claims = await verify_subject_token(subject_token)
    except SubjectVerifyError as exc:
        logger.info("exchange refused: subject token unverifiable (%s)", exc)
        return _err(ExchangeError(401, "invalid_token", f"subject_token verification failed: {exc}"))
    actor_claims: Optional[Dict[str, Any]] = None
    if actor_token:
        try:
            actor_claims = await verify_subject_token(actor_token)
        except SubjectVerifyError as exc:
            return _err(ExchangeError(401, "invalid_token", f"actor_token verification failed: {exc}"))

    # 2) Authorize + assemble the mint (pure).
    try:
        mint_kwargs = authorize_and_build_mint(
            subject_claims=subject_claims,
            actor_claims=actor_claims,
            audience=audience,
            requested_scope=scope,
            workspace_id_param=workspace_id,
            allow_actors=allowed_actors(),
            allow_audiences=allowed_audiences(),
        )
    except ExchangeError as exc:
        logger.info("exchange denied: %s (%s)", exc.error, exc.description)
        return _err(exc)

    # 3) Mint the audience-bound delegation token.
    try:
        ttl = exchange_ttl()
        token = mint_app_jwt(ttl_seconds=ttl, **mint_kwargs)
    except RuntimeError as exc:
        # Signing key not provisioned.
        logger.error("exchange mint failed: %s", exc)
        return _err(ExchangeError(503, "temporarily_unavailable", "federation signing key is not configured"))

    logger.info(
        "token exchange: actor=%s aud=%s workspace=%s scopes=%s",
        mint_kwargs["act"]["client_id"], audience, mint_kwargs["workspace_id"], mint_kwargs["scopes"],
    )
    return JSONResponse(
        status_code=200,
        content={
            "access_token": token,
            "issued_token_type": TOKEN_TYPE_ACCESS,
            "token_type": "Bearer",
            "expires_in": ttl,
            "scope": " ".join(mint_kwargs["scopes"]),
        },
    )
