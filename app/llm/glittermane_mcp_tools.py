"""Glitter Mane MCP tools — proxy into the Dr. Glitter Mane medical MCP server.

Dr. Glitter Mane is a personal-medical-AI agent that LIVES on its own platform:
the clinical reasoning, specialty routing, and the two-layer emergency/crisis +
drug-interaction safety net all run *inside* its ``ask`` tool, not here. Brigade
does not own or re-implement the agent — it registers the platform's tools so a
Brigade agent scoped to the record's owner can use them. The agent stays remote;
Brigade just grants access.

Any agent that lists these tools (``glitter_*``) in its ``tools`` field gets them
as callable LLM functions.

Transport — Glitter Mane runs the *legacy MCP SSE transport* (FastMCP ``sse``),
not the Streamable-HTTP transport Project-Ops/Center-Deep use, so each call:
  1. opens a GET event-stream to ``…/sse`` and reads the ``endpoint`` event to
     learn the per-session POST URL (``/messages/?session_id=…``),
  2. POSTs ``initialize`` + ``notifications/initialized`` (responses arrive back
     on the stream), then
  3. POSTs ``tools/call`` and reads the matching JSON-RPC response off the stream.
A fresh session per call keeps the handler stateless and robust.

Auth — mirrors the Project-Ops precedence, plus a trusted-network no-auth default:
  1. If ``caller_user_id`` is present AND ``GLITTERMANE_JWT_SECRET`` is set, mint a
     short-lived ``sub=<user>`` / ``aud=glitter-mane`` JWT so the medical platform
     can scope RLS to the real end user (per-user — the long-term target).
  2. Else if ``GLITTERMANE_MCP_TOKEN`` is set, send it as a static service bearer.
  3. Else send no Authorization header — works today over the trusted tailnet,
     where the MCP acts as a single Glitter service user.

The whole module is inert unless ``GLITTERMANE_MCP_URL`` is set (see tool_resolver).
"""

import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, Optional
from urllib.parse import urlsplit, urlunsplit

import httpx
from jose import jwt as jose_jwt

from app.llm.ops_center_client import ToolDefinition, ToolParameter

logger = logging.getLogger(__name__)

GLITTERMANE_MCP_URL = os.getenv("GLITTERMANE_MCP_URL", "")
# Static service bearer — fallback when no per-user secret/caller is available.
GLITTERMANE_MCP_TOKEN = os.getenv("GLITTERMANE_MCP_TOKEN", "")
# When set, Brigade mints a short-lived per-user JWT (sub=caller, aud below) for
# each call so the medical platform enforces per-user RLS. Until then we fall
# back to the service bearer or (on the trusted tailnet) no auth.
GLITTERMANE_JWT_SECRET = os.getenv("GLITTERMANE_JWT_SECRET", "")
GLITTERMANE_JWT_AUD = os.getenv("GLITTERMANE_JWT_AUD", "glitter-mane")
GLITTERMANE_USER_JWT_TTL = int(os.getenv("GLITTERMANE_USER_JWT_TTL", "300"))  # 5 min
# Consults route to a real medical model — keep the ceiling generous.
GLITTERMANE_MCP_TIMEOUT = float(os.getenv("GLITTERMANE_MCP_TIMEOUT", "150.0"))

_PROTOCOL_VERSION = "2024-11-05"
_CLIENT_INFO = {"name": "unicorn-brigade", "version": "1"}


def _origin(url: str) -> str:
    """Scheme+host of the SSE URL, for resolving the relative session endpoint."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, "", "", ""))


def _mint_user_jwt(user_id: str) -> str:
    now = int(time.time())
    payload = {
        "sub": user_id,
        "aud": GLITTERMANE_JWT_AUD,
        "iat": now,
        "exp": now + GLITTERMANE_USER_JWT_TTL,
    }
    return jose_jwt.encode(payload, GLITTERMANE_JWT_SECRET, algorithm="HS256")


def _auth_headers(caller_user_id: Optional[str]) -> Dict[str, str]:
    if caller_user_id and GLITTERMANE_JWT_SECRET:
        try:
            return {"Authorization": f"Bearer {_mint_user_jwt(caller_user_id)}"}
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"glittermane-mcp: per-user JWT mint failed for {caller_user_id}: {exc}")
    if GLITTERMANE_MCP_TOKEN:
        return {"Authorization": f"Bearer {GLITTERMANE_MCP_TOKEN}"}
    return {}


def _rpc(method: str, mid: int, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    body: Dict[str, Any] = {"jsonrpc": "2.0", "id": mid, "method": method}
    if params is not None:
        body["params"] = params
    return body


async def _read_endpoint(lines) -> str:
    """Consume SSE lines until the FastMCP ``endpoint`` event; return its path."""
    event = None
    async for raw in lines:
        line = raw.strip()
        if line.startswith("event:"):
            event = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            data = line.split(":", 1)[1].strip()
            if event == "endpoint":
                return data
            event = None
    raise ValueError("glittermane-mcp: SSE stream closed before endpoint event")


async def _read_response(lines, target_id: int) -> Dict[str, Any]:
    """Consume SSE lines until a JSON-RPC message whose id == target_id."""
    event = None
    async for raw in lines:
        line = raw.strip()
        if line.startswith("event:"):
            event = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            data = line.split(":", 1)[1].strip()
            event = None
            try:
                msg = json.loads(data)
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(msg, dict) and msg.get("id") == target_id:
                return msg
    raise ValueError(f"glittermane-mcp: SSE stream closed before response id={target_id}")


async def _call_mcp(
    tool_name: str,
    arguments: Dict[str, Any],
    caller_user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """One stateless legacy-SSE MCP session: open stream → initialize → call."""
    if not GLITTERMANE_MCP_URL:
        return {"error": "glittermane-mcp not configured (set GLITTERMANE_MCP_URL)"}
    headers = _auth_headers(caller_user_id)
    origin = _origin(GLITTERMANE_MCP_URL)
    timeout = httpx.Timeout(GLITTERMANE_MCP_TIMEOUT, connect=10.0)

    async def _do() -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "GET", GLITTERMANE_MCP_URL,
                headers={"Accept": "text/event-stream", **headers},
            ) as resp:
                if resp.status_code >= 400:
                    return {"error": f"glittermane-mcp SSE HTTP {resp.status_code}"}
                lines = resp.aiter_lines()
                post_url = origin + await _read_endpoint(lines)
                await client.post(post_url, headers=headers, json=_rpc(
                    "initialize", 1,
                    {"protocolVersion": _PROTOCOL_VERSION, "capabilities": {}, "clientInfo": _CLIENT_INFO},
                ))
                await _read_response(lines, 1)
                await client.post(post_url, headers=headers,
                                  json={"jsonrpc": "2.0", "method": "notifications/initialized"})
                await client.post(post_url, headers=headers, json=_rpc(
                    "tools/call", 2, {"name": tool_name, "arguments": arguments or {}},
                ))
                return await _read_response(lines, 2)

    try:
        msg = await asyncio.wait_for(_do(), timeout=GLITTERMANE_MCP_TIMEOUT + 15)
    except asyncio.TimeoutError:
        return {"error": f"glittermane-mcp call timed out after {GLITTERMANE_MCP_TIMEOUT}s"}
    except httpx.TimeoutException:
        return {"error": f"glittermane-mcp call timed out after {GLITTERMANE_MCP_TIMEOUT}s"}
    except Exception as exc:  # noqa: BLE001 - defensive boundary; never break a chat
        logger.error(f"glittermane-mcp call failed for {tool_name}: {exc}")
        return {"error": f"glittermane-mcp call failed: {exc}"}

    # _do() returns either an early {"error": ...} dict or a JSON-RPC message.
    if "error" in msg and "result" not in msg:
        return {"error": str(msg["error"])[:300]}
    result = msg.get("result", {}) or {}
    if result.get("isError"):
        content = result.get("content", [])
        text = content[0].get("text", "") if content else "tool error"
        return {"error": str(text)[:300]}
    content = result.get("content", [])
    if not content:
        sc = result.get("structuredContent")
        return {"result": sc if sc is not None else ""}
    text = content[0].get("text", "")
    try:
        return {"result": json.loads(text)}
    except (json.JSONDecodeError, TypeError):
        return {"result": text}


def _make_handler(tool_name: str):
    async def handler(caller_user_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        # caller_user_id is injected by the tool layer (needs_caller_context=True);
        # never let it leak into the MCP arguments dict.
        args = {k: v for k, v in kwargs.items() if v is not None}
        return await _call_mcp(tool_name, args, caller_user_id=caller_user_id)
    handler.__name__ = f"glitter_{tool_name}_handler"
    return handler


def _read_tool(bare: str, description: str) -> ToolDefinition:
    """A no-argument Glitter Mane read tool."""
    return ToolDefinition(
        name=f"glitter_{bare}",
        description=description,
        parameters=[],
        handler=_make_handler(bare),
        needs_caller_context=True,
    )


# ── Tool definitions (mirror Glitter Mane's MCP tools/list, prefixed glitter_) ─

ASK_TOOL = ToolDefinition(
    name="glitter_ask",
    description=(
        "Ask Dr. Glitter Mane a health/medical question. Runs a full grounded clinical "
        "consult over the user's record — routes to the right specialty, screens for "
        "emergencies and drug interactions (built-in safety net), and returns a "
        "differential plus specific, guideline-cited guidance. USE THIS for ANY health, "
        "symptom, diagnosis, treatment, medication, or lab-interpretation question rather "
        "than answering medically yourself; pass the user's question verbatim and relay "
        "the result."
    ),
    parameters=[
        ToolParameter(name="question", type="string",
                      description="The user's health question, in their own words.", required=True),
    ],
    handler=_make_handler("ask"),
    needs_caller_context=True,
)

INGEST_TEXT_TOOL = ToolDefinition(
    name="glitter_ingest_text",
    description=(
        "File unstructured medical text (visit notes, lab reports, pasted history). Glitter "
        "Mane extracts, deduplicates, and stores it as structured record entries. Use when "
        "the user dumps raw medical info they want captured into their record."
    ),
    parameters=[
        ToolParameter(name="text", type="string", description="The raw medical text to file.", required=True),
        ToolParameter(name="source_label", type="string",
                      description="Short provenance label for the entry.", required=False, default="agent ingest"),
    ],
    handler=_make_handler("ingest_text"),
    needs_caller_context=True,
)

ADD_CONDITION_TOOL = ToolDefinition(
    name="glitter_add_condition",
    description="Add a medical condition to the user's record. Only when the user asks to record one.",
    parameters=[
        ToolParameter(name="name", type="string", description="Condition name.", required=True),
        ToolParameter(name="status", type="string", description="Condition status.", required=False,
                      default="active", enum=["active", "managed", "resolved"]),
        ToolParameter(name="notes", type="string", description="Optional notes.", required=False),
    ],
    handler=_make_handler("add_condition"),
    needs_caller_context=True,
)

ADD_MEDICATION_TOOL = ToolDefinition(
    name="glitter_add_medication",
    description="Add a medication to the user's record. Only when the user asks to record one.",
    parameters=[
        ToolParameter(name="name", type="string", description="Medication name.", required=True),
        ToolParameter(name="dose", type="string", description="Dose, e.g. '10 mg'.", required=False),
        ToolParameter(name="frequency", type="string", description="Frequency, e.g. 'once daily'.", required=False),
        ToolParameter(name="active", type="boolean", description="Whether currently taken.", required=False, default=True),
    ],
    handler=_make_handler("add_medication"),
    needs_caller_context=True,
)

ADD_ALLERGY_TOOL = ToolDefinition(
    name="glitter_add_allergy",
    description="Add an allergy to the user's record. Only when the user asks to record one.",
    parameters=[
        ToolParameter(name="allergen", type="string", description="The allergen.", required=True),
        ToolParameter(name="reaction", type="string", description="Reaction, e.g. 'hives'.", required=False),
        ToolParameter(name="severity", type="string", description="Severity.", required=False,
                      enum=["mild", "moderate", "severe"]),
    ],
    handler=_make_handler("add_allergy"),
    needs_caller_context=True,
)

ADD_VITAL_TOOL = ToolDefinition(
    name="glitter_add_vital",
    description="Record a vital-sign reading in the user's record.",
    parameters=[
        ToolParameter(name="type", type="string", description="Vital type.", required=True,
                      enum=["blood_pressure", "heart_rate", "temperature", "weight", "glucose", "spo2", "other"]),
        ToolParameter(name="value", type="string", description="The reading, e.g. '120/80'.", required=True),
        ToolParameter(name="unit", type="string", description="Unit, e.g. 'mmHg'.", required=False),
    ],
    handler=_make_handler("add_vital"),
    needs_caller_context=True,
)

ADD_CARE_PLAN_ITEM_TOOL = ToolDefinition(
    name="glitter_add_care_plan_item",
    description="Add a care-plan action item (a recommendation or to-do) to the user's record.",
    parameters=[
        ToolParameter(name="title", type="string", description="Short action title.", required=True),
        ToolParameter(name="detail", type="string", description="Optional detail.", required=False),
        ToolParameter(name="due_on", type="string", description="Due date YYYY-MM-DD.", required=False),
    ],
    handler=_make_handler("add_care_plan_item"),
    needs_caller_context=True,
)

ADD_APPOINTMENT_TOOL = ToolDefinition(
    name="glitter_add_appointment",
    description="Add an upcoming appointment to the user's record.",
    parameters=[
        ToolParameter(name="title", type="string", description="Appointment title.", required=True),
        ToolParameter(name="provider", type="string", description="Provider/clinic.", required=False),
        ToolParameter(name="scheduled_for", type="string", description="Date YYYY-MM-DD.", required=False),
        ToolParameter(name="prep", type="string", description="Prep instructions.", required=False),
    ],
    handler=_make_handler("add_appointment"),
    needs_caller_context=True,
)


GLITTERMANE_MCP_TOOLS: Dict[str, ToolDefinition] = {
    # The consult (headline) + ingest
    "glitter_ask": ASK_TOOL,
    "glitter_ingest_text": INGEST_TEXT_TOOL,
    # Record reads (no args)
    "glitter_get_health_summary": _read_tool(
        "get_health_summary",
        "Snapshot of the user's health record — active conditions, current meds, recent "
        "vitals, and counts. A good first call to ground a consult."),
    "glitter_list_conditions": _read_tool("list_conditions", "List the user's medical conditions."),
    "glitter_list_medications": _read_tool("list_medications", "List the user's medications."),
    "glitter_list_allergies": _read_tool("list_allergies", "List the user's allergies."),
    "glitter_list_labs": _read_tool("list_labs", "List the user's lab results."),
    "glitter_list_vitals": _read_tool("list_vitals", "List the user's recorded vital signs."),
    "glitter_get_timeline": _read_tool(
        "get_timeline", "The user's chronological health timeline (conditions, labs, vitals, visits, meds)."),
    "glitter_get_visit_summary": _read_tool(
        "get_visit_summary", "A compiled, markdown doctor-visit summary of the whole record."),
    "glitter_list_models": _read_tool(
        "list_models", "List Glitter Mane's medical model registry (which specialty/imaging models are wired vs planned)."),
    # Record writes
    "glitter_add_condition": ADD_CONDITION_TOOL,
    "glitter_add_medication": ADD_MEDICATION_TOOL,
    "glitter_add_allergy": ADD_ALLERGY_TOOL,
    "glitter_add_vital": ADD_VITAL_TOOL,
    "glitter_add_care_plan_item": ADD_CARE_PLAN_ITEM_TOOL,
    "glitter_add_appointment": ADD_APPOINTMENT_TOOL,
}
