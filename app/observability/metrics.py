"""Prometheus metrics for Unicorn Brigade.

Exposes /metrics with request counters, request-duration histogram, and
agent-execution counters. The metrics module is import-safe — no side
effects unless the middleware is registered with the FastAPI app.
"""
import time
import re
from typing import Callable

from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    CONTENT_TYPE_LATEST,
    generate_latest,
    CollectorRegistry,
    multiprocess,
)
from starlette.requests import Request
from starlette.responses import Response


# Bound label cardinality. UUIDs in path → :uuid; numbers → :num.
_UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)


def normalize_path(path: str) -> str:
    p = _UUID_RE.sub(":uuid", path)
    return p


# ---- Metric definitions ----

http_requests_total = Counter(
    "brigade_http_requests_total",
    "HTTP requests by method, route, and status class",
    ["method", "route", "status_class"],
)

http_request_duration_seconds = Histogram(
    "brigade_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "route"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120, 300, 600),
)

agent_chat_total = Counter(
    "brigade_agent_chat_total",
    "Agent chat completions by agent and outcome",
    ["agent", "outcome"],  # outcome: ok | error | tool_loop_max
)

agent_tool_calls_total = Counter(
    "brigade_agent_tool_calls_total",
    "Tool calls executed during agent runs",
    ["agent", "tool"],
)

agent_active = Gauge(
    "brigade_agent_active",
    "Active agent calls in flight",
    ["agent"],
)


async def metrics_middleware(request: Request, call_next: Callable):
    """Records every HTTP request. Mounted via app.middleware("http")."""
    start = time.perf_counter()
    try:
        response = await call_next(request)
        status = response.status_code
    except Exception:
        # Let exception propagate but still record it
        status = 500
        raise
    finally:
        elapsed = time.perf_counter() - start
        # Use the matched route template (e.g., /api/v1/agents/{agent_id})
        # if available, else the raw path with UUID scrubbing.
        route = None
        if hasattr(request, "scope") and "route" in request.scope:
            r = request.scope.get("route")
            route = getattr(r, "path", None) or getattr(r, "path_format", None)
        if not route:
            route = normalize_path(request.url.path)
        method = request.method
        try:
            http_requests_total.labels(
                method=method,
                route=route,
                status_class=f"{status // 100}xx",
            ).inc()
            http_request_duration_seconds.labels(
                method=method,
                route=route,
            ).observe(elapsed)
        except Exception:
            # Never let metrics break the request
            pass
    return response


def metrics_endpoint(request: Request) -> Response:
    """GET /metrics — Prometheus scrape endpoint."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
