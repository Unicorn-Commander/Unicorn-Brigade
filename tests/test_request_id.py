"""Focused unit tests for request-id correlation + structured logging.

These exercise app.observability.logging_config in isolation (no full app
import), so they run even with the repo's optional-dep collection errors.
"""

import json
import logging

from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.observability.logging_config import (
    JsonFormatter,
    RequestContextFilter,
    REQUEST_ID_HEADER,
    request_id_ctx,
    mission_id_ctx,
    agent_id_ctx,
    request_id_middleware,
)


def _record(msg="hello"):
    return logging.LogRecord(
        name="test", level=logging.INFO, pathname=__file__, lineno=1,
        msg=msg, args=(), exc_info=None,
    )


def test_filter_stamps_context_ids():
    token = request_id_ctx.set("req-abc")
    mtoken = mission_id_ctx.set("mission-1")
    atoken = agent_id_ctx.set("col-finance")
    try:
        rec = _record()
        assert RequestContextFilter().filter(rec) is True
        assert rec.request_id == "req-abc"
        assert rec.mission_id == "mission-1"
        assert rec.agent_id == "col-finance"
    finally:
        request_id_ctx.reset(token)
        mission_id_ctx.reset(mtoken)
        agent_id_ctx.reset(atoken)


def test_filter_empty_when_unset():
    # Fresh context — no ids bound.
    rec = _record()
    RequestContextFilter().filter(rec)
    assert rec.request_id == ""
    assert rec.mission_id == ""


def test_json_formatter_includes_present_ids_only():
    token = request_id_ctx.set("req-xyz")
    try:
        rec = _record("structured line")
        RequestContextFilter().filter(rec)
        out = JsonFormatter().format(rec)
        payload = json.loads(out)  # must be valid JSON
        assert payload["message"] == "structured line"
        assert payload["level"] == "INFO"
        assert payload["request_id"] == "req-xyz"
        # mission/agent unset → omitted, not null
        assert "mission_id" not in payload
        assert "agent_id" not in payload
    finally:
        request_id_ctx.reset(token)


def test_json_formatter_serializes_exc_info():
    try:
        raise ValueError("boom")
    except ValueError:
        import sys
        rec = logging.LogRecord(
            name="test", level=logging.ERROR, pathname=__file__, lineno=1,
            msg="failed", args=(), exc_info=sys.exc_info(),
        )
    payload = json.loads(JsonFormatter().format(rec))
    assert "exc_info" in payload
    assert "ValueError" in payload["exc_info"]


def _build_app():
    async def echo(request):
        # The middleware must have bound the id by the time the handler runs.
        return PlainTextResponse(request_id_ctx.get(""))

    app = Starlette(routes=[Route("/echo", echo)])
    app.middleware("http")(request_id_middleware)
    return app


def test_middleware_generates_request_id():
    client = TestClient(_build_app())
    resp = client.get("/echo")
    assert resp.status_code == 200
    rid = resp.headers.get(REQUEST_ID_HEADER)
    assert rid and len(rid) >= 8
    # Handler saw the same id that came back on the response header.
    assert resp.text == rid


def test_middleware_propagates_incoming_id():
    client = TestClient(_build_app())
    resp = client.get("/echo", headers={REQUEST_ID_HEADER: "caller-123"})
    assert resp.headers.get(REQUEST_ID_HEADER) == "caller-123"
    assert resp.text == "caller-123"


def test_middleware_resets_context_after_request():
    client = TestClient(_build_app())
    client.get("/echo", headers={REQUEST_ID_HEADER: "caller-123"})
    # Context must not leak across requests.
    assert request_id_ctx.get("") == ""
