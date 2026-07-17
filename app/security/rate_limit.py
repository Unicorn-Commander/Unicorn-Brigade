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

# Shared with the ASGI flood-limiter (app.security.ratelimit) so BOTH limiters
# make the SAME delegation-trust decision: honor X-Delegate-User only when a VALID
# master service key is presented, never on header presence alone.
from app.security.ratelimit import delegate_key_is_trusted


@dataclass
class RateLimitConfig:
    name: str
    max_requests: int
    window_seconds: int


_lock = asyncio.Lock()
_requests: Dict[str, Deque[float]] = {}


def _default_key_fn(request: Request) -> str:
    # Delegated sub-chats POST from loopback with the shared service key plus an
    # X-Delegate-User header naming the real end-user. Bucket on that user for
    # loopback requests only (external callers can't reach this path), so
    # concurrent delegations on behalf of different users don't all starve on a
    # single service-key bucket.
    #
    # S8: only honor X-Delegate-User when a VALID master service key is ALSO
    # presented (constant-time compare, same first check as the service-key auth
    # path — see delegate_key_is_trusted). Trusting the header on presence alone
    # let anyone reaching loopback spoof/evade another user's bucket by pairing a
    # junk key (or no key) with an arbitrary X-Delegate-User. When the key does
    # not validate we fall through to api-key / IP bucketing instead.
    client = request.client.host if request.client else "unknown"
    api_key = request.headers.get("X-API-Key")
    if client in ("127.0.0.1", "::1", "localhost"):
        delegate_user = request.headers.get("X-Delegate-User")
        if delegate_user and delegate_key_is_trusted(api_key):
            user_hash = hashlib.sha256(delegate_user.encode("utf-8")).hexdigest()[:16]
            return f"deleg:{user_hash}"
    if api_key:
        key_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]
        return f"api:{key_hash}"
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
