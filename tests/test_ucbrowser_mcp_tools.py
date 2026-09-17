"""Tests for the uc-browser MCP bridge (app/llm/ucbrowser_mcp_tools.py).

Hermetic: the HTTP layer is an ``httpx.MockTransport`` standing in for both
the uchub token endpoint and the browser gate. The canned gate replies are
the REAL Playwright MCP 0.0.81 ``tools/call`` responses captured on
2026-09-17 from a throwaway headless instance (section layout, error framing,
image content item), trimmed to a data: URL fixture page — so the parser is
tested against what the server actually emits, not against a guess.

Runs standalone (no Postgres / Redis / slack_sdk): the module only imports
``app.llm.ops_center_client`` for the ToolDefinition dataclasses::

    python3 -m pytest tests/test_ucbrowser_mcp_tools.py -q

The tool_resolver registration check is a source-level canary plus an
import-guarded runtime check (skipped when the full dependency set is absent).
"""

import importlib
import json
import os
import re
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs

import httpx
import pytest

import app.llm.ucbrowser_mcp_tools as ucb

TOKEN_URL = "https://auth.test/realms/uchub/protocol/openid-connect/token"
GATE_URL = "https://browser.test/mcp"

# ── Real 0.0.81 reply texts (captured; URL shortened) ─────────────────

PAGE_URL = "https://example.test/fixture"

NAVIGATE_TEXT = (
    "### Ran Playwright code\n```js\nawait page.goto('" + PAGE_URL + "');\n```\n"
    "### Page\n- Page URL: " + PAGE_URL + "\n- Page Title: Fixture Page\n- Console: 1 errors, 0 warnings\n"
    "### Snapshot\n- [Snapshot](pw-out/page-2026-09-17T20-52-09-770Z.yml)\n"
    "### Events\n- New console entries: pw-out/console-2026-09-17T20-52-09-702Z.log#L1-L2"
)

SNAPSHOT_YAML = (
    "- generic [active] [ref=e1]:\n"
    "  - heading \"Hello\" [level=1] [ref=e2]\n"
    "  - paragraph [ref=e3]: Line two & \"quotes\"\n"
    "  - generic [ref=e4]:\n"
    "    - textbox \"Search\" [ref=e5]\n"
    "    - button \"Go\" [ref=e6]"
)
SNAPSHOT_TEXT = (
    "### Page\n- Page URL: " + PAGE_URL + "\n- Page Title: Fixture Page\n- Console: 1 errors, 0 warnings\n"
    "### Snapshot\n```yaml\n" + SNAPSHOT_YAML + "\n```"
)

EVALUATE_TEXT = (
    "### Result\n\"Hello\\n\\nLine two & \\\"quotes\\\"\\n\\nGo\"\n"
    "### Ran Playwright code\n```js\nawait page.evaluate('() => document.body.innerText');\n```"
)

EVALUATE_ERROR_TEXT = (
    "### Error\nError: kaboom\n"
    "    at eval (eval at <anonymous> (eval at evaluate (:311:30)), <anonymous>:1:16)"
)

CLICK_BAD_REF_TEXT = "### Error\nError: Ref e999 not found in the current page snapshot. Try capturing new snapshot."

TYPE_TEXT = "### Ran Playwright code\n```js\nawait page.getByRole('textbox', { name: 'Search' }).fill('unicorns');\n```"

CONSOLE_TEXT = "### Result\nTotal messages: 2 (Errors: 1, Warnings: 0)\n\n[LOG] hi from page @ :0\n[ERROR] boom @ :0"

PDF_TEXT = (
    "### Result\n- [Page as pdf](pw-out/page-2026-09-17T20-52-10-386Z.pdf)\n"
    "### Ran Playwright code\n```js\nawait page.pdf({\n  path: 'pw-out/page-2026-09-17T20-52-10-386Z.pdf'\n});\n```"
)

SCREENSHOT_TEXT = (
    "### Result\n- [Screenshot of viewport](pw-out/page-2026-09-17T20-52-10-314Z.png)\n"
    "### Ran Playwright code\n```js\n// Screenshot viewport and save it as pw-out/page-2026-09-17T20-52-10-314Z.png\n"
    "await page.screenshot({\n  path: 'pw-out/page-2026-09-17T20-52-10-314Z.png',\n  scale: 'css',\n  type: 'png'\n});\n```"
)
# 1x1 PNG, base64 (a real screenshot is ~13k chars; the shape is what matters)
TINY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


def text_result(text: str, is_error: bool = False, images: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    content: List[Dict[str, Any]] = [{"type": "text", "text": text}]
    for img in images or []:
        content.append({"type": "image", "data": img["data"], "mimeType": img["mimeType"]})
    result: Dict[str, Any] = {"content": content}
    if is_error:
        result["isError"] = True
    return result


DEFAULT_TOOL_REPLIES: Dict[str, Dict[str, Any]] = {
    "browser_navigate": text_result(NAVIGATE_TEXT),
    "browser_snapshot": text_result(SNAPSHOT_TEXT),
    "browser_evaluate": text_result(EVALUATE_TEXT),
    "browser_click": text_result(NAVIGATE_TEXT),
    "browser_type": text_result(TYPE_TEXT),
    "browser_fill_form": text_result(TYPE_TEXT),
    "browser_take_screenshot": text_result(
        SCREENSHOT_TEXT, images=[{"data": TINY_PNG_B64, "mimeType": "image/png"}]
    ),
    "browser_pdf_save": text_result(PDF_TEXT),
    "browser_console_messages": text_result(CONSOLE_TEXT),
}


class FakeGate:
    """MockTransport handler standing in for uchub + the browser gate.

    Records every request (parsed) and answers from ``tool_replies`` /
    ``queue``. ``queue`` entries are ``httpx.Response`` objects (or callables
    returning one) consumed in order for MCP-endpoint requests before the
    default routing kicks in; ``sse=True`` frames MCP replies as SSE.
    """

    def __init__(self, sse: bool = False):
        self.sse = sse
        self.requests: List[httpx.Request] = []
        self.token_requests: List[Dict[str, List[str]]] = []
        self.mcp_requests: List[Dict[str, Any]] = []
        self.mcp_headers: List[Dict[str, str]] = []
        self.queue: List[Any] = []
        self.tool_replies: Dict[str, Dict[str, Any]] = dict(DEFAULT_TOOL_REPLIES)
        self.token_status = 200
        self.token_body: Dict[str, Any] = {"access_token": "tok-1", "expires_in": 300}
        self.session_id: Optional[str] = None  # set to emit Mcp-Session-Id on MCP replies

    # -- framing helpers --
    def rpc(self, rpc_id: Any, result: Optional[Dict[str, Any]] = None, error: Optional[Dict[str, Any]] = None,
            status: int = 200, extra_headers: Optional[Dict[str, str]] = None) -> httpx.Response:
        msg: Dict[str, Any] = {"jsonrpc": "2.0", "id": rpc_id}
        if error is not None:
            msg["error"] = error
        else:
            msg["result"] = result
        headers = dict(extra_headers or {})
        if self.sse:
            headers["Content-Type"] = "text/event-stream"
            body = "event: message\ndata: " + json.dumps(msg) + "\n\n"
            return httpx.Response(status, content=body.encode(), headers=headers)
        headers["Content-Type"] = "application/json"
        return httpx.Response(status, content=json.dumps(msg).encode(), headers=headers)

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        url = str(request.url)
        if url == TOKEN_URL:
            self.token_requests.append(parse_qs(request.content.decode()))
            if self.token_status >= 400:
                return httpx.Response(self.token_status, json={"error": "invalid_client"})
            return httpx.Response(200, json=self.token_body)
        if url == GATE_URL:
            body = json.loads(request.content.decode()) if request.content else {}
            self.mcp_requests.append(body)
            self.mcp_headers.append({k.lower(): v for k, v in request.headers.items()})
            if self.queue:
                nxt = self.queue.pop(0)
                return nxt(request, body) if callable(nxt) else nxt
            method = body.get("method")
            if method == "notifications/initialized":
                return httpx.Response(202)
            if method == "initialize":
                return self.rpc(body.get("id"), {"protocolVersion": "2025-06-18", "capabilities": {},
                                                 "serverInfo": {"name": "Playwright", "version": "test"}},
                                extra_headers={"Mcp-Session-Id": self.session_id} if self.session_id else None)
            if method == "tools/call":
                name = body["params"]["name"]
                reply = self.tool_replies.get(name)
                if reply is None:
                    reply = text_result(f'### Error\nTool "{name}" not found', is_error=True)
                return self.rpc(body.get("id"), reply,
                                extra_headers={"Mcp-Session-Id": self.session_id} if self.session_id else None)
            return self.rpc(body.get("id"), error={"code": -32601, "message": "Method not found"})
        return httpx.Response(500, text=f"unexpected url {url}")


@pytest.fixture
def gate(monkeypatch) -> FakeGate:
    g = FakeGate()

    def _client(timeout: float) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(g.handle), timeout=timeout)

    monkeypatch.setattr(ucb, "_http_client", _client)
    monkeypatch.setattr(ucb, "UC_BROWSER_MCP_URL", GATE_URL)
    monkeypatch.setattr(ucb, "UC_BROWSER_TOKEN_URL", TOKEN_URL)
    monkeypatch.setattr(ucb, "UC_BROWSER_CLIENT_ID", "brigade")
    monkeypatch.setattr(ucb, "UC_BROWSER_CLIENT_SECRET", "test-secret-not-real")
    monkeypatch.setattr(ucb, "UC_BROWSER_IMAGE_INLINE_MAX", 0)
    monkeypatch.setattr(ucb, "UC_BROWSER_TEXT_MAX", 20000)
    # per-process state must not leak between tests
    ucb._TOKEN_CACHE.update({"token": None, "exp": 0.0})
    ucb._SESSION["id"] = None
    yield g
    ucb._TOKEN_CACHE.update({"token": None, "exp": 0.0})
    ucb._SESSION["id"] = None


def last_call(gate: FakeGate) -> Dict[str, Any]:
    calls = [r for r in gate.mcp_requests if r.get("method") == "tools/call"]
    assert calls, "no tools/call was made"
    return calls[-1]


# ── token mint ────────────────────────────────────────────────────────


async def test_token_mint_request_shape_and_cache(gate):
    out = await ucb.ucb_snapshot_handler()
    assert "result" in out, out
    assert len(gate.token_requests) == 1
    form = gate.token_requests[0]
    assert form["grant_type"] == ["client_credentials"]
    assert form["client_id"] == ["brigade"]
    assert form["client_secret"] == ["test-secret-not-real"]
    token_req = gate.requests[0]
    assert token_req.headers["user-agent"].startswith("Mozilla/5.0")
    assert token_req.headers["content-type"].startswith("application/x-www-form-urlencoded")
    # Second tool call reuses the cached bearer: still one token mint.
    await ucb.ucb_snapshot_handler()
    assert len(gate.token_requests) == 1
    assert all(h["authorization"] == "Bearer tok-1" for h in gate.mcp_headers)


async def test_token_mint_failure_is_a_tool_error_and_makes_no_mcp_call(gate):
    gate.token_status = 401
    out = await ucb.ucb_navigate_handler("https://example.test/")
    assert "error" in out and "token" in out["error"]
    assert gate.mcp_requests == []


async def test_missing_client_secret_short_circuits(gate, monkeypatch):
    monkeypatch.setattr(ucb, "UC_BROWSER_CLIENT_SECRET", "")
    out = await ucb.ucb_navigate_handler("https://example.test/")
    assert "error" in out
    assert gate.requests == []


async def test_unconfigured_gate_url_errors_without_network(gate, monkeypatch):
    monkeypatch.setattr(ucb, "UC_BROWSER_MCP_URL", "")
    out = await ucb.ucb_snapshot_handler()
    assert "error" in out and "UC_BROWSER_MCP_URL" in out["error"]
    assert gate.requests == []


# ── request shapes per tool ───────────────────────────────────────────


async def test_navigate_request_shape_and_result(gate):
    out = await ucb.ucb_navigate_handler("https://example.test/fixture")
    call = last_call(gate)
    assert call["jsonrpc"] == "2.0" and isinstance(call["id"], int)
    assert call["method"] == "tools/call"
    assert call["params"] == {"name": "browser_navigate", "arguments": {"url": "https://example.test/fixture"}}
    hdrs = gate.mcp_headers[-1]
    assert hdrs["accept"] == "application/json, text/event-stream"
    assert hdrs["content-type"] == "application/json"
    assert hdrs["authorization"] == "Bearer tok-1"
    assert not hdrs["user-agent"].startswith("python-httpx"), "Cloudflare 403s the default UA"
    assert out["result"]["ok"] is True
    assert out["result"]["page"]["url"] == PAGE_URL
    assert out["result"]["page"]["title"] == "Fixture Page"
    assert "ucb_page_text" in out["result"]["note"]


async def test_snapshot_returns_inline_yaml_with_refs(gate):
    out = await ucb.ucb_snapshot_handler()
    assert last_call(gate)["params"] == {"name": "browser_snapshot", "arguments": {}}
    snap = out["result"]["snapshot"]
    assert snap == SNAPSHOT_YAML  # fence stripped, nothing else leaked in
    assert "[ref=e5]" in snap and "```" not in snap
    assert out["result"]["truncated"] is False
    assert out["result"]["page"]["title"] == "Fixture Page"


async def test_page_text_navigates_then_evaluates(gate):
    out = await ucb.ucb_page_text_handler(url="https://example.test/fixture")
    calls = [r["params"] for r in gate.mcp_requests if r["method"] == "tools/call"]
    assert [c["name"] for c in calls] == ["browser_navigate", "browser_evaluate"]
    assert calls[1]["arguments"] == {"function": "() => document.body.innerText"}
    # The Result section is a JSON-encoded string → decoded to real text
    assert out["result"]["text"] == 'Hello\n\nLine two & "quotes"\n\nGo'
    assert out["result"]["truncated"] is False
    assert out["result"]["length"] == len(out["result"]["text"])
    assert out["result"]["page"]["url"] == PAGE_URL


async def test_page_text_without_url_reads_current_page(gate):
    out = await ucb.ucb_page_text_handler()
    names = [r["params"]["name"] for r in gate.mcp_requests if r["method"] == "tools/call"]
    assert names == ["browser_evaluate"]
    assert "page" not in out["result"]
    assert out["result"]["text"].startswith("Hello")


async def test_page_text_truncates_to_cap(gate, monkeypatch):
    monkeypatch.setattr(ucb, "UC_BROWSER_TEXT_MAX", 50)
    long_text = "word " * 1000
    gate.tool_replies["browser_evaluate"] = text_result("### Result\n" + json.dumps(long_text))
    out = await ucb.ucb_page_text_handler()
    assert out["result"]["truncated"] is True
    assert out["result"]["length"] == len(long_text)
    assert out["result"]["text"].startswith("word word")
    assert "[truncated:" in out["result"]["text"]
    assert len(out["result"]["text"]) < 120


async def test_click_remaps_ref_to_target(gate):
    out = await ucb.ucb_click_handler(element="Go button", ref="e6")
    args = last_call(gate)["params"]["arguments"]
    assert args == {"element": "Go button", "target": "e6"}
    assert "ref" not in args
    assert out["result"]["ok"] is True and out["result"]["page"]["title"] == "Fixture Page"


async def test_click_accepts_target_alias_and_requires_a_ref(gate):
    await ucb.ucb_click_handler(target="e6")
    assert last_call(gate)["params"]["arguments"] == {"target": "e6"}
    out = await ucb.ucb_click_handler(element="nothing")
    assert "error" in out and "ref" in out["error"]


async def test_type_sends_target_text_and_submit_only_when_set(gate):
    await ucb.ucb_type_handler(element="Search box", ref="e5", text="unicorns")
    args = last_call(gate)["params"]["arguments"]
    assert args == {"element": "Search box", "target": "e5", "text": "unicorns"}
    await ucb.ucb_type_handler(ref="e5", text="unicorns", submit=True)
    args = last_call(gate)["params"]["arguments"]
    assert args == {"target": "e5", "text": "unicorns", "submit": True}
    assert last_call(gate)["params"]["name"] == "browser_type"


async def test_fill_form_remaps_nested_ref_and_stringifies_bools(gate):
    fields = [
        {"name": "q", "type": "textbox", "ref": "e5", "value": "filled"},
        {"name": "agree", "type": "checkbox", "ref": "e7", "value": True},
    ]
    out = await ucb.ucb_fill_form_handler(fields)
    call = last_call(gate)["params"]
    assert call["name"] == "browser_fill_form"
    assert call["arguments"] == {"fields": [
        {"name": "q", "type": "textbox", "target": "e5", "value": "filled"},
        {"name": "agree", "type": "checkbox", "target": "e7", "value": "true"},
    ]}
    assert out["result"]["ok"] is True


async def test_fill_form_accepts_json_string_and_rejects_garbage(gate):
    await ucb.ucb_fill_form_handler('[{"name":"q","type":"textbox","ref":"e5","value":"x"}]')
    assert last_call(gate)["params"]["arguments"]["fields"][0]["target"] == "e5"
    assert "error" in await ucb.ucb_fill_form_handler("not json")
    assert "error" in await ucb.ucb_fill_form_handler([])
    assert "error" in await ucb.ucb_fill_form_handler(["e5"])


async def test_screenshot_returns_saved_path_and_size_without_base64(gate):
    out = await ucb.ucb_screenshot_handler()
    args = last_call(gate)["params"]["arguments"]
    assert args == {"scale": "css"}  # 'scale' is required upstream despite its default
    res = out["result"]
    assert res["saved_as"] == "pw-out/page-2026-09-17T20-52-10-314Z.png"
    assert res["mime_type"] == "image/png"
    assert res["image_bytes"] == (len(TINY_PNG_B64) * 3) // 4
    assert res["image_inlined"] is False and "image_base64" not in res


async def test_screenshot_inlines_base64_when_allowed_and_full_page_flag(gate, monkeypatch):
    monkeypatch.setattr(ucb, "UC_BROWSER_IMAGE_INLINE_MAX", 10_000)
    out = await ucb.ucb_screenshot_handler(full_page=True)
    assert last_call(gate)["params"]["arguments"] == {"scale": "css", "fullPage": True}
    assert out["result"]["image_base64"] == TINY_PNG_B64


async def test_pdf_save_returns_saved_path(gate):
    out = await ucb.ucb_pdf_save_handler()
    assert last_call(gate)["params"] == {"name": "browser_pdf_save", "arguments": {}}
    assert out["result"] == {"saved_as": "pw-out/page-2026-09-17T20-52-10-386Z.pdf"}


async def test_console_messages_always_sends_level(gate):
    out = await ucb.ucb_console_messages_handler()
    assert last_call(gate)["params"]["arguments"] == {"level": "info"}
    assert out["result"]["messages"].startswith("Total messages: 2")
    assert "[ERROR] boom" in out["result"]["messages"]
    await ucb.ucb_console_messages_handler(level="error")
    assert last_call(gate)["params"]["arguments"] == {"level": "error"}


# ── transport: SSE unwrap, session header, handshake ──────────────────


async def test_sse_framed_reply_parses_the_same(gate):
    gate.sse = True
    out = await ucb.ucb_snapshot_handler()
    assert out["result"]["snapshot"] == SNAPSHOT_YAML


def test_parse_streamable_response_keeps_last_response_frame():
    body = (
        'event: message\ndata: {"jsonrpc":"2.0","method":"notifications/message","params":{"x":1}}\n\n'
        'event: message\ndata: {"jsonrpc":"2.0","id":7,"result":{"content":[]}}\n\n'
    )
    assert ucb._parse_streamable_response(body) == {"jsonrpc": "2.0", "id": 7, "result": {"content": []}}
    assert ucb._parse_streamable_response('{"jsonrpc":"2.0","id":1,"result":{}}') == {"jsonrpc": "2.0", "id": 1, "result": {}}
    assert ucb._parse_streamable_response("") == {}
    with pytest.raises(ValueError):
        ucb._parse_streamable_response("<html>nope</html>")


async def test_session_id_from_gate_is_stored_and_resent(gate):
    gate.session_id = "sess-42"
    await ucb.ucb_snapshot_handler()
    assert "mcp-session-id" not in gate.mcp_headers[0]  # nothing to send yet
    assert ucb._SESSION["id"] == "sess-42"
    await ucb.ucb_snapshot_handler()
    assert gate.mcp_headers[-1]["mcp-session-id"] == "sess-42"


async def test_missing_session_triggers_one_handshake_and_retry(gate):
    gate.session_id = "sess-new"
    ucb._SESSION["id"] = "sess-stale"
    # First tools/call is refused the way the MCP SDK does it (HTTP 400, -32000).
    gate.queue.append(gate.rpc(None, error={"code": -32000, "message": "Bad Request: Server not initialized"}, status=400))
    out = await ucb.ucb_snapshot_handler()
    assert "result" in out, out
    methods = [r["method"] for r in gate.mcp_requests]
    assert methods == ["tools/call", "initialize", "notifications/initialized", "tools/call"]
    init_req = gate.mcp_requests[1]
    assert init_req["params"]["protocolVersion"] == "2025-06-18"
    assert init_req["params"]["clientInfo"]["name"] == "unicorn-brigade"
    # stale id is NOT sent on the handshake; the new one is sent on the retry
    assert "mcp-session-id" not in gate.mcp_headers[1]
    assert gate.mcp_headers[3]["mcp-session-id"] == "sess-new"
    assert ucb._SESSION["id"] == "sess-new"


async def test_handshake_is_not_repeated_when_retry_fails(gate):
    gate.queue.append(gate.rpc(None, error={"code": -32001, "message": "Session not found"}, status=404))
    gate.queue.append(httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2025-06-18"}}))
    gate.queue.append(httpx.Response(202))
    gate.queue.append(gate.rpc(None, error={"code": -32001, "message": "Session not found"}, status=404))
    out = await ucb.ucb_snapshot_handler()
    assert "error" in out and "HTTP 404" in out["error"]
    assert [r["method"] for r in gate.mcp_requests] == ["tools/call", "initialize", "notifications/initialized", "tools/call"]


async def test_plain_400_without_session_hint_is_not_a_handshake(gate):
    gate.queue.append(httpx.Response(400, json={"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": "Invalid params: url"}}))
    out = await ucb.ucb_navigate_handler("nope")
    assert "error" in out and "HTTP 400" in out["error"]
    assert [r["method"] for r in gate.mcp_requests] == ["tools/call"]


# ── error mapping ─────────────────────────────────────────────────────


async def test_is_error_result_maps_to_tool_error_text(gate):
    gate.tool_replies["browser_click"] = text_result(CLICK_BAD_REF_TEXT, is_error=True)
    out = await ucb.ucb_click_handler(ref="e999")
    assert "result" not in out
    assert "Ref e999 not found" in out["error"]
    assert out["error"].startswith("ucbrowser-mcp browser_click:")


async def test_evaluate_error_surfaces_from_page_text(gate):
    gate.tool_replies["browser_evaluate"] = text_result(EVALUATE_ERROR_TEXT, is_error=True)
    out = await ucb.ucb_page_text_handler()
    assert "kaboom" in out["error"]


async def test_jsonrpc_error_object_maps_to_error(gate):
    gate.queue.append(gate.rpc(1, error={"code": -32602, "message": "Invalid params"}))
    out = await ucb.ucb_snapshot_handler()
    assert out == {"error": "-32602 Invalid params"}


async def test_http_error_maps_to_error(gate):
    gate.queue.append(httpx.Response(502, text="<html>bad gateway</html>"))
    out = await ucb.ucb_snapshot_handler()
    assert out["error"].startswith("ucbrowser-mcp HTTP 502")


async def test_timeout_maps_to_error(gate):
    def boom(request, body):
        raise httpx.ReadTimeout("slow", request=request)

    gate.queue.append(boom)
    out = await ucb.ucb_navigate_handler("https://slow.test/")
    assert "timed out" in out["error"]


async def test_empty_content_is_not_a_crash(gate):
    gate.tool_replies["browser_pdf_save"] = {"content": []}
    out = await ucb.ucb_pdf_save_handler()
    assert out == {"result": {"saved_as": None}}


# ── definitions / registration ────────────────────────────────────────


def test_tool_definitions_and_openai_schemas():
    names = list(ucb.UC_BROWSER_MCP_TOOLS)
    assert names == [
        "ucb_navigate", "ucb_snapshot", "ucb_page_text", "ucb_click", "ucb_type",
        "ucb_fill_form", "ucb_screenshot", "ucb_pdf_save", "ucb_console_messages",
    ]
    for name, tool in ucb.UC_BROWSER_MCP_TOOLS.items():
        assert tool.name == name and tool.handler is not None and tool.description
        assert tool.needs_caller_context is False and tool.needs_room_context is False
        fmt = tool.to_openai_format()
        fn = fmt.get("function", fmt)
        assert fn["name"] == name
    click = ucb.UCB_CLICK_TOOL.to_openai_format()
    fn = click.get("function", click)
    assert fn["parameters"]["required"] == ["ref"]
    assert set(fn["parameters"]["properties"]) == {"element", "ref"}
    typ = ucb.UCB_TYPE_TOOL.to_openai_format()
    fn = typ.get("function", typ)
    assert fn["parameters"]["required"] == ["ref", "text"]
    assert fn["parameters"]["properties"]["submit"]["type"] == "boolean"
    form = ucb.UCB_FILL_FORM_TOOL.to_openai_format()
    fn = form.get("function", form)
    items = fn["parameters"]["properties"]["fields"]["items"]
    assert items["type"] == "object" and items["required"] == ["name", "type", "ref", "value"]
    assert items["properties"]["type"]["enum"] == ["textbox", "checkbox", "radio", "combobox", "slider"]
    console = ucb.UCB_CONSOLE_MESSAGES_TOOL.to_openai_format()
    fn = console.get("function", console)
    assert fn["parameters"]["properties"]["level"]["enum"] == ["error", "warning", "info", "debug"]


def test_tool_resolver_gates_registration_on_env_source_canary():
    here = os.path.dirname(os.path.abspath(__file__))
    src = open(os.path.join(here, "..", "app", "llm", "tool_resolver.py"), encoding="utf-8").read()
    block = re.search(
        r'if os\.getenv\("UC_BROWSER_MCP_URL"\):.*?from app\.llm\.ucbrowser_mcp_tools import UC_BROWSER_MCP_TOOLS'
        r'.*?TOOL_REGISTRY\.update\(UC_BROWSER_MCP_TOOLS\)',
        src, re.S,
    )
    assert block, "tool_resolver must register UC_BROWSER_MCP_TOOLS only when UC_BROWSER_MCP_URL is set"
    before_gate = src.split('if os.getenv("UC_BROWSER_MCP_URL")')[0]
    assert not re.search(r"^\s*from app\.llm\.ucbrowser_mcp_tools import", before_gate, re.M), \
        "the uc-browser module must not be imported unconditionally"


def test_tool_resolver_registers_ucb_tools_when_env_set(monkeypatch):
    pytest.importorskip("slack_sdk", reason="tool_resolver needs the full dependency set")
    try:
        import app.llm.tool_resolver as resolver
    except Exception as exc:  # noqa: BLE001 — heavy import chain
        pytest.skip(f"tool_resolver not importable here: {exc}")
    monkeypatch.setenv("UC_BROWSER_MCP_URL", GATE_URL)
    resolver = importlib.reload(resolver)
    assert set(ucb.UC_BROWSER_MCP_TOOLS) <= set(resolver.TOOL_REGISTRY)
    agent = {"tools": ["ucb_navigate", "ucb_page_text", "ucb_snapshot", "ucb_screenshot", "nope"]}
    assert [t.name for t in resolver.get_tools_for_agent(agent)] == [
        "ucb_navigate", "ucb_page_text", "ucb_snapshot", "ucb_screenshot",
    ]
    monkeypatch.delenv("UC_BROWSER_MCP_URL")
    resolver = importlib.reload(resolver)
    assert not any(k.startswith("ucb_") for k in resolver.TOOL_REGISTRY)
