"""Stable knowledge tool — let a Brigade agent (e.g. Majik) search the
knowledge bases attached to the Stable chat/voice/video room it is currently
speaking in, and read/cite passages from the user's own documents.

One tool, ``needs_room_context=True``: the tool invocation layer injects
``caller_room_id`` / ``caller_room_name`` / ``caller_agent_id`` (the running
agent's id) into the handler, mirroring the canvas tools. The handler maps that
context onto Stable's internal knowledge-search API:

    caller_room_id    -> room_id
    caller_room_name  -> livekit_room_name
    caller_agent_id   -> brigade_agent_id

The MODEL only ever sees ``query`` and ``k``. The room/agent identity is
server-injected and never exposed to the model, so an agent can only search the
knowledge bases attached to the room it is actually in.

Transport: plain JSON over HTTP to Stable's in-cluster backend
(``http://stable-backend:8400`` by default — no public hop). Auth is the same
static bearer used by the canvas tools, ``STABLE_INTERNAL_TOKEN`` (Stable's
``livekit_api_secret``); the token is NEVER logged. The internal route (built on
the Stable side):

    POST {url}/api/v1/internal/knowledge/search
        body {room_id, livekit_room_name, brigade_agent_id, query, k}
        -> {results: [{text, filename, score, collection_id}]}

On any error (missing config, HTTP error, timeout, non-JSON, exception) or an
empty result set, the handler returns gracefully (``{"results": []}`` or
``{"error": ...}``) and NEVER raises into the tool loop.
"""

import logging
import os
from typing import Any, Dict, Optional

import httpx

from app.llm.ops_center_client import ToolDefinition, ToolParameter

logger = logging.getLogger(__name__)

# Stable backend, reachable in-cluster (no public hop). Override via env.
# Shared with the Stable canvas tools.
STABLE_INTERNAL_URL = os.getenv("STABLE_INTERNAL_URL", "http://stable-backend:8400")
# Static internal bearer = Stable's livekit_api_secret. Injected via env at
# deploy time; NEVER logged. Empty -> the tool returns a clear error rather than
# making an unauthenticated call. Shared with the Stable canvas tools.
STABLE_INTERNAL_TOKEN = os.getenv("STABLE_INTERNAL_TOKEN", "")
STABLE_INTERNAL_TIMEOUT = float(os.getenv("STABLE_INTERNAL_TIMEOUT", "30.0"))

# Default number of passages to return when the model omits ``k``.
_DEFAULT_K = 5


async def _knowledge_search_handler(
    query: str,
    k: int = _DEFAULT_K,
    caller_room_id: Optional[str] = None,
    caller_room_name: Optional[str] = None,
    caller_agent_id: Optional[str] = None,
    **_ignored: Any,
) -> Dict[str, Any]:
    """Search the knowledge bases attached to the caller's room.

    Returns the route's JSON (``{"results": [...]}``) on success so the model
    can read/cite the passages. On missing config, any HTTP error, timeout,
    non-JSON body, or exception, returns gracefully (``{"results": []}`` or
    ``{"error": ...}``) and NEVER raises into the tool loop. The bearer token is
    never included in any log line.
    """
    if not STABLE_INTERNAL_TOKEN:
        return {"error": "STABLE_INTERNAL_TOKEN not configured", "results": []}

    body: Dict[str, Any] = {
        "room_id": caller_room_id,
        "livekit_room_name": caller_room_name,
        "brigade_agent_id": caller_agent_id,
        "query": query,
        "k": k,
    }
    url = f"{STABLE_INTERNAL_URL}/api/v1/internal/knowledge/search"
    headers = {
        "Authorization": f"Bearer {STABLE_INTERNAL_TOKEN}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=STABLE_INTERNAL_TIMEOUT) as client:
            resp = await client.post(url, headers=headers, json=body)
        if resp.status_code >= 400:
            logger.warning(
                "stable-knowledge search HTTP %s for room %s",
                resp.status_code,
                caller_room_id,
            )
            return {
                "error": f"stable-knowledge HTTP {resp.status_code}: {resp.text[:300]}",
                "results": [],
            }
        try:
            data = resp.json()
        except Exception:  # noqa: BLE001 - unexpected non-JSON 2xx
            return {"results": []}
        # Normalise to always hand the model a results list it can iterate.
        if not isinstance(data, dict):
            return {"results": []}
        data.setdefault("results", [])
        return data
    except httpx.TimeoutException:
        logger.warning("stable-knowledge search timed out for room %s", caller_room_id)
        return {
            "error": f"stable-knowledge search timed out after {STABLE_INTERNAL_TIMEOUT}s",
            "results": [],
        }
    except Exception as exc:  # noqa: BLE001 - defensive boundary; never raise into the loop
        logger.error("stable-knowledge search failed: %s", exc)
        return {"error": f"stable-knowledge search failed: {exc}", "results": []}


SEARCH_KNOWLEDGE_TOOL = ToolDefinition(
    name="search_knowledge",
    description=(
        "Search the knowledge bases attached to THIS room/conversation for "
        "relevant information from the user's own documents (handbooks, project "
        "docs, etc.). Use when the user asks about internal, project-specific, "
        "or document-specific information that wouldn't be on the public web."
    ),
    parameters=[
        ToolParameter(
            name="query",
            type="string",
            description="The search query — what to look for in the attached documents.",
            required=True,
        ),
        ToolParameter(
            name="k",
            type="number",
            description="Number of top passages to return (default 5).",
            required=False,
            default=_DEFAULT_K,
        ),
    ],
    handler=_knowledge_search_handler,
    needs_room_context=True,
)


# Name -> ToolDefinition, registered into the global TOOL_REGISTRY.
STABLE_KNOWLEDGE_TOOLS: Dict[str, ToolDefinition] = {
    "search_knowledge": SEARCH_KNOWLEDGE_TOOL,
}
