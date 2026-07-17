"""Prometheus metrics for Unicorn Brigade.

Exposes /metrics with request counters, request-duration histogram, and
agent-execution counters. The metrics module is import-safe — no side
effects unless the middleware is registered with the FastAPI app.
"""
import os
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

scheduled_run_total = Counter(
    "brigade_scheduled_run_total",
    "Scheduled agent runs by outcome",
    ["outcome"],  # outcome: success | error | timeout | agent_missing
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


def _metrics_authorized(request: Request) -> bool:
    """Gate /metrics.

    When ``METRICS_TOKEN`` is set, require it as a bearer token or ``?token=``
    query param — the Prometheus scrape config supplies it. When unset, only
    allow scrapes from private/loopback source addresses (internal bind), so a
    public deployment does not leak metrics by default. ``METRICS_PUBLIC=true``
    restores the old unauthenticated behavior for trusted internal networks.
    """
    if os.getenv("METRICS_PUBLIC", "false").strip().lower() in ("1", "true", "yes", "on"):
        return True

    token = os.getenv("METRICS_TOKEN", "").strip()
    if token:
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer ") and auth[7:].strip() == token:
            return True
        if request.query_params.get("token", "") == token:
            return True
        return False

    # No token configured → restrict to internal/loopback source addresses.
    client_host = request.client.host if request.client else ""
    if _is_internal_host(client_host):
        return True
    return False


def _is_internal_host(host: str) -> bool:
    """True for loopback / RFC-1918 / container-network source addresses."""
    if not host:
        return False
    try:
        import ipaddress

        ip = ipaddress.ip_address(host)
        return ip.is_loopback or ip.is_private or ip.is_link_local
    except ValueError:
        # Non-IP host (e.g. a docker service name proxied through) — treat as
        # internal only for the obvious localhost aliases.
        return host in ("localhost", "127.0.0.1", "::1")


def metrics_endpoint(request: Request) -> Response:
    """GET /metrics — Prometheus scrape endpoint (gated; see _metrics_authorized)."""
    if not _metrics_authorized(request):
        return Response("forbidden", status_code=403)
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
