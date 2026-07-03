"""
OIDC (Keycloak) Authentication Routes

Implements the Authorization Code flow with PKCE against the Unicorn Hub
Keycloak realm. Exposes:

- GET  /auth/oidc/login     -> returns {authUrl} for the frontend to redirect to
- GET  /auth/oidc/callback  -> exchanges code for tokens, sets session cookie
- POST /auth/oidc/logout    -> clears session, returns Keycloak end-session URL
- GET  /auth/oidc/logout    -> convenience redirect variant of logout
- GET  /auth/me             -> current user from session/JWT
- GET  /auth/oidc/user      -> same as /auth/me (frontend-compatible alias)
- POST /auth/oidc/refresh   -> exchange refresh_token for new tokens

Auxiliary endpoints used by the Brigade frontend (permissions, tool access,
upgrade info) return benign defaults here so the UI never breaks - richer
entitlement data can be layered on later.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import secrets
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

from app.auth.keycloak import (
    KeycloakValidationError,
    issuer,
    keycloak_enabled,
    validate_token as kc_validate_token,
)
from app.auth.middleware import (
    AuthUser,
    OIDC_SESSION_COOKIE,
    get_current_user_optional,
    validate_bearer_token,
)
from app.auth.roles import UserRole

logger = logging.getLogger(__name__)

router = APIRouter()


# --- Configuration helpers --------------------------------------------------

def _env(key: str, default: Optional[str] = None) -> Optional[str]:
    val = os.getenv(key)
    if val is None or val == "":
        return default
    return val


def _auth_endpoint() -> str:
    return _env(
        "OIDC_AUTH_ENDPOINT",
        f"{issuer().rstrip('/')}/protocol/openid-connect/auth",
    )


def _token_endpoint() -> str:
    return _env(
        "OIDC_TOKEN_ENDPOINT",
        f"{issuer().rstrip('/')}/protocol/openid-connect/token",
    )


def _userinfo_endpoint() -> str:
    return _env(
        "OIDC_USERINFO_ENDPOINT",
        f"{issuer().rstrip('/')}/protocol/openid-connect/userinfo",
    )


def _end_session_endpoint() -> str:
    return _env(
        "OIDC_END_SESSION_ENDPOINT",
        f"{issuer().rstrip('/')}/protocol/openid-connect/logout",
    )


def _client_id() -> str:
    return _env("KEYCLOAK_CLIENT_ID", "brigade")


def _client_secret() -> Optional[str]:
    return _env("KEYCLOAK_CLIENT_SECRET")


def _callback_url() -> str:
    return _env(
        "BRIGADE_CALLBACK_URL",
        "https://brigade.magicunicorn.dev/api/auth/oidc/callback",
    )


def _frontend_base_url() -> str:
    # Where to send the browser after a successful or failed login.
    # Defaults to the brigade root so relative hash-routes still work.
    return _env("BRIGADE_FRONTEND_URL", "https://brigade.magicunicorn.dev")


def _cookie_secure() -> bool:
    # Secure cookies in prod; allow override in dev via env.
    return (_env("COOKIE_SECURE", "true") or "true").lower() == "true"


# --- In-memory PKCE + state store (single-process acceptable for Brigade) ---
# For multi-replica setups, move this to Redis. Each entry is (code_verifier,
# redirect_after, created_at).
_pkce_store: Dict[str, Dict[str, Any]] = {}
_PKCE_TTL_SECONDS = 600  # 10 minutes


def _prune_pkce_store() -> None:
    cutoff = time.time() - _PKCE_TTL_SECONDS
    stale = [k for k, v in _pkce_store.items() if v.get("created_at", 0) < cutoff]
    for k in stale:
        _pkce_store.pop(k, None)


def _generate_pkce_pair() -> tuple[str, str]:
    """Return (code_verifier, code_challenge) using S256."""
    verifier = secrets.token_urlsafe(64)[:128]
    challenge_bytes = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(challenge_bytes).decode("ascii").rstrip("=")
    return verifier, challenge


# --- Response models --------------------------------------------------------

class LoginResponse(BaseModel):
    authUrl: str
    state: str


class RefreshRequest(BaseModel):
    refresh_token: str


class CheckPermissionRequest(BaseModel):
    permission: str


# --- Routes -----------------------------------------------------------------

@router.get("/auth/oidc/login", response_model=LoginResponse, tags=["auth"])
async def oidc_login(
    request: Request,
    redirect_after: Optional[str] = Query(
        None,
        description="Optional frontend path to return to after login (e.g. /dashboard)",
    ),
):
    """
    Start the OIDC login flow.

    Returns a JSON payload with the Keycloak ``authUrl`` the frontend should
    redirect the browser to. Uses PKCE (S256) and a one-time ``state`` value
    to protect against CSRF.

    When the browser NAVIGATES here directly (Accept: text/html — e.g. the
    401 handler set window.location to this endpoint), respond with a 302
    into Keycloak instead of showing the JSON payload.
    """
    if not keycloak_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Keycloak SSO is not enabled (BRIGADE_USE_KEYCLOAK=false)",
        )

    _prune_pkce_store()

    state = secrets.token_urlsafe(32)
    verifier, challenge = _generate_pkce_pair()
    _pkce_store[state] = {
        "code_verifier": verifier,
        "redirect_after": redirect_after or "/auth/callback",
        "created_at": time.time(),
    }

    params = {
        "client_id": _client_id(),
        "redirect_uri": _callback_url(),
        "response_type": "code",
        "scope": "openid profile email",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    auth_url = f"{_auth_endpoint()}?{urlencode(params)}"
    logger.info("OIDC login initiated (state=%s)", state[:8])

    if "text/html" in (request.headers.get("accept") or ""):
        return RedirectResponse(auth_url, status_code=302)

    return LoginResponse(authUrl=auth_url, state=state)


@router.get("/auth/oidc/callback", tags=["auth"])
async def oidc_callback(
    request: Request,
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    error_description: Optional[str] = Query(None),
):
    """
    OIDC redirect callback.

    Exchanges the authorization ``code`` for an access token, validates it,
    sets a session cookie, and redirects the browser back to the frontend.
    """
    frontend = _frontend_base_url().rstrip("/")

    if error:
        msg = error_description or error
        logger.warning("OIDC callback returned error: %s", msg)
        return RedirectResponse(
            url=f"{frontend}/auth/callback?error={msg}",
            status_code=302,
        )

    if not code or not state:
        return RedirectResponse(
            url=f"{frontend}/auth/callback?error=missing_code_or_state",
            status_code=302,
        )

    _prune_pkce_store()
    pkce_entry = _pkce_store.pop(state, None)
    if pkce_entry is None:
        logger.warning("OIDC callback with unknown state=%s", state[:8])
        return RedirectResponse(
            url=f"{frontend}/auth/callback?error=invalid_state",
            status_code=302,
        )

    verifier = pkce_entry["code_verifier"]
    redirect_after = pkce_entry.get("redirect_after") or "/auth/callback"

    # Exchange code for tokens at Keycloak
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": _callback_url(),
        "client_id": _client_id(),
        "code_verifier": verifier,
    }
    secret = _client_secret()
    if secret:
        data["client_secret"] = secret

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                _token_endpoint(),
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
    except httpx.HTTPError as exc:
        logger.error("Token exchange network error: %s", exc)
        return RedirectResponse(
            url=f"{frontend}/auth/callback?error=token_exchange_failed",
            status_code=302,
        )

    if resp.status_code != 200:
        logger.warning(
            "Token exchange failed: status=%s body=%s",
            resp.status_code,
            resp.text[:500],
        )
        return RedirectResponse(
            url=f"{frontend}/auth/callback?error=token_exchange_rejected",
            status_code=302,
        )

    tokens = resp.json()
    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")
    expires_in = int(tokens.get("expires_in", 3600) or 3600)

    if not access_token:
        logger.error("Token response missing access_token")
        return RedirectResponse(
            url=f"{frontend}/auth/callback?error=no_access_token",
            status_code=302,
        )

    # Validate the token to confirm issuer/signature before setting cookie.
    try:
        await kc_validate_token(access_token)
    except KeycloakValidationError as exc:
        logger.error("Issued token failed validation: %s", exc)
        return RedirectResponse(
            url=f"{frontend}/auth/callback?error=invalid_token",
            status_code=302,
        )

    # Normalize redirect target to frontend path
    if redirect_after.startswith("http"):
        landing = redirect_after
    else:
        landing = f"{frontend}{redirect_after if redirect_after.startswith('/') else '/' + redirect_after}"

    # Append login=success for AuthCallback.jsx to pick up
    sep = "&" if "?" in landing else "?"
    landing = f"{landing}{sep}login=success"

    response = RedirectResponse(url=landing, status_code=302)
    response.set_cookie(
        key=OIDC_SESSION_COOKIE,
        value=access_token,
        max_age=expires_in,
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
        path="/",
    )
    if refresh_token:
        response.set_cookie(
            key=f"{OIDC_SESSION_COOKIE}_refresh",
            value=refresh_token,
            max_age=int(tokens.get("refresh_expires_in", expires_in * 10) or expires_in * 10),
            httponly=True,
            secure=_cookie_secure(),
            samesite="lax",
            path="/",
        )
    logger.info("OIDC login completed, session cookie set")
    return response


@router.post("/auth/oidc/logout", tags=["auth"])
async def oidc_logout_post(request: Request):
    """Clear the session cookie and return the Keycloak end-session URL."""
    refresh_token = request.cookies.get(f"{OIDC_SESSION_COOKIE}_refresh")

    # Best-effort revoke refresh token at Keycloak.
    if refresh_token:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    _end_session_endpoint(),
                    data={
                        "client_id": _client_id(),
                        "client_secret": _client_secret() or "",
                        "refresh_token": refresh_token,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
        except httpx.HTTPError as exc:
            logger.debug("Best-effort logout revoke failed: %s", exc)

    end_session_url = (
        f"{_end_session_endpoint()}?"
        f"{urlencode({'client_id': _client_id(), 'post_logout_redirect_uri': _frontend_base_url()})}"
    )
    response = JSONResponse({"loggedOut": True, "endSessionUrl": end_session_url})
    response.delete_cookie(OIDC_SESSION_COOKIE, path="/")
    response.delete_cookie(f"{OIDC_SESSION_COOKIE}_refresh", path="/")
    return response


@router.get("/auth/oidc/logout", tags=["auth"])
async def oidc_logout_get(request: Request):
    """Browser-friendly logout that redirects to the Keycloak end-session URL."""
    frontend = _frontend_base_url()
    end_session_url = (
        f"{_end_session_endpoint()}?"
        f"{urlencode({'client_id': _client_id(), 'post_logout_redirect_uri': frontend})}"
    )
    response = RedirectResponse(url=end_session_url, status_code=302)
    response.delete_cookie(OIDC_SESSION_COOKIE, path="/")
    response.delete_cookie(f"{OIDC_SESSION_COOKIE}_refresh", path="/")
    return response


@router.post("/auth/oidc/refresh", tags=["auth"])
async def oidc_refresh(body: RefreshRequest):
    """Exchange a refresh_token for a new access_token at Keycloak."""
    if not keycloak_enabled():
        raise HTTPException(status_code=503, detail="Keycloak SSO disabled")

    data = {
        "grant_type": "refresh_token",
        "refresh_token": body.refresh_token,
        "client_id": _client_id(),
    }
    secret = _client_secret()
    if secret:
        data["client_secret"] = secret

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                _token_endpoint(),
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
    except httpx.HTTPError as exc:
        logger.error("Refresh failed: %s", exc)
        raise HTTPException(status_code=502, detail="refresh_failed") from exc

    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail=resp.json())

    return resp.json()


def _auth_user_to_dict(user: AuthUser) -> Dict[str, Any]:
    return {
        "id": user.id,
        "userId": user.user_id,
        "email": user.email,
        "name": user.key_name,
        "role": user.role.value if isinstance(user.role, UserRole) else str(user.role),
        "authSource": user.auth_source,
        "permissions": user.permissions or [],
    }


@router.get("/auth/config", tags=["auth"])
async def auth_config():
    """Public deployment flags the frontend uses to gate nav items and auth UI.

    Safe to expose unauthenticated: booleans and a version string only.
    """
    sso = keycloak_enabled()
    return {
        "sso_enabled": sso,
        # Native email/password signup defaults OFF when SSO owns identity so
        # register can't mint shadow accounts that bypass Keycloak.
        "native_register_enabled": os.getenv(
            "BRIGADE_ALLOW_NATIVE_REGISTER", "false" if sso else "true"
        ).lower() == "true",
        "langflow_enabled": os.getenv("LANGFLOW_ENABLED", "false").lower() == "true",
        "falkordb_enabled": os.getenv("FALKORDB_ENABLED", "false").lower() == "true",
        "version": os.getenv("API_VERSION", "1.17.0"),
        "environment": os.getenv("ENVIRONMENT", "development"),
    }


@router.get("/auth/me", tags=["auth"])
async def auth_me(
    user: Optional[AuthUser] = Depends(get_current_user_optional),
):
    """Return the current authenticated user (session cookie, Bearer, or API key)."""
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return _auth_user_to_dict(user)


@router.get("/auth/oidc/user", tags=["auth"])
async def oidc_user(
    user: Optional[AuthUser] = Depends(get_current_user_optional),
):
    """Frontend-compatible alias of /auth/me."""
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    data = _auth_user_to_dict(user)
    # Frontend expects a ``tier`` hint and ``roles`` array for legacy UI code.
    data["tier"] = data["role"]
    data["roles"] = data["permissions"]
    return data


@router.get("/auth/oidc/permissions", tags=["auth"])
async def oidc_permissions(
    user: Optional[AuthUser] = Depends(get_current_user_optional),
):
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {
        "role": user.role.value if isinstance(user.role, UserRole) else str(user.role),
        "permissions": user.permissions or [],
    }


@router.post("/auth/oidc/check-permission", tags=["auth"])
async def oidc_check_permission(
    body: CheckPermissionRequest,
    user: Optional[AuthUser] = Depends(get_current_user_optional),
):
    if not user:
        return {"allowed": False, "reason": "not_authenticated"}
    return {"allowed": user.has_permission(body.permission)}


@router.get("/auth/oidc/tool-access", tags=["auth"])
async def oidc_tool_access(
    tool: str = Query(...),
    user: Optional[AuthUser] = Depends(get_current_user_optional),
):
    if not user:
        return {"allowed": False, "tool": tool, "reason": "not_authenticated"}
    # Admins get everything; operators get chat/read tools; viewers read-only.
    if user.role == UserRole.ADMIN:
        return {"allowed": True, "tool": tool}
    if user.role == UserRole.OPERATOR:
        return {"allowed": True, "tool": tool}
    # Viewer: only allow read-style tools (naming heuristic)
    read_like = any(tool.lower().startswith(p) for p in ("get_", "list_", "read_", "search_"))
    return {"allowed": read_like, "tool": tool}


@router.get("/auth/oidc/upgrade-info", tags=["auth"])
async def oidc_upgrade_info(feature: str = Query(...)):
    # Static default; real entitlement data can be added later.
    return {
        "feature": feature,
        "requiredTier": "operator",
        "description": f"{feature} requires operator or admin access.",
        "contact": "support@magicunicorn.tech",
    }
