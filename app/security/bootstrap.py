"""
Fail-closed startup guards (BR-6 enterprise hardening).

The primary guard REFUSES to boot when ``AUTH_BYPASS=true`` in a production-like
environment. The auth middleware already *ignores* the bypass unless
``ENVIRONMENT==development`` (see ``app/auth/middleware.py``), but silently
ignoring a dangerous flag hides a misconfiguration. This turns it into a loud,
boot-time failure so a bad deploy is caught immediately — instead of an operator
running with the (false) belief that auth is bypassed, or a future refactor
quietly beginning to honor the flag in prod.

Env detection matches the rest of the app, which reads ``ENVIRONMENT`` (default
``"production"``) and treats ``"development"`` as the sole dev value. This module
additionally honors ``BRIGADE_ENV`` / ``ENV`` as the task specified, in that
precedence order.
"""

import logging
import os

logger = logging.getLogger(__name__)

# Environment names treated as NON-production (where AUTH_BYPASS is tolerable).
# Everything else — including the app's default of "production" when unset — is
# treated as production. Fail-safe: when in doubt, assume prod.
_NON_PROD_ENVS = {"development", "dev", "local", "test", "testing"}


def resolve_environment() -> str:
    """Resolve the deployment environment name.

    Honors ``BRIGADE_ENV``, then ``ENV``, then ``ENVIRONMENT`` (the var the rest
    of the app already reads — see ``app/auth/middleware.py`` /
    ``app/api/oidc_routes.py``), defaulting to ``"production"`` when none are set
    (matches the app default and is the fail-safe choice)."""
    for var in ("BRIGADE_ENV", "ENV", "ENVIRONMENT"):
        val = os.getenv(var)
        if val and val.strip():
            return val.strip().lower()
    return "production"


def is_production_env() -> bool:
    """True unless the resolved environment is an explicit non-production one."""
    return resolve_environment() not in _NON_PROD_ENVS


def auth_bypass_requested() -> bool:
    """True when ``AUTH_BYPASS`` is set truthy."""
    return os.getenv("AUTH_BYPASS", "false").strip().lower() == "true"


class InsecureConfigurationError(RuntimeError):
    """Raised to fail-closed on a dangerous production misconfiguration."""


def assert_auth_bypass_safe() -> None:
    """Refuse to boot if ``AUTH_BYPASS=true`` in a production-like environment.

    Raises :class:`InsecureConfigurationError` (a ``RuntimeError``) after logging
    LOUDLY. Safe to call from the startup path: in dev/test, or when
    ``AUTH_BYPASS`` is unset, it is effectively a no-op (a non-prod bypass still
    emits a loud warning)."""
    if auth_bypass_requested() and is_production_env():
        env = resolve_environment()
        banner = (
            "FATAL SECURITY MISCONFIGURATION: AUTH_BYPASS=true in a production-like "
            f"environment (resolved environment='{env}'). Authentication bypass is "
            "DEVELOPMENT-ONLY and must NEVER be enabled outside development. "
            "Refusing to boot. Unset AUTH_BYPASS (or set the environment to "
            "'development' only on a non-production host) and redeploy."
        )
        # Log loudly on both critical and error channels so it surfaces
        # regardless of the configured level/handler.
        logger.critical("❌❌❌ %s", banner)
        logger.error("❌❌❌ %s", banner)
        raise InsecureConfigurationError(banner)

    if auth_bypass_requested():
        # Non-production but the flag is on — permitted, yet still worth a loud
        # warning so it is never mistaken for a safe default.
        logger.warning(
            "⚠️ AUTH_BYPASS=true (environment='%s' is non-production). "
            "Authentication is BYPASSED — never use this posture in production.",
            resolve_environment(),
        )
