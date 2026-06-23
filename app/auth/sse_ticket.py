"""Short-lived, single-use tickets for authenticating browser EventSource streams.

The browser ``EventSource`` API cannot send custom request headers (no
``Authorization`` / ``X-API-Key``), so an already-authenticated client mints a
ticket via a normal POST and then opens the SSE stream with ``?ticket=<t>``.

Properties:
  - bound to the authenticated user captured at mint time (grants nothing more
    than that user already has),
  - single-use (consumed on first redemption),
  - expires after ``TTL_SECONDS`` (redeemed within a second or two of minting).

In-memory and per-process, which is correct here: the ticket is minted and
redeemed against the same node within the same page load. Nothing durable is
stored, and a lost ticket simply forces the client to mint another.
"""

import secrets
import time
from typing import Any, Dict, Optional, Tuple

# Long enough to cover a mint -> open round-trip plus a retry or two; short
# enough that a leaked ticket is useless almost immediately.
TTL_SECONDS = 60

# Hard upper bound on outstanding tickets — a final backstop against a mint
# flood within one TTL window (the per-user rate limit on the mint endpoint is
# the primary guard). Keeps the store provably bounded regardless of user count.
MAX_TICKETS = 10000

# ticket -> (user, expires_at_monotonic)
_tickets: Dict[str, Tuple[Any, float]] = {}


def _purge(now: float) -> None:
    """Drop expired tickets. Cheap; called on every mint."""
    if not _tickets:
        return
    expired = [t for t, (_u, exp) in _tickets.items() if exp <= now]
    for t in expired:
        _tickets.pop(t, None)


def mint_ticket(user: Any) -> str:
    """Create a single-use ticket bound to ``user``. Returns the ticket string."""
    now = time.monotonic()
    _purge(now)
    # Backstop eviction if a flood outpaces TTL purging. dicts preserve
    # insertion order, so the first key is the oldest.
    while len(_tickets) >= MAX_TICKETS:
        _tickets.pop(next(iter(_tickets)), None)
    ticket = secrets.token_urlsafe(32)
    _tickets[ticket] = (user, now + TTL_SECONDS)
    return ticket


def consume_ticket(ticket: Optional[str]) -> Optional[Any]:
    """Redeem a ticket, returning its bound user or ``None`` if invalid/expired.

    The ticket is removed on redemption, so it cannot be replayed.
    """
    if not ticket:
        return None
    entry = _tickets.pop(ticket, None)  # single-use: remove on read
    if entry is None:
        return None
    user, expires_at = entry
    if expires_at <= time.monotonic():
        return None
    return user
