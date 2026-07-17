"""
Request body-size limit middleware (BR-6 enterprise hardening).

A dependency-free pure-ASGI middleware that rejects requests whose declared
``Content-Length`` exceeds a configurable cap with ``413 Request Entity Too
Large`` BEFORE the body is read or the handler runs.

Known large-upload routes (voice audio test upload, document/medical file
upload, bulk agent import) are relaxed to a higher cap via a path allowlist, so
the tight default cap protects the JSON API surface without breaking uploads.

Scope of enforcement: this middleware enforces the *declared* ``Content-Length``
header — a cheap, allocation-free first line of defense that blocks the common
oversized-payload case up front. The per-route
``app.security.request_limits.max_body_size`` dependencies still read + measure
the ACTUAL body on the sensitive exec routes, so a request that lies about (or
omits) ``Content-Length`` remains bounded there.
"""

import json
import os
from typing import Optional, Tuple

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

DEFAULT_MAX_BODY_BYTES = 10 * 1024 * 1024  # 10 MB — JSON API default
DEFAULT_MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB — allowlisted uploads

# Path prefixes for routes that legitimately accept large multipart/binary bodies.
DEFAULT_UPLOAD_PATHS = ",".join(
    [
        "/api/v1/voice/test",  # STT/TTS audio upload (voice test endpoints)
        "/api/v1/documents",  # document process / extract / analyze
        "/api/v1/medical/analyze-image",  # medical image upload
        "/api/v1/agents/import",  # bulk agent JSON import
    ]
)


class RequestSizeLimitMiddleware:
    """Reject over-cap requests by ``Content-Length`` (pure ASGI)."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        max_body_bytes: Optional[int] = None,
        max_upload_bytes: Optional[int] = None,
        upload_paths: Optional[Tuple[str, ...]] = None,
    ) -> None:
        self.app = app
        self.max_body_bytes = (
            max_body_bytes
            if max_body_bytes is not None
            else int(os.getenv("SECURITY_MAX_BODY_BYTES", str(DEFAULT_MAX_BODY_BYTES)))
        )
        self.max_upload_bytes = (
            max_upload_bytes
            if max_upload_bytes is not None
            else int(
                os.getenv("SECURITY_MAX_UPLOAD_BYTES", str(DEFAULT_MAX_UPLOAD_BYTES))
            )
        )
        upload_raw = (
            ",".join(upload_paths)
            if upload_paths is not None
            else os.getenv("SECURITY_UPLOAD_PATHS", DEFAULT_UPLOAD_PATHS)
        )
        self.upload_paths = tuple(p.strip() for p in upload_raw.split(",") if p.strip())

    def _limit_for_path(self, path: str) -> int:
        for prefix in self.upload_paths:
            if path == prefix or path.startswith(prefix):
                return self.max_upload_bytes
        return self.max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        content_length = Headers(scope=scope).get("content-length")
        if content_length is not None:
            try:
                declared = int(content_length)
            except (TypeError, ValueError):
                declared = None
            if declared is not None:
                limit = self._limit_for_path(scope.get("path", ""))
                if declared > limit:
                    await self._reject(send, limit)
                    return

        await self.app(scope, receive, send)

    @staticmethod
    async def _reject(send: Send, limit: int) -> None:
        body = json.dumps(
            {"detail": {"message": f"Request body too large (max {limit} bytes)"}}
        ).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
