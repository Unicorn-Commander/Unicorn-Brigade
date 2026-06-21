"""Stable canvas tools — let a Brigade agent (e.g. Majik) author into the
canvas of the Stable chat/voice/video room it is currently speaking in.

Three tools, all ``needs_room_context=True``: the tool invocation layer
injects ``caller_room_id`` / ``caller_room_name`` / ``caller_agent_id`` (the
running agent's id) into each handler, mirroring the ``caller_user_id``
injection used by the Project-Ops tools. The handlers map that context onto
Stable's internal artifact API:

    caller_room_id    -> room_id
    caller_room_name  -> livekit_room_name
    caller_agent_id   -> brigade_agent_id

The MODEL only ever sees the content-shaped params (title/kind/content/
language, artifact_id, edits). The room/agent identity is server-injected and
never exposed to the model, so an agent cannot author into a room it isn't in.

Transport: plain JSON over HTTP to Stable's in-cluster backend
(``http://stable-backend:8400`` by default — no public hop). Auth is a static
bearer in ``STABLE_INTERNAL_TOKEN`` (Stable's ``livekit_api_secret``); the
token is NEVER logged. The internal routes (already built on the Stable side):

    POST {url}/api/v1/internal/artifacts/create
        body {room_id, livekit_room_name, brigade_agent_id, title, kind,
              language?, content}
        -> {artifact_id, current_version_id, seq}
    POST {url}/api/v1/internal/artifacts/rewrite
        body {..., artifact_id, content}
    POST {url}/api/v1/internal/artifacts/edit
        body {..., artifact_id, edits:[{search, replace, replace_all?}]}
        -> on a non-matching block, HTTP 422 with a structured body. We hand
           that body back to the model (NOT treated as a hard failure) so it
           can fix its SEARCH text and retry.
"""

import logging
import os
from typing import Any, Dict, List, Optional

import httpx

from app.llm.ops_center_client import ToolDefinition, ToolParameter

logger = logging.getLogger(__name__)

# Stable backend, reachable in-cluster (no public hop). Override via env.
STABLE_INTERNAL_URL = os.getenv("STABLE_INTERNAL_URL", "http://stable-backend:8400")
# Static internal bearer = Stable's livekit_api_secret. Injected via env at
# deploy time; NEVER logged. Empty -> tools return a clear error rather than
# making an unauthenticated call.
STABLE_INTERNAL_TOKEN = os.getenv("STABLE_INTERNAL_TOKEN", "")
STABLE_INTERNAL_TIMEOUT = float(os.getenv("STABLE_INTERNAL_TIMEOUT", "30.0"))

_ARTIFACT_KINDS = ["markdown", "code", "html", "svg", "mermaid", "react", "sheet"]


async def _post_internal(path: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """POST ``body`` to a Stable internal artifact route and return a dict for
    the model.

    Returns:
      * the parsed success JSON on 2xx,
      * the structured 422 body verbatim (well-formed edit that didn't match —
        the model self-corrects from it; NOT a hard failure),
      * ``{"error": ...}`` for missing config, other HTTP errors, timeouts, or
        any exception. Never raises into the tool loop.

    The bearer token is never included in any log line.
    """
    if not STABLE_INTERNAL_TOKEN:
        return {"error": "STABLE_INTERNAL_TOKEN not configured"}
    url = f"{STABLE_INTERNAL_URL}{path}"
    headers = {
        "Authorization": f"Bearer {STABLE_INTERNAL_TOKEN}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=STABLE_INTERNAL_TIMEOUT) as client:
            resp = await client.post(url, headers=headers, json=body)
        # 422 = well-formed edit whose SEARCH block(s) didn't match. Return the
        # structured body so the model can fix its search text and retry. This
        # is an expected, recoverable outcome — do NOT surface it as an error.
        if resp.status_code == 422:
            try:
                return {"error_type": "no_match", "detail": resp.json()}
            except Exception:  # noqa: BLE001 - body wasn't JSON
                return {"error_type": "no_match", "detail": resp.text[:1000]}
        if resp.status_code >= 400:
            return {"error": f"stable-canvas HTTP {resp.status_code}: {resp.text[:300]}"}
        try:
            return resp.json()
        except Exception:  # noqa: BLE001 - unexpected non-JSON 2xx
            return {"result": resp.text[:1000]}
    except httpx.TimeoutException:
        return {"error": f"stable-canvas call timed out after {STABLE_INTERNAL_TIMEOUT}s"}
    except Exception as exc:  # noqa: BLE001 - defensive boundary; never raise into the loop
        logger.error(f"stable-canvas call failed for {path}: {exc}")
        return {"error": f"stable-canvas call failed: {exc}"}


def _room_context(
    caller_room_id: Optional[str],
    caller_room_name: Optional[str],
    caller_agent_id: Optional[str],
) -> Dict[str, Any]:
    """Build the room/agent identity fields Stable's internal API expects.

    These come from the server-side injection (needs_room_context), never from
    the model. If room context is missing the call would be rejected by Stable;
    we still send what we have so the failure is explicit downstream.
    """
    return {
        "room_id": caller_room_id,
        "livekit_room_name": caller_room_name,
        "brigade_agent_id": caller_agent_id,
    }


async def _canvas_create_handler(
    title: str,
    kind: str,
    content: str,
    language: Optional[str] = None,
    caller_room_id: Optional[str] = None,
    caller_room_name: Optional[str] = None,
    caller_agent_id: Optional[str] = None,
    **_ignored: Any,
) -> Dict[str, Any]:
    body = _room_context(caller_room_id, caller_room_name, caller_agent_id)
    body.update({"title": title, "kind": kind, "content": content})
    if language is not None:
        body["language"] = language
    return await _post_internal("/api/v1/internal/artifacts/create", body)


async def _canvas_rewrite_handler(
    artifact_id: str,
    content: str,
    caller_room_id: Optional[str] = None,
    caller_room_name: Optional[str] = None,
    caller_agent_id: Optional[str] = None,
    **_ignored: Any,
) -> Dict[str, Any]:
    body = _room_context(caller_room_id, caller_room_name, caller_agent_id)
    body.update({"artifact_id": artifact_id, "content": content})
    return await _post_internal("/api/v1/internal/artifacts/rewrite", body)


async def _canvas_edit_handler(
    artifact_id: str,
    edits: List[Dict[str, Any]],
    caller_room_id: Optional[str] = None,
    caller_room_name: Optional[str] = None,
    caller_agent_id: Optional[str] = None,
    **_ignored: Any,
) -> Dict[str, Any]:
    body = _room_context(caller_room_id, caller_room_name, caller_agent_id)
    body.update({"artifact_id": artifact_id, "edits": edits})
    return await _post_internal("/api/v1/internal/artifacts/edit", body)


CANVAS_CREATE_TOOL = ToolDefinition(
    name="canvas_create",
    description=(
        "Create a document, diagram, or code artifact in the user's canvas (the "
        "side panel of this Stable room). Use whenever the user asks you to write, "
        "draft, diagram, code, or build something they'll want to see and keep — "
        "e.g. a write-up, a plan, a code file, a flowchart. Returns the new "
        "artifact_id; pass it to canvas_rewrite or canvas_edit to revise. Pick the "
        "kind that matches the content: 'markdown' for prose/notes/docs, 'code' for "
        "source files (set 'language'), 'html' for a web page, 'svg' for vector "
        "graphics, 'mermaid' for flow/sequence/diagram syntax, 'react' for a React "
        "component, 'sheet' for tabular/CSV data."
    ),
    parameters=[
        ToolParameter(
            name="title",
            type="string",
            description="Short human-readable title for the artifact.",
            required=True,
        ),
        ToolParameter(
            name="kind",
            type="string",
            description="Artifact kind — how the canvas renders it.",
            required=True,
            enum=_ARTIFACT_KINDS,
        ),
        ToolParameter(
            name="content",
            type="string",
            description="The full body of the artifact (markdown, code, HTML, SVG, mermaid, JSX, or sheet data).",
            required=True,
        ),
        ToolParameter(
            name="language",
            type="string",
            description="For kind='code': the programming language (e.g. 'python', 'typescript'). Omit otherwise.",
            required=False,
        ),
    ],
    handler=_canvas_create_handler,
    needs_room_context=True,
)

CANVAS_REWRITE_TOOL = ToolDefinition(
    name="canvas_rewrite",
    description=(
        "Replace the ENTIRE content of an existing canvas artifact with a new "
        "version. Use when the changes are large or you're rewriting the whole "
        "thing; for small, surgical changes prefer canvas_edit. Needs the "
        "artifact_id returned by canvas_create (or one the user is pointing at)."
    ),
    parameters=[
        ToolParameter(
            name="artifact_id",
            type="string",
            description="The id of the artifact to rewrite (from canvas_create).",
            required=True,
        ),
        ToolParameter(
            name="content",
            type="string",
            description="The complete new body that replaces the artifact's current content.",
            required=True,
        ),
    ],
    handler=_canvas_rewrite_handler,
    needs_room_context=True,
)

CANVAS_EDIT_TOOL = ToolDefinition(
    name="canvas_edit",
    description=(
        "Make targeted search/replace edits to an existing canvas artifact "
        "without resending the whole document. Provide one or more edit blocks; "
        "each 'search' string must match the current content EXACTLY (set "
        "'replace_all' true to replace every occurrence, otherwise the first). "
        "Prefer this over canvas_rewrite for small changes. If a search block "
        "doesn't match, the tool returns {error_type:'no_match', detail:{...}} "
        "listing which blocks failed — read it, fix your search text to match the "
        "live content, and call canvas_edit again."
    ),
    parameters=[
        ToolParameter(
            name="artifact_id",
            type="string",
            description="The id of the artifact to edit (from canvas_create).",
            required=True,
        ),
        ToolParameter(
            name="edits",
            type="array",
            description=(
                "List of edit blocks. Each item: {\"search\": <exact text to find>, "
                "\"replace\": <replacement text>, \"replace_all\": <bool, optional, "
                "default false>}."
            ),
            required=True,
            items={
                "type": "object",
                "properties": {
                    "search": {
                        "type": "string",
                        "description": "Exact substring of the current content to replace.",
                    },
                    "replace": {
                        "type": "string",
                        "description": "Text to substitute in place of 'search'.",
                    },
                    "replace_all": {
                        "type": "boolean",
                        "description": "Replace every occurrence (default false = first only).",
                    },
                },
                "required": ["search", "replace"],
            },
        ),
    ],
    handler=_canvas_edit_handler,
    needs_room_context=True,
)


# Name -> ToolDefinition, registered into the global TOOL_REGISTRY.
STABLE_CANVAS_TOOLS: Dict[str, ToolDefinition] = {
    "canvas_create": CANVAS_CREATE_TOOL,
    "canvas_rewrite": CANVAS_REWRITE_TOOL,
    "canvas_edit": CANVAS_EDIT_TOOL,
}
