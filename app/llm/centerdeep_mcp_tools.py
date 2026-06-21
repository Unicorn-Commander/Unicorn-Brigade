"""Center Deep Research MCP tools — proxies into the Center Deep Research
(CD) MCP server so any Brigade agent that lists them in its ``tools`` field
gets web search / quick-answer / deep-research as callable LLM functions.

CD's MCP endpoint is FastMCP in streamable-HTTP mode (``stateless_http=True``)
sitting behind cdr-oauth2-proxy on the internal ``web`` docker network. Two
transport facts shape this module:

  * The endpoint replies ``Content-Type: text/event-stream``: a single SSE
    message framed as ``event: message\\ndata: <json>\\n\\n``. We strip the
    framing before parsing (see ``_parse_streamable_response``) — identical
    to the Project-Ops MCP transport.
  * Auth is a uchub (Keycloak) RS256 bearer minted via the
    ``client_credentials`` grant using Brigade's own client
    (``KEYCLOAK_CLIENT_ID`` / ``KEYCLOAK_CLIENT_SECRET``). A Keycloak audience
    mapper puts ``center-deep-research`` in the token's ``aud``, so the same
    Brigade client token is accepted by CD's oauth2-proxy. The token TTL is
    short (~5 min) so we mint per-call with a small in-process cache and NEVER
    persist it.

These tools are system-callable: CD search has no per-user identity, so unlike
the Project-Ops tools they do NOT set ``needs_caller_context``.
"""

import json
import logging
import os
import time
from typing import Any, Dict, Optional

import httpx

from app.llm.ops_center_client import ToolDefinition, ToolParameter

logger = logging.getLogger(__name__)

# CD MCP endpoint on the internal ``web`` docker network (via oauth2-proxy).
CDR_MCP_URL = os.getenv("CDR_MCP_URL", "http://cdr-oauth2-proxy:4180/mcp")
# uchub token endpoint (behind Cloudflare → must send a browser User-Agent).
CDR_TOKEN_URL = os.getenv(
    "CDR_TOKEN_URL",
    "https://auth.magicunicorn.dev/realms/uchub/protocol/openid-connect/token",
)
# Reuse Brigade's own uchub client; the audience mapper grants
# center-deep-research in aud. Safe defaults → no new env required.
CDR_CLIENT_ID = os.getenv("CDR_CLIENT_ID", os.getenv("KEYCLOAK_CLIENT_ID", "brigade"))
CDR_CLIENT_SECRET = os.getenv("CDR_CLIENT_SECRET", os.getenv("KEYCLOAK_CLIENT_SECRET", ""))
CDR_MCP_TIMEOUT = float(os.getenv("CDR_MCP_TIMEOUT", "120.0"))
# Cloudflare fronts the token endpoint and 1010s non-browser UAs.
_BROWSER_UA = "Mozilla/5.0"

# In-process token cache. client_credentials TTL is ~300s; refresh a little
# early. We never write the token anywhere — memory only, per process.
_TOKEN_CACHE: Dict[str, Any] = {"token": None, "exp": 0.0}
_TOKEN_REFRESH_SKEW = 30.0  # mint a fresh token this many seconds before exp
_TOKEN_MAX_TTL = float(os.getenv("CDR_TOKEN_MAX_TTL", "240.0"))  # cap cache at ~4 min


async def _get_token() -> Optional[str]:
    """Mint (or return cached) a uchub client_credentials bearer for CD.

    Caches the token in-process for up to ~4 minutes (or the token's own
    ``expires_in`` minus a small skew, whichever is shorter). Returns ``None``
    on failure — callers turn that into an error dict. The client secret is
    never logged.
    """
    now = time.time()
    cached = _TOKEN_CACHE.get("token")
    if cached and now < float(_TOKEN_CACHE.get("exp", 0.0)):
        return cached
    if not CDR_CLIENT_SECRET:
        logger.error("centerdeep-mcp: no client secret configured (CDR_CLIENT_SECRET / KEYCLOAK_CLIENT_SECRET)")
        return None
    data = {
        "grant_type": "client_credentials",
        "client_id": CDR_CLIENT_ID,
        "client_secret": CDR_CLIENT_SECRET,
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": _BROWSER_UA,
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(CDR_TOKEN_URL, data=data, headers=headers)
        if resp.status_code >= 400:
            # Redact: never echo the response body wholesale (it can't contain
            # the secret, but stay conservative) and never log the secret.
            logger.error(f"centerdeep-mcp: token mint HTTP {resp.status_code} (client_id={CDR_CLIENT_ID})")
            return None
        body = resp.json()
        token = body.get("access_token")
        if not token:
            logger.error("centerdeep-mcp: token response missing access_token")
            return None
        expires_in = float(body.get("expires_in", 300) or 300)
        ttl = min(_TOKEN_MAX_TTL, max(0.0, expires_in - _TOKEN_REFRESH_SKEW))
        _TOKEN_CACHE["token"] = token
        _TOKEN_CACHE["exp"] = now + ttl
        return token
    except Exception as exc:  # noqa: BLE001 - defensive boundary; do not surface secret
        logger.error(f"centerdeep-mcp: token mint failed: {exc}")
        return None


def _parse_streamable_response(body: str) -> Dict[str, Any]:
    """Parse CD's streamable-HTTP (SSE) reply into the JSON-RPC response.

    Short tools (``search``) reply with a single SSE event::

        event: message
        data: {"jsonrpc":"2.0","id":1,"result":{...}}

    But long-running tools (``quick_answer``, ``deep_research``) STREAM
    progress first — many ``notifications/message`` events — and the real
    JSON-RPC response is the LAST ``data:`` frame::

        data: {"jsonrpc":"2.0","method":"notifications/message",...}   <- progress
        ... (N more) ...
        data: {"jsonrpc":"2.0","id":1,"result":{...}}                  <- the answer

    So we must scan ALL ``data:`` frames and return the one carrying a
    top-level ``result``/``error`` (the response), not the first frame
    (a progress notification → empty content). Keep the last such frame.
    Falls back to plain-JSON parsing (defensive).
    """
    body = (body or "").strip()
    if not body:
        return {}
    if body.startswith("{"):
        return json.loads(body)
    response = None
    last_frame = None
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line.startswith("data:"):
            continue
        try:
            frame = json.loads(line[len("data:"):].strip())
        except json.JSONDecodeError:
            continue
        last_frame = frame
        # The JSON-RPC response carries result/error; notifications carry a
        # "method" and no result. Keep the last matching response frame.
        if isinstance(frame, dict) and ("result" in frame or "error" in frame):
            response = frame
    if response is not None:
        return response
    if last_frame is not None:
        return last_frame
    raise ValueError(f"centerdeep-mcp: no data line in response: {body[:200]}")


async def _call_mcp(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """JSON-RPC 2.0 ``tools/call`` into CD's MCP. Returns ``{"result": ...}``
    or ``{"error": ...}`` — never raises."""
    token = await _get_token()
    if not token:
        return {"error": "centerdeep-mcp: could not mint uchub client_credentials token"}
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments or {}},
    }
    try:
        async with httpx.AsyncClient(timeout=CDR_MCP_TIMEOUT) as client:
            resp = await client.post(CDR_MCP_URL, headers=headers, json=payload)
        if resp.status_code >= 400:
            return {"error": f"centerdeep-mcp HTTP {resp.status_code}: {resp.text[:200]}"}
        data = _parse_streamable_response(resp.text)
        if "error" in data:
            return {"error": str(data["error"])[:300]}
        content = data.get("result", {}).get("content", [])
        if not content:
            return {"result": ""}
        text = content[0].get("text", "")
        try:
            return {"result": json.loads(text)}
        except (json.JSONDecodeError, TypeError):
            return {"result": text}
    except httpx.TimeoutException:
        return {"error": f"centerdeep-mcp call timed out after {CDR_MCP_TIMEOUT}s"}
    except Exception as exc:  # noqa: BLE001 - defensive boundary
        logger.error(f"centerdeep-mcp call failed for {tool_name}: {exc}")
        return {"error": f"centerdeep-mcp call failed: {exc}"}


def _make_handler(tool_name: str):
    async def handler(**kwargs) -> Dict[str, Any]:
        # Drop None values so CD's MCP uses its own defaults.
        args = {k: v for k, v in kwargs.items() if v is not None}
        return await _call_mcp(tool_name, args)
    handler.__name__ = f"{tool_name}_handler"
    return handler


# ── Tool definitions (mirror CD's MCP tools/list) ──────────────

CDR_SEARCH_TOOL = ToolDefinition(
    name="cdr_search",
    description=(
        "Live web search via Center Deep Research (Serper-backed). Returns ranked "
        "organic results — title, link, snippet — for a query. Use this for "
        "fresh/factual lookups, finding sources, or current information the model "
        "may not know. Cite the returned links."
    ),
    parameters=[
        ToolParameter(name="query", type="string", description="The search query.", required=True),
        ToolParameter(
            name="count",
            type="number",
            description="Number of results to return (default ~10).",
            required=False,
        ),
    ],
    handler=_make_handler("search"),
)

CDR_QUICK_ANSWER_TOOL = ToolDefinition(
    name="cdr_quick_answer",
    description=(
        "Ask Center Deep Research for a fast, synthesized answer to a single "
        "question, grounded in live web results. Use when you need a concise "
        "answer with sources rather than a list of raw links. For a deeper "
        "multi-step investigation use cdr_deep_research instead."
    ),
    parameters=[
        ToolParameter(name="question", type="string", description="The question to answer.", required=True),
    ],
    handler=_make_handler("quick_answer"),
)

CDR_DEEP_RESEARCH_TOOL = ToolDefinition(
    name="cdr_deep_research",
    description=(
        "Run a multi-step deep research investigation via Center Deep Research: "
        "fans out web searches, reads sources, and synthesizes a cited report. "
        "Use for complex questions that need breadth and verification. 'mode' "
        "trades depth for latency (quick < balanced < deep)."
    ),
    parameters=[
        ToolParameter(name="question", type="string", description="The research question.", required=True),
        ToolParameter(
            name="mode",
            type="string",
            description="Depth/latency tradeoff.",
            required=False,
            enum=["quick", "balanced", "deep"],
        ),
    ],
    handler=_make_handler("deep_research"),
)


CENTERDEEP_MCP_TOOLS: Dict[str, ToolDefinition] = {
    "cdr_search": CDR_SEARCH_TOOL,
    "cdr_quick_answer": CDR_QUICK_ANSWER_TOOL,
    "cdr_deep_research": CDR_DEEP_RESEARCH_TOOL,
}
