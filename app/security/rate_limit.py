"""
Simple in-memory rate limiting utilities.

NOTE: This is per-process and resets on restart.
"""

import asyncio
import hashlib
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable, Deque, Dict, Optional

from fastapi import Depends, HTTPException, Request, status


@dataclass
class RateLimitConfig:
    name: str
    max_requests: int
    window_seconds: int


_lock = asyncio.Lock()
_requests: Dict[str, Deque[float]] = {}


def _default_key_fn(request: Request) -> str:
    api_key = request.headers.get("X-API-Key")
    if api_key:
        key_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]
        return f"api:{key_hash}"
    client = request.client.host if request.client else "unknown"
    return f"ip:{client}"


async def _check_rate_limit(
    request: Request,
    config: RateLimitConfig,
    key_fn: Optional[Callable[[Request], str]] = None,
) -> None:
    key = (key_fn or _default_key_fn)(request)
    bucket_key = f"{config.name}:{key}"
    now = time.monotonic()

    async with _lock:
        q = _requests.get(bucket_key)
        if q is None:
            q = deque()
            _requests[bucket_key] = q

        # Evict old entries
        while q and now - q[0] >= config.window_seconds:
            q.popleft()

        if len(q) >= config.max_requests:
            retry_after = max(1, int(config.window_seconds - (now - q[0])))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded for {config.name}",
                headers={"Retry-After": str(retry_after)},
            )

        q.append(now)


def rate_limit(
    name: str,
    max_requests: int,
    window_seconds: int,
    key_fn: Optional[Callable[[Request], str]] = None,
):
    """
    FastAPI dependency for rate limiting.
    """
    config = RateLimitConfig(name=name, max_requests=max_requests, window_seconds=window_seconds)

    async def _dependency(request: Request) -> None:
        await _check_rate_limit(request, config, key_fn=key_fn)

    return Depends(_dependency)
