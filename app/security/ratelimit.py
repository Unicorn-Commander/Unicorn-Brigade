"""
Per-identity rate-limiting middleware (BR-6 enterprise hardening).

An in-memory token-bucket limiter applied to auth-sensitive and execution
("exec") routes. Each identity gets a bucket that refills at a steady rate up to
a burst capacity; a request costs one token, and when the bucket is empty the
request is rejected with ``429 Too Many Requests`` + a ``Retry-After`` header.

Identity key (precedence):
  1. Loopback delegations (127.0.0.1 / ::1) carrying ``X-Delegate-User`` bucket on
     that end-user, so concurrent delegations for different users don't all
     starve on one shared service-key bucket. S8: only honored when a service key
     is ALSO presented — otherwise the bucket key would be a fully
     attacker-controlled header on the loopback path.
  2. The PRESENTED API key (``X-API-Key``, or a ``Bearer`` credential) hashed to a
     stable id. We hash the presented credential rather than the DB key-id because
     this middleware runs BEFORE auth resolves — a DB lookup on the hot path would
     defeat the purpose of a cheap pre-auth abuse cap.
  3. The ``brigade_session`` cookie (browser users authenticate with it, not an
     API key) hashed — so each browser user gets their OWN bucket.
  4. The SSE ticket (``?ticket=`` query param or the ``brigade_sse_ticket``
     cookie) hashed — so each EventSource consumer gets its OWN bucket. C2: browser
     + SSE callers previously carried none of {api key} and all collapsed onto a
     single ``ip:<host>`` bucket, so shared-NAT users 429'd each other.
  5. Fallback: client IP.

============================ MULTI-REPLICA FOLLOW-UP ============================
⚠️ This limiter is PER-PROCESS and IN-MEMORY ONLY. Each uvicorn worker / replica
keeps its own bucket table, so the effective cluster-wide limit is
(configured limit x replica count) and all buckets reset on restart. A
Redis-backed SHARED token bucket (atomic INCR/EXPIRE or a Lua bucket script) is
the correct multi-replica limiter and is the planned follow-up. Do NOT add Redis
here now — this layer is a deliberately cheap per-process flood cap that composes
with the finer-grained per-route ``app.security.rate_limit`` dependencies.
================================================================================
"""

import hashlib
import json
import os
import time
from typing import Dict, Optional, Tuple

from starlette.datastructures import Headers
from starlette.requests import HTTPConnection
from starlette.types import ASGIApp, Receive, Scope, Send

# Auth-credential names folded into the per-identity bucket key so browser
# (cookie) and SSE (ticket) callers each get their OWN bucket instead of all
# collapsing onto a shared ``ip:<host>`` bucket (shared-NAT users would otherwise
# 429 each other). Kept in sync with the auth layer's source of truth:
#   app.auth.middleware.OIDC_SESSION_COOKIE   = "brigade_session"
#   app.auth.sse_ticket.SSE_TICKET_COOKIE     = "brigade_sse_ticket"
# Defined locally (not imported) so this middleware stays self-contained
# (starlette + stdlib only, per the module docstring) and free of an app.auth
# import at startup.
_SESSION_COOKIE = "brigade_session"
_SSE_TICKET_COOKIE = "brigade_sse_ticket"


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


# Default path prefixes to protect: auth-sensitive + exec (LLM / tool / code-exec)
# routes. Read-only browse endpoints are intentionally excluded so normal usage
# isn't throttled. Override the WHOLE set via ``SECURITY_RATELIMIT_PATHS``.
DEFAULT_RATELIMIT_PATHS = ",".join(
    [
        # --- auth-sensitive ---
        "/api/v1/users/login",
        "/api/v1/users/register",
        "/api/v1/users/me/api-keys",
        "/api/auth",
        "/api/v1/auth",
        "/api/v1/federation/token",
        # --- exec / LLM / tool / code ---
        "/api/v1/agents",  # chat + execute + import
        "/api/v1/chat",
        "/api/v1/openai",
        "/api/v1/orchestration",
        "/api/v1/a2a",
        "/api/v1/mcp",
        "/api/v1/hierarchical",
        "/api/v1/ralph",
        "/api/v1/crisis",
    ]
)

# When the bucket table grows past this many keys, opportunistically prune idle
# (fully-refilled) buckets to bound memory against key/IP churn.
_PRUNE_THRESHOLD = 10_000


class _Bucket:
    __slots__ = ("tokens", "updated")

    def __init__(self, tokens: float, updated: float) -> None:
        self.tokens = tokens
        self.updated = updated


class RateLimitMiddleware:
    """Per-identity token-bucket limiter for sensitive routes (pure ASGI)."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        enabled: Optional[bool] = None,
        burst: Optional[int] = None,
        refill_per_sec: Optional[float] = None,
        paths: Optional[Tuple[str, ...]] = None,
    ) -> None:
        self.app = app
        self.enabled = (
            enabled
            if enabled is not None
            else _bool_env("SECURITY_RATELIMIT_ENABLED", True)
        )
        self.burst = float(
            burst
            if burst is not None
            else int(os.getenv("SECURITY_RATELIMIT_BURST", "60"))
        )
        self.refill_per_sec = (
            refill_per_sec
            if refill_per_sec is not None
            else float(os.getenv("SECURITY_RATELIMIT_REFILL_PER_SEC", "1.0"))
        )
        paths_raw = (
            ",".join(paths)
            if paths is not None
            else os.getenv("SECURITY_RATELIMIT_PATHS", DEFAULT_RATELIMIT_PATHS)
        )
        self.paths = tuple(p.strip() for p in paths_raw.split(",") if p.strip())
        self._buckets: Dict[str, _Bucket] = {}

    def _match(self, path: str) -> bool:
        for prefix in self.paths:
            if path == prefix or path.startswith(prefix):
                return True
        return False

    @staticmethod
    def _h(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]

    def _identity(self, scope: Scope) -> str:
        headers = Headers(scope=scope)
        client = scope.get("client")
        client_host = client[0] if client else "unknown"

        # Presented API key (X-API-Key, or a Bearer API/JWT credential). Hashed
        # rather than DB-resolved because this runs BEFORE auth on the hot path.
        api_key = headers.get("x-api-key")
        if not api_key:
            auth = headers.get("authorization")
            if auth and auth.lower().startswith("bearer "):
                api_key = auth.split(" ", 1)[1].strip()

        # (1) Loopback delegation: a sub-chat POSTs from loopback with the service
        # key PLUS an X-Delegate-User naming the end-user; bucket per end-user so
        # concurrent delegations don't starve on one key. S8: only trust the
        # delegate header when a service key is ALSO presented — otherwise the
        # bucket key would be a fully attacker-controlled header on the loopback
        # path (anyone reaching loopback could spray/spoof identities).
        if client_host in ("127.0.0.1", "::1", "localhost"):
            delegate = headers.get("x-delegate-user")
            if delegate and api_key:
                return f"deleg:{self._h(delegate)}"

        # (2) Presented API key → its own bucket.
        if api_key:
            return f"api:{self._h(api_key)}"

        # (3)/(4) Browser + SSE identities. Fold the auth credential into the
        # bucket so cookie/ticket users each get their OWN bucket instead of all
        # sharing ip:<host>. HTTPConnection derives cookies/query from the scope
        # alone (no receive needed). C2: browser users authenticate via the
        # ``brigade_session`` cookie and SSE via ``?ticket=`` / the SSE ticket
        # cookie — none of which the pre-fix identity looked at, so they all fell
        # to a single shared ip bucket.
        conn = HTTPConnection(scope)
        session_cookie = conn.cookies.get(_SESSION_COOKIE)
        if session_cookie:
            return f"sess:{self._h(session_cookie)}"
        ticket = conn.query_params.get("ticket") or conn.cookies.get(_SSE_TICKET_COOKIE)
        if ticket:
            return f"ticket:{self._h(ticket)}"

        # (5) Fallback: client IP.
        return f"ip:{client_host}"

    def _check(self, key: str) -> Tuple[bool, float]:
        """Refill + try to consume one token. Returns ``(allowed, retry_after)``.

        Runs entirely synchronously (no ``await`` between read and write), so the
        read-modify-write is atomic under the single asyncio event loop — no lock
        is needed for per-process correctness.
        """
        now = time.monotonic()
        bucket = self._buckets.get(key)
        if bucket is None:
            if len(self._buckets) >= _PRUNE_THRESHOLD:
                self._prune(now)
            bucket = _Bucket(tokens=self.burst, updated=now)
            self._buckets[key] = bucket
        else:
            elapsed = now - bucket.updated
            if elapsed > 0:
                bucket.tokens = min(
                    self.burst, bucket.tokens + elapsed * self.refill_per_sec
                )
                bucket.updated = now

        if bucket.tokens >= 1.0:
            bucket.tokens -= 1.0
            return True, 0.0

        deficit = 1.0 - bucket.tokens
        retry_after = deficit / self.refill_per_sec if self.refill_per_sec > 0 else 1.0
        return False, retry_after

    def _prune(self, now: float) -> None:
        # Drop buckets that have fully refilled (idle) — they carry no state worth
        # keeping and would otherwise accumulate under key/IP churn.
        stale = [
            k
            for k, b in self._buckets.items()
            if b.tokens + (now - b.updated) * self.refill_per_sec >= self.burst
        ]
        for k in stale:
            self._buckets.pop(k, None)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # Skip non-HTTP, disabled, and CORS preflight (OPTIONS carries no auth and
        # must not consume a token) requests.
        if (
            scope["type"] != "http"
            or not self.enabled
            or scope.get("method") == "OPTIONS"
        ):
            await self.app(scope, receive, send)
            return
        if not self._match(scope.get("path", "")):
            await self.app(scope, receive, send)
            return

        allowed, retry_after = self._check(self._identity(scope))
        if not allowed:
            await self._reject(send, retry_after)
            return
        await self.app(scope, receive, send)

    @staticmethod
    async def _reject(send: Send, retry_after: float) -> None:
        retry = max(1, int(retry_after + 0.999))  # ceil, floor of 1s
        body = json.dumps({"detail": {"message": "Rate limit exceeded"}}).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                    (b"retry-after", str(retry).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
