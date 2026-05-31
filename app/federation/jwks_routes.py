"""
Brigade federation JWKS endpoint.

Publishes Brigade's RS256 public signing keys at /.well-known/jwks.json so
federated UC apps can verify Brigade-minted JWTs. Public material only, no auth,
cacheable. Current + previous keys are both served during a rotation grace
window so tokens keep verifying while a verifier's cache is warm.

Mounted at root (no /api/v1 prefix) in app/main.py.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Response

from app.federation.keys import get_keystore

router = APIRouter(tags=["federation"])

_CACHE_SECONDS = int(os.getenv("BRIGADE_JWKS_CACHE_SECONDS", "3600"))


@router.get("/.well-known/jwks.json")
async def jwks(response: Response) -> dict:
    """Brigade's public JWKS (RS256). Always reachable, no auth."""
    response.headers["Cache-Control"] = f"public, max-age={_CACHE_SECONDS}"
    return get_keystore().public_jwks()
