"""
Security response-headers middleware (BR-6 enterprise hardening).

A dependency-free, streaming-safe pure-ASGI middleware that stamps a conservative
set of security response headers onto EVERY HTTP response — including error
responses produced by inner middleware/handlers — without buffering the body, so
Server-Sent Events (``/api/v1/orchestration/events``) and other streaming
responses keep flowing. (This is why it is a raw ASGI middleware and not a
``BaseHTTPMiddleware`` subclass, which buffers and can stall SSE.)

Headers added (each via ``setdefault`` so a handler that sets its own wins):
  - ``X-Content-Type-Options: nosniff``
  - ``X-Frame-Options: DENY``
  - ``Referrer-Policy: strict-origin-when-cross-origin``
  - ``Content-Security-Policy`` — conservative JSON-API default (configurable)
  - ``Strict-Transport-Security`` — ONLY when the request arrived over TLS
    (``scheme == https`` or ``X-Forwarded-Proto: https`` behind a TLS-terminating
    proxy such as Traefik/Cloudflare).

Everything is env-configurable with safe production defaults, so existing
deployments need no env change.
"""

import os
from typing import Optional, Tuple

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


# Conservative default CSP for a JSON API host. The React app is served
# separately, so the API itself never needs to load scripts/styles/frames.
DEFAULT_CSP = (
    "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
)

# Interactive API docs (Swagger UI / ReDoc) and the OpenAPI schema are HTML/JS
# pages that legitimately load scripts + styles; a ``default-src 'none'`` CSP
# would break them. They are exempt from CSP by default (they still receive every
# OTHER security header). Override via ``SECURITY_CSP_EXEMPT_PATHS``.
DEFAULT_CSP_EXEMPT = "/docs,/redoc,/openapi.json"

DEFAULT_HSTS_MAX_AGE = 365 * 24 * 60 * 60  # 1 year


class SecurityHeadersMiddleware:
    """Stamp security headers on every response (pure ASGI, streaming-safe)."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        csp: Optional[str] = None,
        csp_exempt_paths: Optional[Tuple[str, ...]] = None,
        hsts_enabled: Optional[bool] = None,
        hsts_max_age: Optional[int] = None,
        hsts_include_subdomains: Optional[bool] = None,
        referrer_policy: str = "strict-origin-when-cross-origin",
        frame_options: str = "DENY",
    ) -> None:
        self.app = app
        self.csp = csp if csp is not None else os.getenv("SECURITY_CSP", DEFAULT_CSP)
        exempt_raw = (
            ",".join(csp_exempt_paths)
            if csp_exempt_paths is not None
            else os.getenv("SECURITY_CSP_EXEMPT_PATHS", DEFAULT_CSP_EXEMPT)
        )
        self.csp_exempt_paths = tuple(
            p.strip() for p in exempt_raw.split(",") if p.strip()
        )
        self.hsts_enabled = (
            hsts_enabled
            if hsts_enabled is not None
            else _bool_env("SECURITY_HSTS_ENABLED", True)
        )
        self.hsts_max_age = (
            hsts_max_age
            if hsts_max_age is not None
            else int(os.getenv("SECURITY_HSTS_MAX_AGE", str(DEFAULT_HSTS_MAX_AGE)))
        )
        self.hsts_include_subdomains = (
            hsts_include_subdomains
            if hsts_include_subdomains is not None
            else _bool_env("SECURITY_HSTS_INCLUDE_SUBDOMAINS", True)
        )
        self.referrer_policy = referrer_policy
        self.frame_options = frame_options

    def _is_https(self, scope: Scope) -> bool:
        if scope.get("scheme") == "https":
            return True
        # Behind a TLS-terminating proxy (Traefik/Cloudflare): trust the forwarded
        # proto header. Use the first hop if it is a comma-separated list.
        xfp = Headers(scope=scope).get("x-forwarded-proto")
        if xfp:
            return xfp.split(",")[0].strip().lower() == "https"
        return False

    def _csp_for_path(self, path: str) -> Optional[str]:
        if not self.csp:
            return None
        for prefix in self.csp_exempt_paths:
            if path == prefix or path.startswith(prefix):
                return None
        return self.csp

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        is_https = self._is_https(scope)
        csp_value = self._csp_for_path(scope.get("path", ""))

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.setdefault("X-Content-Type-Options", "nosniff")
                headers.setdefault("X-Frame-Options", self.frame_options)
                headers.setdefault("Referrer-Policy", self.referrer_policy)
                if csp_value:
                    headers.setdefault("Content-Security-Policy", csp_value)
                if self.hsts_enabled and is_https:
                    hsts = f"max-age={self.hsts_max_age}"
                    if self.hsts_include_subdomains:
                        hsts += "; includeSubDomains"
                    headers.setdefault("Strict-Transport-Security", hsts)
            await send(message)

        await self.app(scope, receive, send_wrapper)
