"""uc-browser MCP tools — proxies into the uc-browser gate so any Brigade agent
that lists them in its ``tools`` field can drive a real Chrome (Playwright MCP
0.0.81 behind ``https://browser.magicunicorn.dev/mcp``) as callable LLM
functions: navigate, read the page, click, type, fill forms, screenshot, PDF,
console log.

Shape mirrors ``centerdeep_mcp_tools``: env-configured endpoint, a uchub
client_credentials bearer minted per call with an in-process cache, one
``_call_mcp`` doing JSON-RPC 2.0 ``tools/call`` over Streamable HTTP, and
``ToolDefinition`` wrappers collected in ``UC_BROWSER_MCP_TOOLS``. Registration
in ``tool_resolver`` is gated on ``UC_BROWSER_MCP_URL`` being set.

Transport facts that shape this module (all measured against Playwright MCP
0.0.81's ``tools/list`` and real ``tools/call`` replies, 2026-09-17):

  * The gate speaks Streamable HTTP MCP. It pins ONE upstream browser session
    per caller and unwraps SSE to plain JSON when the caller does not ask for
    ``text/event-stream``. We send the spec's ``Accept: application/json,
    text/event-stream`` (same as the other bridges) and parse either framing.
  * If the gate hands back an ``Mcp-Session-Id`` header we keep it per process
    and resend it on every later request. If a call is refused because the
    session is missing/expired (HTTP 400/404 with a "session"/"initialized"
    message) we run the ``initialize`` + ``notifications/initialized``
    handshake once and retry the call once.
  * Auth is the same Keycloak client_credentials bearer Center-Deep uses
    (``KEYCLOAK_CLIENT_ID`` / ``KEYCLOAK_CLIENT_SECRET``): the gate accepts
    ``azp=brigade`` (or a Brigade-exchanged JWT with ``aud=browser-ops``). The
    token TTL is ~5 min so we mint per-call with a small cache and NEVER
    persist it. The public gate is behind Cloudflare, which 403s default
    Python User-Agents — every request carries a named browser-style UA.
  * Playwright MCP returns ONE text content item made of ``### Section``
    blocks (``Error``, ``Result``, ``Ran Playwright code``, ``Page``,
    ``Snapshot``, ``Events``) plus, for screenshots, an ``image`` content item
    (base64). Tool failures are NOT JSON-RPC errors: they come back as a
    normal result with ``isError: true`` and a ``### Error`` section. Both are
    mapped to ``{"error": ...}`` here. Only an explicit ``browser_snapshot``
    returns the accessibility tree inline; after navigate/click/type the
    snapshot is written to a file on the browser host and only linked, so
    agents must call ``ucb_snapshot`` / ``ucb_page_text`` to read the page.

Schema mismatches between the exposed tools and Playwright MCP 0.0.81 (kept
deliberately, documented here and in docs/uc-browser-bridge.md):

  * 0.0.81 names the element reference ``target`` (older releases: ``ref``).
    The agent-facing tools keep ``ref`` (as specified) and this module remaps
    ``ref`` -> ``target`` before forwarding, including inside ``fill_form``
    fields, whose schema is ``additionalProperties: false`` — an un-remapped
    ``ref`` is a hard upstream error ("expected string, received undefined at
    target").
  * ``element`` (human-readable description) is optional upstream; it is kept
    optional here too but strongly encouraged in the descriptions.
  * ``browser_console_messages.level`` and ``browser_take_screenshot.scale``
    are marked ``required`` upstream even though they carry defaults; we
    always send them (``level="info"``, ``scale="css"``).

These tools are system-callable: the browser has no per-user identity, so
like the Center-Deep tools they do NOT set ``needs_caller_context``. All
agents share the one pinned browser session — treat it as a single tab
driven by one agent at a time.

Enable for an agent (agent record)::

    {"tools": ["ucb_navigate", "ucb_page_text", "ucb_snapshot", "ucb_screenshot"]}

Enable in the deployment (bigboy, docker-compose.brigade.yml, ``environment:``
block of ``unicorn-brigade``)::

    UC_BROWSER_MCP_URL: https://browser.magicunicorn.dev/mcp

Optional knobs: ``UC_BROWSER_MCP_TIMEOUT`` (s, default 60 — keep it under the
tool loop's ``TOOL_EXECUTION_TIMEOUT_SECONDS``), ``UC_BROWSER_TEXT_MAX``
(chars returned by page_text/snapshot, default 20000),
``UC_BROWSER_IMAGE_INLINE_MAX`` (base64 chars of a screenshot to inline in the
tool result, default 0 = path only), ``UC_BROWSER_TOKEN_URL`` /
``UC_BROWSER_CLIENT_ID`` / ``UC_BROWSER_CLIENT_SECRET`` (default to the
Center-Deep / Keycloak values).
"""

import itertools
import json
import logging
import os
import re
import time
from typing import Any, Optional

import httpx

from app.llm.ops_center_client import ToolDefinition, ToolParameter

logger = logging.getLogger(__name__)

# The gate URL. No default on purpose: tool_resolver registers these tools
# only when it is set, so an unconfigured deployment exposes nothing.
UC_BROWSER_MCP_URL = os.getenv("UC_BROWSER_MCP_URL", "")
# uchub token endpoint (behind Cloudflare → must send a browser User-Agent).
UC_BROWSER_TOKEN_URL = os.getenv(
    "UC_BROWSER_TOKEN_URL",
    os.getenv(
        "CDR_TOKEN_URL",
        "https://auth.magicunicorn.dev/realms/uchub/protocol/openid-connect/token",
    ),
)
# Reuse Brigade's own uchub client (same one Center-Deep uses); the gate
# accepts azp=brigade. Safe defaults → no new secret required.
UC_BROWSER_CLIENT_ID = os.getenv("UC_BROWSER_CLIENT_ID", os.getenv("KEYCLOAK_CLIENT_ID", "brigade"))
UC_BROWSER_CLIENT_SECRET = os.getenv("UC_BROWSER_CLIENT_SECRET", os.getenv("KEYCLOAK_CLIENT_SECRET", ""))
# Navigation of a slow page can take a while; 60 s matches the tool loop's
# default per-tool budget (TOOL_EXECUTION_TIMEOUT_SECONDS).
UC_BROWSER_MCP_TIMEOUT = float(os.getenv("UC_BROWSER_MCP_TIMEOUT", "60.0"))
# Cap on text handed back to the model (page text, snapshot, console log).
UC_BROWSER_TEXT_MAX = int(os.getenv("UC_BROWSER_TEXT_MAX", "20000"))
# Screenshots: the image is saved on the browser host and linked; base64 is
# inlined only up to this many chars (0 = never — the tool loop feeds results
# to a text model, so base64 mostly burns context).
UC_BROWSER_IMAGE_INLINE_MAX = int(os.getenv("UC_BROWSER_IMAGE_INLINE_MAX", "0"))
# Cloudflare fronts both the token endpoint and the gate and 1010s/403s
# non-browser UAs (python-httpx/...). A named, browser-style UA passes.
_USER_AGENT = "Mozilla/5.0 (compatible; UnicornBrigade/ucbrowser-bridge)"
_MCP_PROTOCOL_VERSION = "2025-06-18"

# In-process token cache. client_credentials TTL is ~300s; refresh a little
# early. We never write the token anywhere — memory only, per process.
_TOKEN_CACHE: dict[str, Any] = {"token": None, "exp": 0.0}
_TOKEN_REFRESH_SKEW = 30.0  # mint a fresh token this many seconds before exp
_TOKEN_MAX_TTL = float(os.getenv("UC_BROWSER_TOKEN_MAX_TTL", "240.0"))  # cap cache at ~4 min

# Per-process Streamable HTTP session (Mcp-Session-Id) handed out by the gate.
_SESSION: dict[str, Optional[str]] = {"id": None}
# JSON-RPC ids — a counter rather than a constant, since the session is stateful.
_RPC_IDS = itertools.count(1)

_SECTION_RE = re.compile(r"^### (.+?)\s*$", re.MULTILINE)
_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def _http_client(timeout: float) -> httpx.AsyncClient:
    """One place to build the HTTP client (tests swap in a MockTransport)."""
    return httpx.AsyncClient(timeout=timeout)


async def _get_token() -> Optional[str]:
    """Mint (or return cached) a uchub client_credentials bearer for the gate.

    Caches the token in-process for up to ~4 minutes (or the token's own
    ``expires_in`` minus a small skew, whichever is shorter). Returns ``None``
    on failure — callers turn that into an error dict. The client secret is
    never logged.
    """
    now = time.time()
    cached = _TOKEN_CACHE.get("token")
    if cached and now < float(_TOKEN_CACHE.get("exp", 0.0)):
        return cached
    if not UC_BROWSER_CLIENT_SECRET:
        logger.error("ucbrowser-mcp: no client secret configured (UC_BROWSER_CLIENT_SECRET / KEYCLOAK_CLIENT_SECRET)")
        return None
    data = {
        "grant_type": "client_credentials",
        "client_id": UC_BROWSER_CLIENT_ID,
        "client_secret": UC_BROWSER_CLIENT_SECRET,
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": _USER_AGENT,
    }
    try:
        async with _http_client(30.0) as client:
            resp = await client.post(UC_BROWSER_TOKEN_URL, data=data, headers=headers)
        if resp.status_code >= 400:
            # Redact: never echo the response body wholesale and never log the secret.
            logger.error(f"ucbrowser-mcp: token mint HTTP {resp.status_code} (client_id={UC_BROWSER_CLIENT_ID})")
            return None
        body = resp.json()
        token = body.get("access_token")
        if not token:
            logger.error("ucbrowser-mcp: token response missing access_token")
            return None
        expires_in = float(body.get("expires_in", 300) or 300)
        ttl = min(_TOKEN_MAX_TTL, max(0.0, expires_in - _TOKEN_REFRESH_SKEW))
        _TOKEN_CACHE["token"] = token
        _TOKEN_CACHE["exp"] = now + ttl
        return token
    except Exception as exc:  # noqa: BLE001 - defensive boundary; do not surface secret
        logger.error(f"ucbrowser-mcp: token mint failed: {exc}")
        return None


def _parse_streamable_response(body: str) -> dict[str, Any]:
    """Parse a Streamable HTTP reply into the JSON-RPC response.

    The gate unwraps SSE to plain JSON when asked; a raw upstream reply is a
    single SSE message ``event: message\\ndata: <json>\\n\\n``. Both are
    handled, and — as with Center-Deep — when several ``data:`` frames arrive
    (progress notifications first) the LAST frame carrying a top-level
    ``result``/``error`` is the response.
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
        if isinstance(frame, dict) and ("result" in frame or "error" in frame):
            response = frame
    if response is not None:
        return response
    if last_frame is not None:
        return last_frame
    raise ValueError(f"ucbrowser-mcp: no data line in response: {body[:200]}")


def _parse_sections(text: str) -> dict[str, str]:
    """Split Playwright MCP's ``### Title`` blocks into ``{title: body}``.

    Mirrors the server's own ``parseSections``. Text before the first header
    (rare) is kept under ``""``. Bodies keep their code fences; use
    ``_strip_fence`` for the YAML/JS blocks.
    """
    sections: dict[str, str] = {}
    if not text:
        return sections
    matches = list(_SECTION_RE.finditer(text))
    if not matches:
        return {"": text.strip()}
    lead = text[: matches[0].start()].strip()
    if lead:
        sections[""] = lead
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[m.group(1)] = text[m.end():end].strip("\n")
    return sections


def _strip_fence(body: str) -> str:
    """Drop a surrounding ```lang ... ``` fence, if present."""
    lines = (body or "").strip("\n").split("\n")
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
    return "\n".join(lines)


def _page_info(sections: dict[str, str]) -> Optional[dict[str, Any]]:
    """``### Page`` → ``{"url", "title", ...}`` (None when the section is absent)."""
    body = sections.get("Page")
    if not body:
        return None
    info: dict[str, Any] = {}
    extra: list[str] = []
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("- Page URL:"):
            info["url"] = line[len("- Page URL:"):].strip()
        elif line.startswith("- Page Title:"):
            info["title"] = line[len("- Page Title:"):].strip()
        elif line.startswith("- "):
            extra.append(line[2:].strip())
    if extra:
        info["status"] = extra
    return info


def _first_link(body: str) -> Optional[str]:
    """``- [Screenshot of viewport](path/to/file.png)`` → ``path/to/file.png``."""
    m = _LINK_RE.search(body or "")
    return m.group(1) if m else None


def _truncate(text: str, cap: int = 0) -> tuple[str, bool]:
    cap = cap or UC_BROWSER_TEXT_MAX
    text = text or ""
    if len(text) <= cap:
        return text, False
    return text[:cap] + f"\n…[truncated: {len(text) - cap} more chars]", True


def _needs_handshake(status: int, data: dict[str, Any]) -> bool:
    """True when the gate/upstream rejected the request for lack of a live
    Streamable HTTP session (MCP SDK: 400 "Server not initialized", 404
    "Session not found", -32000/-32001)."""
    if status not in (400, 404):
        return False
    err = data.get("error") if isinstance(data, dict) else None
    message = ""
    if isinstance(err, dict):
        message = str(err.get("message", ""))
    elif err is not None:
        message = str(err)
    low = message.lower()
    return ("session" in low) or ("initialized" in low) or not message


async def _initialize(client: httpx.AsyncClient, headers: dict[str, str]) -> None:
    """Run the MCP ``initialize`` handshake and capture the session id.

    Only used when a call was refused for a missing session — the gate
    normally pins the upstream session itself. Never raises to the caller's
    tool result: failures surface on the retried ``tools/call``.
    """
    payload = {
        "jsonrpc": "2.0",
        "id": next(_RPC_IDS),
        "method": "initialize",
        "params": {
            "protocolVersion": _MCP_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "unicorn-brigade", "version": "1"},
        },
    }
    hdrs = {k: v for k, v in headers.items() if k.lower() != "mcp-session-id"}
    resp = await client.post(UC_BROWSER_MCP_URL, headers=hdrs, json=payload)
    sid = resp.headers.get("mcp-session-id")
    if sid:
        _SESSION["id"] = sid
        hdrs["Mcp-Session-Id"] = sid
    if resp.status_code < 400:
        await client.post(
            UC_BROWSER_MCP_URL,
            headers=hdrs,
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        )
    else:
        logger.warning(f"ucbrowser-mcp: initialize HTTP {resp.status_code}: {resp.text[:200]}")


async def _call_mcp(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """JSON-RPC 2.0 ``tools/call`` into the gate. Returns
    ``{"result": {"text": <markdown>, "sections": {...}, "images": [...]}}``
    or ``{"error": <str>}`` — never raises. Tool handlers shape the model-facing
    result from ``sections``."""
    if not UC_BROWSER_MCP_URL:
        return {"error": "ucbrowser-mcp: UC_BROWSER_MCP_URL not configured"}
    token = await _get_token()
    if not token:
        return {"error": "ucbrowser-mcp: could not mint uchub client_credentials token"}
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "User-Agent": _USER_AGENT,
    }
    if _SESSION["id"]:
        headers["Mcp-Session-Id"] = _SESSION["id"]

    def _payload() -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": next(_RPC_IDS),
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments or {}},
        }

    try:
        async with _http_client(UC_BROWSER_MCP_TIMEOUT) as client:
            resp = await client.post(UC_BROWSER_MCP_URL, headers=headers, json=_payload())
            data = _safe_parse(resp.text)
            if _needs_handshake(resp.status_code, data):
                # Lost/absent session: handshake once, retry once.
                _SESSION["id"] = None
                headers.pop("Mcp-Session-Id", None)
                await _initialize(client, headers)
                if _SESSION["id"]:
                    headers["Mcp-Session-Id"] = _SESSION["id"]
                resp = await client.post(UC_BROWSER_MCP_URL, headers=headers, json=_payload())
                data = _safe_parse(resp.text)
        sid = resp.headers.get("mcp-session-id")
        if sid:
            _SESSION["id"] = sid
        if resp.status_code >= 400:
            return {"error": f"ucbrowser-mcp HTTP {resp.status_code}: {resp.text[:200]}"}
        if isinstance(data, Exception):
            raise data
        if "error" in data:
            err = data["error"]
            if isinstance(err, dict):
                err = f"{err.get('code', '')} {err.get('message', '')}".strip()
            return {"error": str(err)[:300]}
        result = data.get("result") or {}
        content = result.get("content") or []
        text = "\n".join(c.get("text", "") for c in content if c.get("type") == "text")
        images = [
            {"mime_type": c.get("mimeType", ""), "data": c.get("data", "")}
            for c in content
            if c.get("type") == "image"
        ]
        sections = _parse_sections(text)
        if result.get("isError") or "Error" in sections:
            message = sections.get("Error") or text or "unknown error"
            return {"error": f"ucbrowser-mcp {tool_name}: {message.strip()[:600]}"}
        return {"result": {"text": text, "sections": sections, "images": images}}
    except httpx.TimeoutException:
        return {"error": f"ucbrowser-mcp call timed out after {UC_BROWSER_MCP_TIMEOUT}s"}
    except Exception as exc:  # noqa: BLE001 - defensive boundary
        logger.error(f"ucbrowser-mcp call failed for {tool_name}: {exc}")
        return {"error": f"ucbrowser-mcp call failed: {exc}"}


def _safe_parse(body: str) -> Any:
    """Parse or return the exception (so the caller can decide after checking
    the HTTP status — a 4xx body is often not JSON-RPC at all)."""
    try:
        return _parse_streamable_response(body)
    except Exception as exc:  # noqa: BLE001
        return exc


# ── Handlers (shape the model-facing result) ─────────────────────────


def _remap_ref(args: dict[str, Any]) -> dict[str, Any]:
    """Agent-facing ``ref`` → upstream ``target`` (0.0.81 renamed it)."""
    out = {k: v for k, v in args.items() if v is not None}
    if "ref" in out:
        out["target"] = out.pop("ref")
    return out


def _action_result(call: dict[str, Any]) -> dict[str, Any]:
    """Common shape for navigate/click/type/fill: ok + page header."""
    if "error" in call:
        return call
    sections = call["result"]["sections"]
    out: dict[str, Any] = {"ok": True}
    page = _page_info(sections)
    if page:
        out["page"] = page
    if sections.get("Modal state"):
        out["modal_state"] = sections["Modal state"]
    return {"result": out}


async def ucb_navigate_handler(url: str) -> dict[str, Any]:
    call = await _call_mcp("browser_navigate", {"url": url})
    out = _action_result(call)
    if "result" in out:
        out["result"]["note"] = "Page loaded. Call ucb_page_text to read it or ucb_snapshot to get element refs."
    return out


async def ucb_snapshot_handler() -> dict[str, Any]:
    call = await _call_mcp("browser_snapshot", {})
    if "error" in call:
        return call
    sections = call["result"]["sections"]
    snapshot = _strip_fence(sections.get("Snapshot", ""))
    if not snapshot:
        snapshot = call["result"]["text"]
    text, truncated = _truncate(snapshot)
    out: dict[str, Any] = {"snapshot": text, "truncated": truncated}
    page = _page_info(sections)
    if page:
        out["page"] = page
    return {"result": out}


async def ucb_page_text_handler(url: Optional[str] = None) -> dict[str, Any]:
    page: Optional[dict[str, Any]] = None
    if url:
        nav = await _call_mcp("browser_navigate", {"url": url})
        if "error" in nav:
            return nav
        page = _page_info(nav["result"]["sections"])
    call = await _call_mcp("browser_evaluate", {"function": "() => document.body.innerText"})
    if "error" in call:
        return call
    raw = call["result"]["sections"].get("Result", "")
    try:
        value = json.loads(raw)
        text = value if isinstance(value, str) else json.dumps(value)
    except (json.JSONDecodeError, TypeError):
        text = raw
    body, truncated = _truncate(text)
    out: dict[str, Any] = {"text": body, "truncated": truncated, "length": len(text)}
    if page:
        out["page"] = page
    return {"result": out}


async def ucb_click_handler(
    ref: Optional[str] = None,
    element: Optional[str] = None,
    target: Optional[str] = None,  # alias: models trained on Playwright MCP emit it
) -> dict[str, Any]:
    ref = ref or target
    if not ref:
        return {"error": "ucb_click: 'ref' is required (take a ucb_snapshot to get element refs)"}
    call = await _call_mcp("browser_click", _remap_ref({"ref": ref, "element": element}))
    return _action_result(call)


async def ucb_type_handler(
    text: str,
    ref: Optional[str] = None,
    element: Optional[str] = None,
    submit: Optional[bool] = False,
    target: Optional[str] = None,  # alias, see ucb_click_handler
) -> dict[str, Any]:
    ref = ref or target
    if not ref:
        return {"error": "ucb_type: 'ref' is required (take a ucb_snapshot to get element refs)"}
    args = _remap_ref({"ref": ref, "element": element, "text": text})
    if submit:
        args["submit"] = True
    call = await _call_mcp("browser_type", args)
    return _action_result(call)


async def ucb_fill_form_handler(fields: Any) -> dict[str, Any]:
    if isinstance(fields, str):
        try:
            fields = json.loads(fields)
        except json.JSONDecodeError:
            return {"error": "ucb_fill_form: 'fields' must be a JSON array of {name, type, ref, value}"}
    if not isinstance(fields, list) or not fields:
        return {"error": "ucb_fill_form: 'fields' must be a non-empty array of {name, type, ref, value}"}
    cleaned = []
    for f in fields:
        if not isinstance(f, dict):
            return {"error": "ucb_fill_form: each field must be an object {name, type, ref, value}"}
        item = _remap_ref(f)
        if "value" in item and not isinstance(item["value"], str):
            # Upstream wants strings ("true"/"false" for checkboxes).
            v = item["value"]
            item["value"] = ("true" if v else "false") if isinstance(v, bool) else str(v)
        cleaned.append(item)
    call = await _call_mcp("browser_fill_form", {"fields": cleaned})
    return _action_result(call)


async def ucb_screenshot_handler(full_page: Optional[bool] = False) -> dict[str, Any]:
    args: dict[str, Any] = {"scale": "css"}
    if full_page:
        args["fullPage"] = True
    call = await _call_mcp("browser_take_screenshot", args)
    if "error" in call:
        return call
    res = call["result"]
    out: dict[str, Any] = {"saved_as": _first_link(res["sections"].get("Result", ""))}
    if res["images"]:
        img = res["images"][0]
        out["mime_type"] = img["mime_type"]
        out["image_bytes"] = (len(img["data"]) * 3) // 4
        if UC_BROWSER_IMAGE_INLINE_MAX and len(img["data"]) <= UC_BROWSER_IMAGE_INLINE_MAX:
            out["image_base64"] = img["data"]
        else:
            out["image_inlined"] = False
    return {"result": out}


async def ucb_pdf_save_handler() -> dict[str, Any]:
    call = await _call_mcp("browser_pdf_save", {})
    if "error" in call:
        return call
    return {"result": {"saved_as": _first_link(call["result"]["sections"].get("Result", ""))}}


async def ucb_console_messages_handler(level: Optional[str] = "info") -> dict[str, Any]:
    call = await _call_mcp("browser_console_messages", {"level": level or "info"})
    if "error" in call:
        return call
    raw = call["result"]["sections"].get("Result") or call["result"]["text"]
    text, truncated = _truncate(raw)
    return {"result": {"messages": text, "truncated": truncated}}


# ── Tool definitions ───────────────────────────────────────────────────

_REF_DESC = (
    "Exact element reference from the latest ucb_snapshot, e.g. 'e12' "
    "(the [ref=eN] tag), or a unique CSS/text selector."
)
_ELEMENT_DESC = "Short human-readable description of the element, e.g. 'Search box' (recommended)."

UCB_NAVIGATE_TOOL = ToolDefinition(
    name="ucb_navigate",
    description=(
        "Open a URL in the shared real Chrome browser (uc-browser). Returns the "
        "final page URL and title. The page content is NOT returned — follow up "
        "with ucb_page_text (readable text) or ucb_snapshot (element refs for "
        "clicking/typing). Use for sites that need a real browser: JavaScript "
        "apps, logged-in sessions, prices, forms."
    ),
    parameters=[
        ToolParameter(name="url", type="string", description="Absolute URL to open (https://...).", required=True),
    ],
    handler=ucb_navigate_handler,
)

UCB_SNAPSHOT_TOOL = ToolDefinition(
    name="ucb_snapshot",
    description=(
        "Accessibility snapshot of the current page as YAML: every visible "
        "element with its role, name and a [ref=eN] tag. Use the ref values with "
        "ucb_click / ucb_type / ucb_fill_form. Refs change after every "
        "navigation or click — take a fresh snapshot before acting. Long pages "
        "are truncated."
    ),
    parameters=[],
    handler=ucb_snapshot_handler,
)

UCB_PAGE_TEXT_TOOL = ToolDefinition(
    name="ucb_page_text",
    description=(
        "Readable text of the current page (document.body.innerText), truncated "
        "to a safe size. Pass url to navigate first, or omit it to read the page "
        "already open. Best tool for 'what does this page say'."
    ),
    parameters=[
        ToolParameter(
            name="url",
            type="string",
            description="Optional URL to open before reading. Omit to read the current page.",
            required=False,
        ),
    ],
    handler=ucb_page_text_handler,
)

UCB_CLICK_TOOL = ToolDefinition(
    name="ucb_click",
    description=(
        "Click an element on the current page, identified by a ref from "
        "ucb_snapshot. Returns the resulting page URL/title; take a new "
        "ucb_snapshot afterwards."
    ),
    parameters=[
        ToolParameter(name="element", type="string", description=_ELEMENT_DESC, required=False),
        ToolParameter(name="ref", type="string", description=_REF_DESC, required=True),
    ],
    handler=ucb_click_handler,
)

UCB_TYPE_TOOL = ToolDefinition(
    name="ucb_type",
    description=(
        "Type text into an editable element (input, textarea, contenteditable) "
        "identified by a ref from ucb_snapshot. Set submit=true to press Enter "
        "afterwards (e.g. a search box)."
    ),
    parameters=[
        ToolParameter(name="element", type="string", description=_ELEMENT_DESC, required=False),
        ToolParameter(name="ref", type="string", description=_REF_DESC, required=True),
        ToolParameter(name="text", type="string", description="Text to type.", required=True),
        ToolParameter(
            name="submit",
            type="boolean",
            description="Press Enter after typing (default false).",
            required=False,
        ),
    ],
    handler=ucb_type_handler,
)

UCB_FILL_FORM_TOOL = ToolDefinition(
    name="ucb_fill_form",
    description=(
        "Fill several form fields in one call. Each field: {name: human field "
        "name, type: textbox|checkbox|radio|combobox|slider, ref: element ref "
        "from ucb_snapshot, value: string ('true'/'false' for checkboxes, option "
        "text for comboboxes)}. Does not submit — follow with ucb_click on the "
        "submit button."
    ),
    parameters=[
        ToolParameter(
            name="fields",
            type="array",
            description="Fields to fill.",
            required=True,
            items={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Human-readable field name."},
                    "type": {
                        "type": "string",
                        "enum": ["textbox", "checkbox", "radio", "combobox", "slider"],
                        "description": "Field type.",
                    },
                    "ref": {"type": "string", "description": _REF_DESC},
                    "value": {"type": "string", "description": "Value to fill ('true'/'false' for a checkbox)."},
                },
                "required": ["name", "type", "ref", "value"],
            },
        ),
    ],
    handler=ucb_fill_form_handler,
)

UCB_SCREENSHOT_TOOL = ToolDefinition(
    name="ucb_screenshot",
    description=(
        "Take a PNG screenshot of the current page. Returns the path it was "
        "saved under on the browser host (and the image size); the image bytes "
        "are not inlined unless the deployment allows it. Use ucb_snapshot, not "
        "screenshots, to decide what to click."
    ),
    parameters=[
        ToolParameter(
            name="full_page",
            type="boolean",
            description="Capture the whole scrollable page instead of the viewport (default false).",
            required=False,
        ),
    ],
    handler=ucb_screenshot_handler,
)

UCB_PDF_SAVE_TOOL = ToolDefinition(
    name="ucb_pdf_save",
    description="Save the current page as a PDF on the browser host. Returns the saved path.",
    parameters=[],
    handler=ucb_pdf_save_handler,
)

UCB_CONSOLE_MESSAGES_TOOL = ToolDefinition(
    name="ucb_console_messages",
    description=(
        "Browser console messages of the current page since the last "
        "navigation (errors, warnings, logs). Useful when a page misbehaves."
    ),
    parameters=[
        ToolParameter(
            name="level",
            type="string",
            description="Minimum level to return; each level includes the more severe ones (default info).",
            required=False,
            enum=["error", "warning", "info", "debug"],
        ),
    ],
    handler=ucb_console_messages_handler,
)


UC_BROWSER_MCP_TOOLS: dict[str, ToolDefinition] = {
    "ucb_navigate": UCB_NAVIGATE_TOOL,
    "ucb_snapshot": UCB_SNAPSHOT_TOOL,
    "ucb_page_text": UCB_PAGE_TEXT_TOOL,
    "ucb_click": UCB_CLICK_TOOL,
    "ucb_type": UCB_TYPE_TOOL,
    "ucb_fill_form": UCB_FILL_FORM_TOOL,
    "ucb_screenshot": UCB_SCREENSHOT_TOOL,
    "ucb_pdf_save": UCB_PDF_SAVE_TOOL,
    "ucb_console_messages": UCB_CONSOLE_MESSAGES_TOOL,
}
