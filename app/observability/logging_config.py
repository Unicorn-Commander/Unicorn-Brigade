"""Structured logging + request-id correlation for Unicorn Brigade.

Three pieces work together:

1. Context vars (``request_id_ctx``, ``mission_id_ctx``, ``agent_id_ctx``)
   carry per-request identity down the async call stack without threading
   arguments through every function.
2. ``RequestContextFilter`` stamps those values onto every LogRecord so any
   logger in the process emits them — no code change at the call site.
3. ``JsonFormatter`` renders records as one-line JSON (stdlib only, no new
   dependency) so a log shipper can index ``request_id`` / ``mission_id`` /
   ``agent_id`` directly.

``request_id_middleware`` (an ASGI/http middleware mounted in ``app.main``)
reads or mints ``X-Request-ID``, binds it to the context var for the life of
the request, and echoes it back on the response so a caller can correlate.
"""

from __future__ import annotations

import contextvars
import json
import logging
import os
import time
import uuid
from typing import Callable

from starlette.requests import Request
from starlette.responses import Response

# ── context vars ──────────────────────────────────────────────
# Empty string (not None) is the "unset" sentinel so the JSON formatter can
# cheaply skip absent fields.
request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default=""
)
mission_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "mission_id", default=""
)
agent_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "agent_id", default=""
)

REQUEST_ID_HEADER = "X-Request-ID"

# Standard LogRecord attributes we never want duplicated into the JSON body.
_RESERVED = frozenset(
    {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "taskName", "message", "asctime",
        # our injected fields — serialized explicitly below
        "request_id", "mission_id", "agent_id",
    }
)


class RequestContextFilter(logging.Filter):
    """Stamp request/mission/agent ids from context vars onto every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        # getattr guard so a record that already set these (rare) is respected.
        if not getattr(record, "request_id", ""):
            record.request_id = request_id_ctx.get("")
        if not getattr(record, "mission_id", ""):
            record.mission_id = mission_id_ctx.get("")
        if not getattr(record, "agent_id", ""):
            record.agent_id = agent_id_ctx.get("")
        return True


class JsonFormatter(logging.Formatter):
    """Render a LogRecord as a single line of JSON (stdlib only)."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created))
            + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Correlation ids — only when present.
        for key in ("request_id", "mission_id", "agent_id"):
            val = getattr(record, key, "")
            if val:
                payload[key] = val

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack_info"] = self.formatStack(record.stack_info)

        # Any structured extras attached via logger.*(..., extra={...}).
        for key, val in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                try:
                    json.dumps(val)
                    payload[key] = val
                except (TypeError, ValueError):
                    payload[key] = str(val)

        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str | None = None, json_logs: bool | None = None) -> None:
    """Install the context filter + formatter on the root logger.

    Idempotent: repeated calls reconfigure the single handler rather than
    stacking new ones. ``json_logs`` defaults to on unless ``LOG_JSON=false``.
    """
    level = level or os.getenv("LOG_LEVEL", "INFO")
    if json_logs is None:
        json_logs = os.getenv("LOG_JSON", "true").strip().lower() in (
            "1", "true", "yes", "on",
        )

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    context_filter = RequestContextFilter()
    if json_logs:
        formatter: logging.Formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s "
            "[req=%(request_id)s mission=%(mission_id)s agent=%(agent_id)s] "
            "- %(message)s"
        )

    # Reuse an existing StreamHandler if one is already attached (avoids the
    # duplicate-line problem when uvicorn/basicConfig already added one).
    handler = None
    for h in root.handlers:
        if isinstance(h, logging.StreamHandler):
            handler = h
            break
    if handler is None:
        handler = logging.StreamHandler()
        root.addHandler(handler)

    handler.setFormatter(formatter)
    # Ensure the filter is present exactly once.
    if not any(isinstance(f, RequestContextFilter) for f in handler.filters):
        handler.addFilter(context_filter)


async def request_id_middleware(request: Request, call_next: Callable) -> Response:
    """Bind an ``X-Request-ID`` to the context var for the request's lifetime."""
    incoming = request.headers.get(REQUEST_ID_HEADER, "").strip()
    request_id = incoming or uuid.uuid4().hex
    token = request_id_ctx.set(request_id)
    # Expose on request.state for handlers that want it explicitly.
    try:
        request.state.request_id = request_id
    except Exception:
        pass
    try:
        response = await call_next(request)
    finally:
        request_id_ctx.reset(token)
    response.headers[REQUEST_ID_HEADER] = request_id
    return response
