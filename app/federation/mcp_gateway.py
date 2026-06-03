"""
Brigade federation MCP gateway (POST /mcp).

The single endpoint a suite customer wires into Claude Desktop / Cursor / Cline /
Zed / Continue. Speaks MCP JSON-RPC (initialize, tools/list, tools/call). It
exposes the union of the customer's federated apps' tools, namespaced. On
tools/call it strips the namespace, mints a short-lived RS256 customer-context
JWT for the target app, proxies the call to the app's mcp_endpoint, and forwards
the result.

Identity (see project_brigade_federation_identity_model): sub = the
authenticated customer's email, the shared identifier Brigade has today. Apps
resolve by email (eg PO's validateKeycloakUser email fallback). Upgrade to the
opaque uchub sub once Brigade stores keycloakId on its User at OIDC login.
The minted token carries the suite-canonical claims (SUITE-IDENTITY §0.1): `act`
records the Brigade->caller delegation chain; `workspace_id`/`entitlements` are
threaded once resolved from uc-registry (Phase 1). `org_id` is retired entirely.

Locked properties:
- customer-context JWT: sub = the caller, never a brigade-service identity
- fresh jti + iat per call (the mint enforces this; no JWT reuse)
- upstream status pass-through: forward the app's status; 502 only when the app
  fails to respond (timeout / connection / malformed). Never collapse to 500.
- structured per-call log {customer, org, app, tool, status, latency_ms, jti}
"""
from __future__ import annotations

import json
import logging
import time
from typing import Annotated, Any, Optional

import httpx
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.middleware import AuthUser, require_api_key
from app.db.database import get_session
from app.federation.catalog import build_catalog, resolve_customer_rank, resolve_tool, tool_allowed
from app.federation.mint import mint_app_jwt
from app.federation.registry import FederatedAppRepository

logger = logging.getLogger(__name__)
router = APIRouter(tags=["federation-mcp"])

_PROTOCOL_VERSION = "2025-06-18"
_PROXY_TIMEOUT = 30.0


def _rpc_result(req_id: Any, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _rpc_error(req_id: Any, code: int, message: str, data: Any = None) -> dict:
    err: dict = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": req_id, "error": err}


def _public_tool(entry: dict) -> dict:
    """Strip the _-prefixed routing metadata before returning to the MCP client."""
    return {
        "name": entry["name"],
        "description": entry.get("description", ""),
        "inputSchema": entry.get("input_schema", {"type": "object"}),
    }


async def _customer_context(user: AuthUser) -> tuple[str, int]:
    """Return (customer_sub, tier_rank) for the authenticated caller."""
    sub = getattr(user, "email", None) or getattr(user, "user_id", None) or getattr(user, "id", None)
    rank = 0
    try:
        from app.integrations.ops_center_billing import get_billing_state
        state = await get_billing_state(getattr(user, "email", "") or "")
        rank = resolve_customer_rank(state.get("subscription_tier"))
    except Exception as exc:  # billing is best-effort; fail-closed to free
        logger.warning("billing tier lookup failed for %s: %s; defaulting to free", sub, exc)
    return str(sub), rank


async def _handle_tools_call(
    req_id: Any, params: dict, user: AuthUser, customer_sub: str, rank: int, session: AsyncSession
) -> dict:
    name = (params or {}).get("name", "")
    arguments = (params or {}).get("arguments", {}) or {}
    apps = await FederatedAppRepository(session).list_active()

    resolved = resolve_tool(apps, name)
    if resolved is None:
        return _rpc_error(req_id, -32602, f"unknown tool: {name}")
    # Defense in depth: re-check tier at invoke (the client's cached list may be stale).
    if not tool_allowed(resolved["tool"], rank):
        return _rpc_error(req_id, -32602, f"tool not available for your tier: {name}")

    aud = resolved["expected_audience"]
    jwt = mint_app_jwt(
        sub=customer_sub,
        aud=aud,
        # Suite-canonical claims (SUITE-IDENTITY §0.1). `act` records the
        # delegation chain: the actor on the customer-MCP path is Brigade acting
        # for the caller. `workspace_id`/`entitlements` are threaded once
        # resolved from uc-registry (handoff §3.3, Phase 1); omitted (not
        # invented from email — D2) until then. `org_id` is gone.
        act={"sub": customer_sub, "client_id": "brigade"},
        scopes=resolved["scopes_required"],
    )
    # jti for the audit log (decode is unverified, it is our own freshly minted token).
    try:
        from jose import jwt as _jose
        jti = _jose.get_unverified_claims(jwt).get("jti")
    except Exception:
        jti = None

    started = time.monotonic()
    upstream_status = None
    try:
        async with httpx.AsyncClient(timeout=_PROXY_TIMEOUT, follow_redirects=False) as client:
            resp = await client.post(
                resolved["mcp_endpoint"],
                headers={"Authorization": f"Bearer {jwt}", "Content-Type": "application/json"},
                json={"jsonrpc": "2.0", "id": req_id, "method": "tools/call",
                      "params": {"name": resolved["tool_name"], "arguments": arguments}},
            )
        upstream_status = resp.status_code
        latency_ms = int((time.monotonic() - started) * 1000)
        _log_call(customer_sub, aud, resolved["tool_name"], upstream_status, latency_ms, jti)
        # Status pass-through: forward the app's body verbatim. The HTTP status is
        # carried back to the client by the outer route via the _status marker.
        try:
            body = resp.json()
        except ValueError:
            body = {"raw": resp.text[:4000]}
        if resp.status_code >= 400:
            return {"_status": resp.status_code, "payload": _rpc_error(
                req_id, -32000, f"upstream {aud} returned {resp.status_code}", data=body)}
        # A well-formed app returns a JSON-RPC envelope; forward its result/error as-is.
        if isinstance(body, dict) and ("result" in body or "error" in body):
            body.setdefault("id", req_id)
            return {"_status": 200, "payload": body}
        return {"_status": 200, "payload": _rpc_result(req_id, body)}
    except httpx.HTTPError as exc:
        latency_ms = int((time.monotonic() - started) * 1000)
        _log_call(customer_sub, aud, resolved["tool_name"], "no_response", latency_ms, jti, error=str(exc))
        return {"_status": 502, "payload": _rpc_error(
            req_id, -32001, f"{aud} did not respond", data=str(exc))}


def _log_call(customer: str, app: str, tool: str, status, latency_ms: int,
              jti: Optional[str], error: Optional[str] = None) -> None:
    rec = {"evt": "federation_proxy_call", "customer": customer, "app": app,
           "tool": tool, "status": status, "latency_ms": latency_ms, "jti": jti}
    if error:
        rec["error"] = error
    logger.info(json.dumps(rec))


@router.post("/mcp")
async def mcp_gateway(
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """MCP JSON-RPC gateway. Auth via the customer's Brigade credential."""
    from fastapi.responses import JSONResponse
    try:
        msg = await request.json()
    except Exception:
        return JSONResponse(_rpc_error(None, -32700, "parse error"), status_code=400)

    req_id = msg.get("id")
    method = msg.get("method")
    params = msg.get("params") or {}

    if method == "initialize":
        return _rpc_result(req_id, {
            "protocolVersion": _PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "brigade-federation", "version": "1.0.0"},
        })
    if method == "notifications/initialized":
        return JSONResponse({}, status_code=202)

    customer_sub, rank = await _customer_context(user)

    if method == "tools/list":
        apps = await FederatedAppRepository(session).list_active()
        catalog = build_catalog(apps, rank)
        return _rpc_result(req_id, {"tools": [_public_tool(t) for t in catalog]})

    if method == "tools/call":
        out = await _handle_tools_call(req_id, params, user, customer_sub, rank, session)
        return JSONResponse(out["payload"], status_code=out.get("_status", 200))

    return _rpc_error(req_id, -32601, f"method not found: {method}")
