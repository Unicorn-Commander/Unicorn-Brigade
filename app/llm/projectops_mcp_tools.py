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
    For now this is a long-lived service-account JWT scoped to a real
    Project-Ops admin user. Per-user identity propagation (forward the
    Project-Ops user's own JWT through Brigade) is the v2 plan.
"""

import json
import logging
import os
from typing import Any, Dict

import httpx

from app.llm.ops_center_client import ToolDefinition, ToolParameter

logger = logging.getLogger(__name__)

PROJECTOPS_MCP_URL = os.getenv(
    "PROJECTOPS_MCP_URL",
    "https://api.projectops.magicunicorn.dev/api/v1/mcp",
)
PROJECTOPS_MCP_TOKEN = os.getenv("PROJECTOPS_MCP_TOKEN", "")
PROJECTOPS_MCP_TIMEOUT = float(os.getenv("PROJECTOPS_MCP_TIMEOUT", "60.0"))


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


async def _call_mcp(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """JSON-RPC 2.0 call into Project-Ops MCP. Returns parsed result or error dict."""
    if not PROJECTOPS_MCP_TOKEN:
        return {"error": "projectops-mcp token not configured (PROJECTOPS_MCP_TOKEN env unset)"}
    headers = {
        "Authorization": f"Bearer {PROJECTOPS_MCP_TOKEN}",
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
    async def handler(**kwargs) -> Dict[str, Any]:
        args = {k: v for k, v in kwargs.items() if v is not None}
        return await _call_mcp(tool_name, args)
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
)


PROJECT_OPS_MCP_TOOLS: Dict[str, ToolDefinition] = {
    "list_my_projects": LIST_MY_PROJECTS_TOOL,
    "get_project": GET_PROJECT_TOOL,
    "list_my_tasks": LIST_MY_TASKS_TOOL,
    "search_projects": SEARCH_PROJECTS_TOOL,
    "get_recent_activity": GET_RECENT_ACTIVITY_TOOL,
    "add_task_comment": ADD_TASK_COMMENT_TOOL,
}
