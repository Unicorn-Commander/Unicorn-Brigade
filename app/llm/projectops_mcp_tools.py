"""Project-Ops MCP tools — proxies into the Project-Ops MCP server.

Exposes the six project-ops tools (list_my_projects, get_project,
list_my_tasks, search_projects, get_recent_activity, add_task_comment)
as Brigade ToolDefinitions so any agent that lists them in its
``tools`` field gets them as callable LLM functions.

The handler proxies via JSON-RPC 2.0 over Project-Ops's Streamable HTTP
MCP transport. Two transport quirks vs. crisis-mcp:

  * Project-Ops's MCP endpoint requires ``Accept: application/json,
    text/event-stream`` and replies with a single SSE-framed message
    (``event: message\\ndata: <json>\\n\\n``). We strip the framing
    before parsing.
  * Authentication is a Bearer JWT minted with Project-Ops's JWT_SECRET.
    When PROJECTOPS_JWT_SECRET is set, Brigade mints a short-lived JWT
    scoped to ``caller_user_id`` for each call so the MCP server enforces
    per-user RBAC. If no caller is available (scheduled health checks)
    we fall back to the long-lived service-account token in
    PROJECTOPS_MCP_TOKEN.
"""

import json
import logging
import os
import time
from typing import Any, Dict, Optional

import httpx
from jose import jwt as jose_jwt

from app.llm.ops_center_client import ToolDefinition, ToolParameter

logger = logging.getLogger(__name__)

PROJECTOPS_MCP_URL = os.getenv(
    "PROJECTOPS_MCP_URL",
    "https://api.projectops.magicunicorn.dev/api/v1/mcp",
)
# Long-lived service-account JWT used as a fallback when no caller identity
# is available (e.g. scheduled health checks). When PROJECTOPS_JWT_SECRET is
# set AND the tool layer injects ``caller_user_id``, the per-user JWT minted
# below takes precedence so MCP tools enforce per-user RBAC.
PROJECTOPS_MCP_TOKEN = os.getenv("PROJECTOPS_MCP_TOKEN", "")
# Project-Ops's JWT_SECRET. When configured, Brigade mints a short-lived JWT
# scoped to the calling user before each MCP call. Required for v2 per-user
# identity propagation; without it we fall back to the service-account token.
PROJECTOPS_JWT_SECRET = os.getenv("PROJECTOPS_JWT_SECRET", "")
PROJECTOPS_USER_JWT_TTL = int(os.getenv("PROJECTOPS_USER_JWT_TTL", "300"))  # 5 min
PROJECTOPS_MCP_TIMEOUT = float(os.getenv("PROJECTOPS_MCP_TIMEOUT", "60.0"))


def _mint_user_jwt(user_id: str) -> str:
    """Mint a short-lived Project-Ops JWT for ``user_id``. The Project-Ops
    JwtStrategy validates by ``sub`` only (it then loads the user from the DB
    to populate role/email), so we don't need to know the user's email or
    role to mint a working token. Token expires after PROJECTOPS_USER_JWT_TTL
    seconds — short by design, since we mint a fresh one per tool call.
    """
    now = int(time.time())
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + PROJECTOPS_USER_JWT_TTL,
    }
    return jose_jwt.encode(payload, PROJECTOPS_JWT_SECRET, algorithm="HS256")


def _parse_streamable_response(body: str) -> Dict[str, Any]:
    """Project-Ops's MCP transport returns a single SSE event per request:

        event: message
        data: {"jsonrpc":"2.0","id":1,"result":{...}}

    Find the first ``data:`` line and parse it as JSON. Falls back to
    parsing the whole body if the SSE framing isn't present (defensive —
    some MCP servers return plain JSON when the client doesn't request
    event-stream).
    """
    body = (body or "").strip()
    if not body:
        return {}
    if body.startswith("{"):
        return json.loads(body)
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if line.startswith("data:"):
            return json.loads(line[len("data:"):].strip())
    raise ValueError(f"projectops-mcp: no data line in response: {body[:200]}")


async def _call_mcp(
    tool_name: str,
    arguments: Dict[str, Any],
    caller_user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """JSON-RPC 2.0 call into Project-Ops MCP. Returns parsed result or error dict.

    Auth precedence:
      1. If ``caller_user_id`` is provided AND PROJECTOPS_JWT_SECRET is set,
         mint a fresh per-user JWT — the MCP server then runs the tool under
         that user's RBAC.
      2. Otherwise fall back to the long-lived service-account token in
         PROJECTOPS_MCP_TOKEN (admin scope; intended for scheduled health
         checks where there is no human caller).
      3. If neither is configured, error out without making the call.
    """
    if caller_user_id and PROJECTOPS_JWT_SECRET:
        try:
            token = _mint_user_jwt(caller_user_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"projectops-mcp: per-user JWT mint failed for {caller_user_id}: {exc}")
            token = PROJECTOPS_MCP_TOKEN
    else:
        token = PROJECTOPS_MCP_TOKEN
    if not token:
        return {"error": "projectops-mcp token not configured (set PROJECTOPS_JWT_SECRET + caller_user_id, or PROJECTOPS_MCP_TOKEN)"}
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
        async with httpx.AsyncClient(timeout=PROJECTOPS_MCP_TIMEOUT) as client:
            resp = await client.post(PROJECTOPS_MCP_URL, headers=headers, json=payload)
        if resp.status_code >= 400:
            return {"error": f"projectops-mcp HTTP {resp.status_code}: {resp.text[:200]}"}
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
        return {"error": f"projectops-mcp call timed out after {PROJECTOPS_MCP_TIMEOUT}s"}
    except Exception as exc:  # noqa: BLE001 - defensive boundary
        logger.error(f"projectops-mcp call failed for {tool_name}: {exc}")
        return {"error": f"projectops-mcp call failed: {exc}"}


def _make_handler(tool_name: str):
    async def handler(caller_user_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        # caller_user_id is injected by the tool invocation layer when
        # ToolDefinition.needs_caller_context is True; never let it leak
        # into the MCP arguments dict.
        args = {k: v for k, v in kwargs.items() if v is not None}
        return await _call_mcp(tool_name, args, caller_user_id=caller_user_id)
    handler.__name__ = f"{tool_name}_handler"
    return handler


# ── Tool definitions (mirror Project-Ops MCP server tools/list) ─

LIST_MY_PROJECTS_TOOL = ToolDefinition(
    name="list_my_projects",
    description=(
        "Return the projects the calling user can see in Project Ops, newest first. "
        "Use this for 'what projects do I have' / 'show me my open work' questions. "
        "Optional 'status' filters by ProjectStatus."
    ),
    parameters=[
        ToolParameter(
            name="status",
            type="string",
            description="Filter by ProjectStatus.",
            required=False,
            enum=["NEW", "IN_PROGRESS", "UNDER_REVIEW", "COMPLETED", "ARCHIVED", "ON_HOLD"],
        ),
        ToolParameter(
            name="limit",
            type="number",
            description="Max projects to return (default 25, max 100).",
            required=False,
            default=25,
        ),
    ],
    handler=_make_handler("list_my_projects"),
    needs_caller_context=True,
)

GET_PROJECT_TOOL = ToolDefinition(
    name="get_project",
    description=(
        "Return full detail for one Project Ops project the user can see, including "
        "recent tasks and comments. Pass either id (UUID) or projectNumber (e.g. 'P-00042')."
    ),
    parameters=[
        ToolParameter(name="id", type="string", description="Project UUID.", required=False),
        ToolParameter(
            name="projectNumber",
            type="string",
            description="Human-readable project number (e.g. P-00042).",
            required=False,
        ),
    ],
    handler=_make_handler("get_project"),
    needs_caller_context=True,
)

LIST_MY_TASKS_TOOL = ToolDefinition(
    name="list_my_tasks",
    description=(
        "Return tasks assigned to the calling user, sorted by due date. "
        "Use for 'what's on my plate' questions. Optional 'status' filters by TaskStatus."
    ),
    parameters=[
        ToolParameter(
            name="status",
            type="string",
            description="Filter by TaskStatus.",
            required=False,
        ),
        ToolParameter(
            name="limit",
            type="number",
            description="Max tasks (default 25, max 100).",
            required=False,
            default=25,
        ),
    ],
    handler=_make_handler("list_my_tasks"),
    needs_caller_context=True,
)

SEARCH_PROJECTS_TOOL = ToolDefinition(
    name="search_projects",
    description=(
        "Free-text search across projects the user can see — matches title, description, "
        "project number, client name, and organization name. Use when the user names a "
        "project loosely and you need to find the actual record."
    ),
    parameters=[
        ToolParameter(name="query", type="string", description="Search text.", required=True),
        ToolParameter(
            name="limit",
            type="number",
            description="Max results (default 10, max 50).",
            required=False,
            default=10,
        ),
    ],
    handler=_make_handler("search_projects"),
    needs_caller_context=True,
)

GET_RECENT_ACTIVITY_TOOL = ToolDefinition(
    name="get_recent_activity",
    description=(
        "Return recent comments and task updates across the projects the user can see. "
        "Use this for 'what changed today' / 'what's been going on' / catch-me-up questions."
    ),
    parameters=[
        ToolParameter(
            name="limit",
            type="number",
            description="How many of each (comments + task updates) to return (default 20, max 50).",
            required=False,
            default=20,
        ),
    ],
    handler=_make_handler("get_recent_activity"),
    needs_caller_context=True,
)

ADD_TASK_COMMENT_TOOL = ToolDefinition(
    name="add_task_comment",
    description=(
        "Post a comment to a Project Ops task on the user's behalf. Use sparingly — only when "
        "the user has explicitly asked you to log or note something on a specific task, "
        "never for ambient narration."
    ),
    parameters=[
        ToolParameter(name="taskId", type="string", description="Task UUID.", required=True),
        ToolParameter(
            name="content",
            type="string",
            description="Comment body (max 5000 chars).",
            required=True,
        ),
    ],
    handler=_make_handler("add_task_comment"),
    needs_caller_context=True,
)


PROJECT_OPS_MCP_TOOLS: Dict[str, ToolDefinition] = {
    "list_my_projects": LIST_MY_PROJECTS_TOOL,
    "get_project": GET_PROJECT_TOOL,
    "list_my_tasks": LIST_MY_TASKS_TOOL,
    "search_projects": SEARCH_PROJECTS_TOOL,
    "get_recent_activity": GET_RECENT_ACTIVITY_TOOL,
    "add_task_comment": ADD_TASK_COMMENT_TOOL,
}
