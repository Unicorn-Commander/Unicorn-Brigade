"""Knowledge-Ops grounding tools — let a Brigade agent ground its answers in the
fleet's INTERNAL knowledge base (SOPs, runbooks, hardware/installer docs, org
memory) instead of hallucinating company/infra facts, AND durably SAVE new
learnings back into that KB.

Knowledge-Ops is the federation/dispatcher KB service (FastAPI, container
``knowledge-ops`` on bigboy, internal ``:8765`` on the same ``unicorn-network``
the Brigade runtime is on). It federates a wiki, file-index, Qdrant, FalkorDB
org-memory, and Center Deep behind:

  * ``POST /kb.ground``      -> a grounded answer with cited sources
  * ``POST /kb.search``      -> raw matching passages (for the model to cite itself)
  * ``POST /kb.upsert_doc``  -> create/update a versioned wiki doc (the WRITE path)

(The routes use a dot, not a slash — ``/kb.ground``, not ``/kb/ground``.)

These tools are thin, defensive HTTP clients: any missing config, HTTP error,
timeout, or non-JSON body returns gracefully and NEVER raises into the tool loop.
Registered only when ``KNOWLEDGE_OPS_URL`` is set (see tool_resolver).

When all three ``KNOWLEDGE_OPS_OIDC_*`` credentials are configured, requests use
an in-process Keycloak client-credentials bearer. Otherwise the legacy static
``KNOWLEDGE_OPS_TOKEN`` bearer is used when present, and otherwise no bearer is
sent. If an OIDC mint fails and a static token is configured, the request falls
back to that token once and logs the route.
"""

import asyncio
import logging
import math
import os
import re
import time
from typing import Any, Optional

import httpx

from app.llm.ops_center_client import ToolDefinition, ToolParameter

logger = logging.getLogger(__name__)

# In-cluster URL; on bigboy the Brigade runtime reaches the KB by DNS name.
KNOWLEDGE_OPS_URL = os.getenv("KNOWLEDGE_OPS_URL", "http://knowledge-ops:8765")
# Legacy optional static bearer. Never logged.
KNOWLEDGE_OPS_TOKEN = os.getenv("KNOWLEDGE_OPS_TOKEN", "")
# Keycloak client-credentials configuration. When all three required values are
# set, this takes precedence over the legacy static bearer unless minting fails.
KNOWLEDGE_OPS_OIDC_TOKEN_URL = os.getenv("KNOWLEDGE_OPS_OIDC_TOKEN_URL", "")
KNOWLEDGE_OPS_OIDC_CLIENT_ID = os.getenv("KNOWLEDGE_OPS_OIDC_CLIENT_ID", "")
KNOWLEDGE_OPS_OIDC_CLIENT_SECRET = os.getenv("KNOWLEDGE_OPS_OIDC_CLIENT_SECRET", "")
KNOWLEDGE_OPS_OIDC_AUDIENCE = os.getenv("KNOWLEDGE_OPS_OIDC_AUDIENCE", "")
KNOWLEDGE_OPS_OIDC_SCOPE = os.getenv("KNOWLEDGE_OPS_OIDC_SCOPE", "")
KNOWLEDGE_OPS_TIMEOUT = float(os.getenv("KNOWLEDGE_OPS_TIMEOUT", "30.0"))
_DEFAULT_K = 5
_USER_AGENT = "unicorn-brigade-ko-client/1.0"
_TOKEN_CACHE: dict[str, Any] = {"token": None, "exp": 0.0}
_TOKEN_CACHE_LOCK = asyncio.Lock()
_TOKEN_REFRESH_SKEW = 30.0
# Defaults for agent-authored docs. Scope is Knowledge-Ops' free-form RLS filter
# ("global" = fleet-wide readable); owner is a denormalized attribution label.
_WRITE_SCOPE = os.getenv("KNOWLEDGE_OPS_WRITE_SCOPE", "global")
_WRITE_OWNER = os.getenv("KNOWLEDGE_OPS_WRITE_OWNER", "brigade-agent")
_WRITE_CATEGORY = os.getenv("KNOWLEDGE_OPS_WRITE_CATEGORY", "learnings")


def _oidc_configured() -> bool:
    """Return whether the complete client-credentials configuration is present."""
    return bool(
        KNOWLEDGE_OPS_OIDC_TOKEN_URL
        and KNOWLEDGE_OPS_OIDC_CLIENT_ID
        and KNOWLEDGE_OPS_OIDC_CLIENT_SECRET
    )


async def _get_oidc_token(*, force_refresh: bool = False) -> Optional[str]:
    """Mint or return the cached Knowledge-Ops client-credentials bearer."""
    if not _oidc_configured():
        return None

    async with _TOKEN_CACHE_LOCK:
        if force_refresh:
            _TOKEN_CACHE.update(token=None, exp=0.0)

        now = time.monotonic()
        cached = _TOKEN_CACHE.get("token")
        if cached and now < float(_TOKEN_CACHE.get("exp", 0.0)):
            return cached

        data = {
            "grant_type": "client_credentials",
            "client_id": KNOWLEDGE_OPS_OIDC_CLIENT_ID,
            "client_secret": KNOWLEDGE_OPS_OIDC_CLIENT_SECRET,
        }
        if KNOWLEDGE_OPS_OIDC_AUDIENCE:
            data["audience"] = KNOWLEDGE_OPS_OIDC_AUDIENCE
        if KNOWLEDGE_OPS_OIDC_SCOPE:
            data["scope"] = KNOWLEDGE_OPS_OIDC_SCOPE
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": _USER_AGENT,
        }
        try:
            async with httpx.AsyncClient(timeout=KNOWLEDGE_OPS_TIMEOUT) as client:
                resp = await client.post(KNOWLEDGE_OPS_OIDC_TOKEN_URL, data=data, headers=headers)
            if resp.status_code >= 400:
                logger.error("knowledge-ops OIDC token mint HTTP %s", resp.status_code)
                return None
            response_body = resp.json()
            token = response_body.get("access_token")
            if not token:
                logger.error("knowledge-ops OIDC token response missing access_token")
                return None
            try:
                expires_in = float(response_body.get("expires_in"))
            except (OverflowError, TypeError, ValueError):
                expires_in = None
            if expires_in is None or not math.isfinite(expires_in) or expires_in <= 0:
                logger.warning(
                    "knowledge-ops OIDC token response has invalid expires_in; token will not be cached"
                )
                _TOKEN_CACHE.update(token=None, exp=0.0)
                return token
            ttl = max(0.0, expires_in - _TOKEN_REFRESH_SKEW)
            _TOKEN_CACHE["token"] = token
            _TOKEN_CACHE["exp"] = time.monotonic() + ttl
            return token
        except Exception as exc:  # noqa: BLE001 - defensive boundary; never expose credentials
            logger.error("knowledge-ops OIDC token mint failed: %s", type(exc).__name__)
            return None


async def _get_bearer(
    *, route: str = "", force_refresh: bool = False
) -> tuple[Optional[str], bool]:
    """Return ``(bearer, uses_oidc)`` while preserving the static-token fallback."""
    if _oidc_configured():
        token = await _get_oidc_token(force_refresh=force_refresh)
        if token:
            return token, True
        if KNOWLEDGE_OPS_TOKEN:
            logger.warning(
                "knowledge-ops OIDC mint failed; falling back to static token route=%s", route
            )
            return KNOWLEDGE_OPS_TOKEN, False
        return None, True
    if KNOWLEDGE_OPS_TOKEN:
        return KNOWLEDGE_OPS_TOKEN, False
    return None, False


def _credential_rejection(route: str, status_code: int) -> dict[str, Any]:
    """Return a safe auth error and log only the route, never the response body."""
    logger.warning("knowledge-ops credential rejected route=%s", route)
    return {"error": f"knowledge-ops rejected the credential ({status_code})"}


async def _post(route: str, body: dict[str, Any]) -> dict[str, Any]:
    """One defensive POST to a Knowledge-Ops route. Returns a dict; never raises."""
    url = f"{KNOWLEDGE_OPS_URL.rstrip('/')}/{route}"
    try:
        token, uses_oidc = await _get_bearer(route=route)
        if uses_oidc and not token:
            return {"error": "knowledge-ops could not obtain an OIDC credential"}

        headers = {"Content-Type": "application/json", "User-Agent": _USER_AGENT}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        async with httpx.AsyncClient(timeout=KNOWLEDGE_OPS_TIMEOUT) as client:
            resp = await client.post(url, headers=headers, json=body)

            if resp.status_code in (401, 403) and uses_oidc:
                refreshed_token, _ = await _get_bearer(route=route, force_refresh=True)
                if refreshed_token:
                    headers["Authorization"] = f"Bearer {refreshed_token}"
                    resp = await client.post(url, headers=headers, json=body)

        if resp.status_code in (401, 403):
            return _credential_rejection(route, resp.status_code)
        if resp.status_code >= 400:
            logger.warning("knowledge-ops %s HTTP %s", route, resp.status_code)
            return {"error": f"knowledge-ops {route} HTTP {resp.status_code}: {resp.text[:200]}"}
        try:
            return resp.json()
        except Exception:  # noqa: BLE001 - unexpected non-JSON 2xx
            return {"error": "knowledge-ops returned a non-JSON response"}
    except httpx.TimeoutException:
        return {"error": f"knowledge-ops {route} timed out after {KNOWLEDGE_OPS_TIMEOUT}s"}
    except Exception as exc:  # noqa: BLE001 - defensive boundary
        logger.error("knowledge-ops %s failed: %s", route, exc)
        return {"error": f"knowledge-ops {route} failed: {exc}"}


def _slug(s: str) -> str:
    """Filesystem/URL-safe slug for a wiki path segment (mirrors Knowledge-Ops)."""
    s = re.sub(r"[^a-z0-9]+", "-", (s or "").strip().lower()).strip("-")
    return s[:80] or "note"


async def _ground_handler(query: str, k: int = _DEFAULT_K, **_) -> dict[str, Any]:
    return await _post("kb.ground", {"query": query, "k": k})


async def _search_handler(query: str, k: int = _DEFAULT_K, **_) -> dict[str, Any]:
    return await _post("kb.search", {"query": query, "k": k})


async def _save_handler(
    title: str,
    content: str,
    category: Optional[str] = None,
    scope: Optional[str] = None,
    **_,
) -> dict[str, Any]:
    """Create/update a wiki doc in Knowledge-Ops. Idempotent on (category,title)."""
    if not title or not title.strip():
        return {"error": "a non-empty 'title' is required"}
    if not content or not content.strip():
        return {"error": "non-empty 'content' (Markdown body) is required"}
    cat = _slug(category or _WRITE_CATEGORY)
    path = f"{cat}/{_slug(title)}.md"
    body = content.strip()
    # Knowledge-Ops derives the doc title from the first '# ' heading — make sure
    # there is one so the saved doc is titled correctly.
    if not body.lstrip().startswith("#"):
        body = f"# {title.strip()}\n\n{body}"
    result = await _post(
        "kb.upsert_doc",
        {"path": path, "md": body, "scope": scope or _WRITE_SCOPE, "owner": _WRITE_OWNER},
    )
    if isinstance(result, dict) and result.get("id"):
        return {
            "ok": True,
            "id": result["id"],
            "path": path,
            "scope": scope or _WRITE_SCOPE,
            "note": "Saved to the internal Knowledge-Ops KB; retrievable via knowledge_ops_search / knowledge_ops_ground.",
        }
    return result


KNOWLEDGE_OPS_GROUND_TOOL = ToolDefinition(
    name="knowledge_ops_ground",
    description=(
        "Ground a question in the fleet's INTERNAL Knowledge-Ops KB (SOPs, runbooks, "
        "hardware/installer/gateway docs, org memory) and get back a grounded answer "
        "with cited sources. Use this BEFORE answering anything about the company's own "
        "infrastructure, hardware, procedures, or history — do not rely on memory for "
        "internal facts."
    ),
    parameters=[
        ToolParameter(name="query", type="string", description="The question to ground.", required=True),
        ToolParameter(name="k", type="number", description="How many sources to pull (default 5).", required=False, default=_DEFAULT_K),
    ],
    handler=_ground_handler,
)

KNOWLEDGE_OPS_SEARCH_TOOL = ToolDefinition(
    name="knowledge_ops_search",
    description=(
        "Search the internal Knowledge-Ops KB for raw matching passages (text + source "
        "path + score) so you can read and cite them yourself. Use when you want the "
        "underlying runbook/SOP excerpts rather than a synthesized answer."
    ),
    parameters=[
        ToolParameter(name="query", type="string", description="What to look for in the internal docs.", required=True),
        ToolParameter(name="k", type="number", description="Number of passages (default 5).", required=False, default=_DEFAULT_K),
    ],
    handler=_search_handler,
)

KNOWLEDGE_OPS_SAVE_TOOL = ToolDefinition(
    name="knowledge_ops_save",
    description=(
        "Save a learning, finding, SOP, decision, or summary to the fleet's INTERNAL "
        "Knowledge-Ops KB so you and other agents can retrieve it later (via "
        "knowledge_ops_search / knowledge_ops_ground). Use this to durably record "
        "something worth remembering across conversations — a resolved procedure, a fact "
        "about the company's infrastructure, a decision and its rationale, or a distilled "
        "summary. Saving with the same title UPDATES that doc (versioned). Do NOT save "
        "secrets, credentials, API keys, or private personal data."
    ),
    parameters=[
        ToolParameter(name="title", type="string", description="Short title/subject — also the key: the same title updates the same doc.", required=True),
        ToolParameter(name="content", type="string", description="The note body in Markdown.", required=True),
        ToolParameter(name="category", type="string", description="Folder to file it under, e.g. 'learnings', 'runbooks', 'infrastructure' (default 'learnings').", required=False, default=_WRITE_CATEGORY),
        ToolParameter(name="scope", type="string", description="Visibility scope; 'global' = fleet-wide (default).", required=False, default=_WRITE_SCOPE),
    ],
    handler=_save_handler,
)


KNOWLEDGE_OPS_TOOLS: dict[str, ToolDefinition] = {
    "knowledge_ops_ground": KNOWLEDGE_OPS_GROUND_TOOL,
    "knowledge_ops_search": KNOWLEDGE_OPS_SEARCH_TOOL,
    "knowledge_ops_save": KNOWLEDGE_OPS_SAVE_TOOL,
}
