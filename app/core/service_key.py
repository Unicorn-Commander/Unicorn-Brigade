"""Validation and fail-closed handling for the Brigade service key."""

from __future__ import annotations

import hmac
import logging
import os

logger = logging.getLogger(__name__)

SERVICE_KEY_ENV = "BRIGADE_SERVICE_KEY"
MIN_SERVICE_KEY_LENGTH = 32

# Keep the existing public default in one shared place.  Do not add live
# credentials here: this tuple is only for literals that are already known to
# be placeholders/defaults.
KNOWN_BAD_SERVICE_KEYS = ("sk-brigade-service-key-2025",)

_weak_key_warnings: set[str] = set()


class ConfigError(RuntimeError):
    """Raised when a required runtime credential is absent or unsafe."""


def reset_weak_key_warnings() -> None:
    """Clear process-local weak-key warning state for test isolation."""
    _weak_key_warnings.clear()


def is_strong_service_key(value: str | None) -> bool:
    """Return whether ``value`` meets the service-key safety rule.

    Validation deliberately never logs or includes the candidate value in an
    exception.  Placeholder matching uses ``compare_digest`` as well as the
    request-time credential comparisons.
    """
    if not isinstance(value, str):
        return False
    candidate = value.strip()
    candidate_bytes = candidate.encode("utf-8")
    if any(
        hmac.compare_digest(candidate_bytes, known.encode("utf-8"))
        for known in KNOWN_BAD_SERVICE_KEYS
    ):
        return False
    return len(candidate) >= MIN_SERVICE_KEY_LENGTH


def require_service_key(purpose: str) -> str:
    """Return the configured service key or fail with a safe config error."""
    value = os.getenv(SERVICE_KEY_ENV, "")
    if not is_strong_service_key(value):
        raise ConfigError(
            f"{SERVICE_KEY_ENV} is required for {purpose}; it must be at least "
            f"{MIN_SERVICE_KEY_LENGTH} characters and must not be a known "
            "placeholder/default literal"
        )
    return value.strip()


def warn_if_weak_service_key(
    purpose: str,
    log: logging.Logger | None = None,
) -> bool:
    """Log one warning for a weak configured key and return whether it logged."""
    value = os.getenv(SERVICE_KEY_ENV, "")
    if not value or is_strong_service_key(value) or purpose in _weak_key_warnings:
        return False
    _weak_key_warnings.add(purpose)
    warning = (
        "%s disabled: %s must be at least %d characters and must not be a "
        "known placeholder/default literal; the configured value is not logged"
    )
    (log or logger).warning(warning, purpose, SERVICE_KEY_ENV, MIN_SERVICE_KEY_LENGTH)
    return True
