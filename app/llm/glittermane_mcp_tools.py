"""Glitter Mane tools — proxy into the Dr. Glitter Mane medical platform.

Dr. Glitter Mane is a personal-medical-AI agent that LIVES on its own platform:
the clinical reasoning, specialty routing, and the two-layer emergency/drug-
interaction safety net all run *inside* the platform (its consult endpoint), not
here. Brigade does not own or re-implement the agent — it registers the platform's
capabilities as tools so a Brigade agent scoped to the record's owner can use them.
The agent stays remote; Brigade just grants access.

Any agent that lists these tools (``glitter_*``) in its ``tools`` field gets them
as callable LLM functions.

Transport — Glitter's per-user auth + RLS live on its REST API (FastAPI,
``HTTPBearer``), NOT on its MCP-over-SSE server (which is for other MCP clients
like Claude Desktop and acts as a single fixed service user). So this module calls
the REST API directly with a per-user token, which is what scopes every read/write
to the right person.

  * Most tools are a single authenticated GET (reads) or POST (writes/ingest).
  * ``ask`` is the consult: POST /api/consultations to open one, then POST a
    message whose response is an SSE token stream we accumulate into the answer.

Auth — per the Glitter dev, shared-secret HS256 (option A):
  * If ``caller_user_id`` is present AND ``GLITTERMANE_JWT_SECRET`` is set, mint a
    short-lived ``sub=<caller>`` / ``aud=glitter-mane`` JWT. Glitter resolves the
    user from ``sub`` and scopes all DB access via per-user RLS (auto-provisioning
    a no-local-login account on first use).
  * Else if ``GLITTERMANE_STATIC_TOKEN`` is set, use it (service scope).
  * Else there is no usable auth and calls return an error (the REST API is
    Bearer-protected). ``needs_caller_context=True`` threads the caller in.

The whole module is inert unless ``GLITTERMANE_API_URL`` is set (see tool_resolver).
Production path (later): swap the HS256 mint for uchub RS256 token-exchange
(aud=glitter-mane); only ``_auth_header`` changes.
"""

import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, Optional

import httpx
from jose import jwt as jose_jwt

from app.llm.ops_center_client import ToolDefinition, ToolParameter

logger = logging.getLogger(__name__)

GLITTERMANE_API_URL = os.getenv("GLITTERMANE_API_URL", "")
# Optional static service bearer (fallback when no per-user secret/caller).
GLITTERMANE_STATIC_TOKEN = os.getenv("GLITTERMANE_STATIC_TOKEN", "")
# Shared HS256 secret for minting per-user tokens. When set + a caller is
# present, Brigade mints sub=<caller>/aud below so Glitter enforces per-user RLS.
GLITTERMANE_JWT_SECRET = os.getenv("GLITTERMANE_JWT_SECRET", "")
GLITTERMANE_JWT_AUD = os.getenv("GLITTERMANE_JWT_AUD", "glitter-mane")
GLITTERMANE_USER_JWT_TTL = int(os.getenv("GLITTERMANE_USER_JWT_TTL", "300"))  # 5 min
# Consults route to a real medical model — keep the ceiling generous.
GLITTERMANE_TIMEOUT = float(os.getenv("GLITTERMANE_TIMEOUT", "150.0"))

# tool name -> REST path. ``ask`` is handled specially (consult + SSE stream).
_GET_PATHS = {
    "get_health_summary": "/api/dashboard",
    "get_timeline": "/api/timeline",
    "get_visit_summary": "/api/export/summary",
    "list_conditions": "/api/conditions",
    "list_medications": "/api/medications",
    "list_allergies": "/api/allergies",
    "list_labs": "/api/labs",
    "list_vitals": "/api/vitals",
    "list_models": "/api/models",
}
_POST_PATHS = {
    "ingest_text": "/api/ingest/text",
    "add_condition": "/api/conditions",
    "add_medication": "/api/medications",
    "add_allergy": "/api/allergies",
    "add_vital": "/api/vitals",
    "add_care_plan_item": "/api/care-plan",
    "add_appointment": "/api/appointments",
}


def _mint_user_jwt(user_id: str) -> str:
    now = int(time.time())
    payload = {
        "sub": user_id,
        "aud": GLITTERMANE_JWT_AUD,
        "iat": now,
        "exp": now + GLITTERMANE_USER_JWT_TTL,
    }
    return jose_jwt.encode(payload, GLITTERMANE_JWT_SECRET, algorithm="HS256")


def _auth_header(caller_user_id: Optional[str]) -> Dict[str, str]:
    if caller_user_id and GLITTERMANE_JWT_SECRET:
        try:
            return {"Authorization": f"Bearer {_mint_user_jwt(caller_user_id)}"}
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"glittermane: per-user JWT mint failed for {caller_user_id}: {exc}")
    if GLITTERMANE_STATIC_TOKEN:
        return {"Authorization": f"Bearer {GLITTERMANE_STATIC_TOKEN}"}
    return {}


async def _consult(question: str, headers: Dict[str, str], base: str,
                   timeout: httpx.Timeout) -> Dict[str, Any]:
    """The ``ask`` flow: open a consultation, post the question, accumulate the
    SSE token stream into the answer."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        c = await client.post(f"{base}/api/consultations", headers=headers,
                              json={"title": (question or "Consult")[:80]})
        if c.status_code >= 400:
            return {"error": f"glittermane create-consult HTTP {c.status_code}: {c.text[:200]}"}
        cid = (c.json() or {}).get("id")
        if not cid:
            return {"error": "glittermane: consultation id missing"}
        tokens, specialties = [], []
        async with client.stream(
            "POST", f"{base}/api/consultations/{cid}/messages",
            headers=headers, json={"content": question},
        ) as r:
            if r.status_code >= 400:
                body = (await r.aread()).decode("utf-8", "ignore")
                return {"error": f"glittermane consult HTTP {r.status_code}: {body[:200]}"}
            async for raw in r.aiter_lines():
                line = raw.strip()
                if not line.startswith("data:"):
                    continue
                try:
                    ev = json.loads(line[5:].strip())
                except (json.JSONDecodeError, TypeError):
                    continue
                t = ev.get("type")
                if t == "token":
                    tokens.append(ev.get("content", ""))
                elif t == "triage":
                    specialties = ev.get("specialties", specialties)
                elif t in ("final", "done", "complete"):
                    if ev.get("answer"):
                        tokens = [ev["answer"]]
                    break
                elif t == "error":
                    return {"error": f"glittermane consult error: {str(ev)[:200]}"}
    answer = "".join(tokens).strip()
    if not answer:
        return {"error": "glittermane consult returned no answer"}
    return {"result": {"answer": answer, "specialties": specialties}}


async def _rest_call(tool_name: str, args: Dict[str, Any],
                     caller_user_id: Optional[str] = None) -> Dict[str, Any]:
    base = GLITTERMANE_API_URL.rstrip("/")
    if not base:
        return {"error": "glittermane not configured (set GLITTERMANE_API_URL)"}
    headers = _auth_header(caller_user_id)
    if "Authorization" not in headers:
        return {"error": "glittermane auth unavailable (set GLITTERMANE_JWT_SECRET + caller, or GLITTERMANE_STATIC_TOKEN)"}
    headers["Content-Type"] = "application/json"
    timeout = httpx.Timeout(GLITTERMANE_TIMEOUT, connect=10.0)
    try:
        if tool_name == "ask":
            return await asyncio.wait_for(
                _consult(args.get("question", ""), headers, base, timeout),
                timeout=GLITTERMANE_TIMEOUT + 15,
            )
        path = _GET_PATHS.get(tool_name) or _POST_PATHS.get(tool_name)
        if not path:
            return {"error": f"glittermane: unmapped tool {tool_name}"}
        async with httpx.AsyncClient(timeout=timeout) as client:
            if tool_name in _GET_PATHS:
                resp = await client.get(base + path, headers=headers)
            else:
                resp = await client.post(base + path, headers=headers, json=args or {})
        if resp.status_code >= 400:
            return {"error": f"glittermane HTTP {resp.status_code}: {resp.text[:200]}"}
        try:
            return {"result": resp.json()}
        except (json.JSONDecodeError, ValueError):
            return {"result": resp.text}
    except asyncio.TimeoutError:
        return {"error": f"glittermane call timed out after {GLITTERMANE_TIMEOUT}s"}
    except httpx.TimeoutException:
        return {"error": f"glittermane call timed out after {GLITTERMANE_TIMEOUT}s"}
    except Exception as exc:  # noqa: BLE001 - defensive boundary; never break a chat
        logger.error(f"glittermane call failed for {tool_name}: {exc}")
        return {"error": f"glittermane call failed: {exc}"}


def _make_handler(tool_name: str):
    async def handler(caller_user_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        # caller_user_id is injected by the tool layer (needs_caller_context=True);
        # never let it leak into the request body.
        args = {k: v for k, v in kwargs.items() if v is not None}
        return await _rest_call(tool_name, args, caller_user_id=caller_user_id)
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


# ── Tool definitions (one per Glitter capability, prefixed glitter_) ──────────

ASK_TOOL = ToolDefinition(
    name="glitter_ask",
    description=(
        "Ask Dr. Glitter Mane a health/medical question. Runs a full grounded clinical "
        "consult over the user's record — routes to the right specialty, screens for "
        "emergencies and drug interactions (built-in safety net), and returns a "
        "differential plus specific, guideline-cited guidance. USE THIS for ANY health, "
        "symptom, diagnosis, treatment, medication, or lab-interpretation question rather "
        "than answering medically yourself; pass the user's question and relay the result."
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
    # Record reads
    "glitter_get_health_summary": _read_tool(
        "get_health_summary",
        "Snapshot of the user's health record — active conditions, current meds, recent "
        "vitals/labs, and counts. A good first call to ground a consult."),
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
