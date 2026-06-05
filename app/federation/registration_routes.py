"""
Brigade federated-apps registration (admin).

  POST   /api/v1/admin/federated-apps/register   {manifest_url}
  GET    /api/v1/admin/federated-apps            list registered apps
  POST   /api/v1/admin/federated-apps/{name}/refresh
  DELETE /api/v1/admin/federated-apps/{name}

Register fetches the app's /.well-known/mcps.json over plain HTTPS, validates it
against the federation spec schema (app.federation.manifest_schema), and stores
the parsed registration. Admin-only. The manifest fetch has SSRF guards: HTTPS
only, short timeout, response-size cap.
"""
from __future__ import annotations

import logging
from typing import Annotated
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.middleware import AuthUser, require_admin
from app.db.database import get_session
from app.federation.manifest_schema import extract_registration, validate_manifest
from app.federation.registry import FederatedAppRepository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/admin/federated-apps", tags=["federation-admin"])

_FETCH_TIMEOUT = 10.0
_MAX_MANIFEST_BYTES = 256 * 1024  # 256 KB is plenty for a manifest


class RegisterRequest(BaseModel):
    manifest_url: str


async def _fetch_manifest(manifest_url: str) -> dict:
    """Fetch + parse a manifest with basic SSRF/abuse guards. Raises HTTPException."""
    parsed = urlparse(manifest_url)
    if parsed.scheme != "https":
        raise HTTPException(status_code=400, detail="manifest_url must be https")
    if not parsed.hostname:
        raise HTTPException(status_code=400, detail="manifest_url has no host")
    try:
        async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT, follow_redirects=False) as client:
            resp = await client.get(manifest_url, headers={"Accept": "application/json"})
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"manifest fetch failed: {exc}") from exc
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"manifest fetch returned {resp.status_code}")
    if len(resp.content) > _MAX_MANIFEST_BYTES:
        raise HTTPException(status_code=413, detail="manifest too large")
    try:
        return resp.json()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"manifest is not valid JSON: {exc}") from exc


async def _ingest(manifest_url: str, doc: dict, session: AsyncSession) -> dict:
    ok, errors = validate_manifest(doc)
    if not ok:
        raise HTTPException(status_code=400, detail={"manifest_invalid": errors})
    reg = extract_registration(doc)
    repo = FederatedAppRepository(session)
    # Key by the audience slug (stable, URL-safe, what the JWT `aud` pins), not
    # the manifest's display `name`. The display name stays in manifest_raw.
    return await repo.upsert(
        name=reg["expected_audience"],
        namespace=reg["tool_namespace"],
        expected_audience=reg["expected_audience"],
        manifest_url=manifest_url,
        mcp_endpoint=reg["mcp_endpoint"],
        version=reg.get("version"),
        tools=reg.get("tools", []),
        manifest_raw=doc,
    )


@router.post("/register", status_code=201)
async def register_app(
    body: RegisterRequest,
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_admin)] = None,
):
    """Fetch + validate + store a federated app's manifest."""
    doc = await _fetch_manifest(body.manifest_url)
    result = await _ingest(body.manifest_url, doc, session)
    logger.info("Registered federated app '%s' (namespace=%s, %d tools)",
                result["name"], result["namespace"], result["tool_count"])
    return result


@router.get("")
async def list_apps(
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_admin)] = None,
):
    """List all registered federated apps with status."""
    return {"apps": await FederatedAppRepository(session).list_all()}


@router.post("/{name}/refresh")
async def refresh_app(
    name: str,
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_admin)] = None,
):
    """Re-ingest the stored manifest URL (in case the app added/changed tools)."""
    repo = FederatedAppRepository(session)
    existing = await repo.get(name)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"federated app '{name}' not found")
    manifest_url = existing.manifest_url
    try:
        doc = await _fetch_manifest(manifest_url)
        return await _ingest(manifest_url, doc, session)
    except HTTPException as exc:
        await repo.mark_error(name, str(exc.detail))
        raise


@router.delete("/{name}")
async def unregister_app(
    name: str,
    session: AsyncSession = Depends(get_session),
    user: Annotated[AuthUser, Depends(require_admin)] = None,
):
    """Unregister a federated app."""
    ok = await FederatedAppRepository(session).delete(name)
    if not ok:
        raise HTTPException(status_code=404, detail=f"federated app '{name}' not found")
    logger.info("Unregistered federated app '%s'", name)
    return {"message": "unregistered", "name": name}
