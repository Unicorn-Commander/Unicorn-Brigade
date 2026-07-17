"""
BR-6.1 audit LOW-severity follow-ups — regression tests.

Covers the four fixes in this branch:
  1. X-Delegate-User rate-limit buckets are only honored when a VALID master
     service key is presented (both app.security.ratelimit and
     app.security.rate_limit).
  2. Ralph GET routes now require authentication (401 when unauthenticated).
  3. Slack webhook signature verification fails CLOSED in a production env when
     no signing secret is configured (dev still skips).
  4. Monitoring alert-webhook egress is governed by MONITORING_WEBHOOK_ALLOWLIST.

These tests are DB-free and dependency-light. To import the ralph / slack route
modules without triggering app/api/__init__.py's heavy eager imports (langgraph,
etc.), we pre-seed a lightweight ``app.api`` namespace package before importing
the submodules — submodule loading still resolves via ``__path__``.
"""

import os
import sys
import types

import pytest

# --- pre-seed app.api as a lightweight namespace package (skip heavy __init__) ---
import app as _app_pkg  # noqa: E402

if not isinstance(sys.modules.get("app.api"), types.ModuleType) or not hasattr(
    sys.modules.get("app.api"), "_lightweight_stub"
):
    _api_pkg = types.ModuleType("app.api")
    _api_pkg.__path__ = [os.path.join(os.path.dirname(_app_pkg.__file__), "api")]
    _api_pkg._lightweight_stub = True
    sys.modules["app.api"] = _api_pkg

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from starlette.requests import Request  # noqa: E402


def _http_scope(headers: dict, client_host: str = "127.0.0.1", query: bytes = b""):
    """Build a minimal ASGI HTTP scope with the given header dict."""
    raw = [(k.lower().encode("utf-8"), v.encode("utf-8")) for k, v in headers.items()]
    return {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/agents/x/chat",
        "headers": raw,
        "client": (client_host, 54321),
        "query_string": query,
        "scheme": "http",
        "server": ("testserver", 80),
    }


# =====================================================================
# Fix 1 — X-Delegate-User honored only with a VALID master service key
# =====================================================================

class TestDelegateKeyValidity:
    def test_helper_fails_closed_without_master_key(self, monkeypatch):
        from app.security.ratelimit import delegate_key_is_trusted

        monkeypatch.delenv("BRIGADE_ADMIN_KEY", raising=False)
        # No master configured: even an empty presented key must NOT be trusted
        # (guards against compare_digest('', '') == True).
        assert delegate_key_is_trusted("") is False
        assert delegate_key_is_trusted("anything") is False
        assert delegate_key_is_trusted(None) is False

    def test_helper_trusts_only_exact_master_key(self, monkeypatch):
        from app.security.ratelimit import delegate_key_is_trusted

        monkeypatch.setenv("BRIGADE_ADMIN_KEY", "master-secret-abc")
        assert delegate_key_is_trusted("master-secret-abc") is True
        assert delegate_key_is_trusted("master-secret-abd") is False
        assert delegate_key_is_trusted("") is False
        assert delegate_key_is_trusted(None) is False

    def test_asgi_limiter_ignores_delegate_without_valid_key(self, monkeypatch):
        from app.security.ratelimit import RateLimitMiddleware

        monkeypatch.setenv("BRIGADE_ADMIN_KEY", "master-secret-abc")
        mw = RateLimitMiddleware(None, enabled=True)

        # delegate header + WRONG key on loopback -> NOT a deleg bucket; falls
        # through to the presented-key bucket.
        ident = mw._identity(
            _http_scope({"X-Delegate-User": "victim", "X-API-Key": "wrong-key"})
        )
        assert not ident.startswith("deleg:")
        assert ident.startswith("api:")

        # delegate header + NO key on loopback -> falls all the way to IP bucket.
        ident_nokey = mw._identity(_http_scope({"X-Delegate-User": "victim"}))
        assert not ident_nokey.startswith("deleg:")
        assert ident_nokey.startswith("ip:")

        # delegate header + VALID master key -> per-end-user deleg bucket honored.
        ident_ok = mw._identity(
            _http_scope({"X-Delegate-User": "victim", "X-API-Key": "master-secret-abc"})
        )
        assert ident_ok.startswith("deleg:")

    def test_asgi_limiter_delegate_ignored_off_loopback(self, monkeypatch):
        from app.security.ratelimit import RateLimitMiddleware

        monkeypatch.setenv("BRIGADE_ADMIN_KEY", "master-secret-abc")
        mw = RateLimitMiddleware(None, enabled=True)
        # Even with the valid master key, a NON-loopback client cannot use the
        # delegate bucket (delegation is a loopback-only primitive).
        ident = mw._identity(
            _http_scope(
                {"X-Delegate-User": "victim", "X-API-Key": "master-secret-abc"},
                client_host="203.0.113.5",
            )
        )
        assert not ident.startswith("deleg:")
        assert ident.startswith("api:")

    def test_dependency_limiter_ignores_delegate_without_valid_key(self, monkeypatch):
        from app.security.rate_limit import _default_key_fn

        monkeypatch.setenv("BRIGADE_ADMIN_KEY", "master-secret-abc")

        def _req(headers, client_host="127.0.0.1"):
            return Request(_http_scope(headers, client_host=client_host))

        # WRONG key -> not a deleg bucket (falls to api bucket).
        k_wrong = _default_key_fn(_req({"X-Delegate-User": "v", "X-API-Key": "nope"}))
        assert not k_wrong.startswith("deleg:")
        assert k_wrong.startswith("api:")

        # No key -> ip bucket.
        k_none = _default_key_fn(_req({"X-Delegate-User": "v"}))
        assert k_none.startswith("ip:")

        # Valid master key -> deleg bucket.
        k_ok = _default_key_fn(
            _req({"X-Delegate-User": "v", "X-API-Key": "master-secret-abc"})
        )
        assert k_ok.startswith("deleg:")

    def test_dependency_limiter_fails_closed_without_master(self, monkeypatch):
        from app.security.rate_limit import _default_key_fn

        monkeypatch.delenv("BRIGADE_ADMIN_KEY", raising=False)
        req = Request(_http_scope({"X-Delegate-User": "v", "X-API-Key": ""}))
        key = _default_key_fn(req)
        assert not key.startswith("deleg:")


# =====================================================================
# Fix 2 — Ralph GET routes require authentication
# =====================================================================

class TestRalphGetAuth:
    @pytest.fixture()
    def ralph_app(self):
        from app.api.ralph_routes import router as ralph_router

        app = FastAPI()
        app.include_router(ralph_router)
        return app

    @pytest.mark.parametrize(
        "path",
        [
            "/api/v1/ralph/executions",
            "/api/v1/ralph/executions/does-not-exist",
            "/api/v1/ralph/executions/does-not-exist/result",
        ],
    )
    def test_get_routes_unauthenticated_return_401(self, ralph_app, path):
        from app.db.database import get_session

        async def _fake_session():
            # Never used on the unauthenticated path (auth resolves to None before
            # any DB access), but overriding it guarantees no real connection.
            yield None

        ralph_app.dependency_overrides[get_session] = _fake_session
        try:
            client = TestClient(ralph_app)
            resp = client.get(path)
            assert resp.status_code == 401, resp.text
        finally:
            ralph_app.dependency_overrides.clear()

    def test_get_executions_authenticated_returns_200(self, ralph_app):
        # With auth satisfied (stub user), the gated route works — proving the 401
        # above is the auth gate, not an unrelated error.
        from app.auth.middleware import get_current_user, AuthUser
        from app.auth.roles import UserRole

        ralph_app.dependency_overrides[get_current_user] = lambda: AuthUser(
            id="tester", role=UserRole.OPERATOR, auth_source="api_key"
        )
        try:
            client = TestClient(ralph_app)
            resp = client.get("/api/v1/ralph/executions")
            assert resp.status_code == 200, resp.text
            assert resp.json() == []
        finally:
            ralph_app.dependency_overrides.clear()


# =====================================================================
# Fix 3 — Slack webhook fails closed in prod when no signing secret
# =====================================================================

class _StubSlack:
    def __init__(self, signing_secret=None, valid=False):
        self.signing_secret = signing_secret
        self._valid = valid

    def verify_request(self, body, timestamp, signature):
        return self._valid


class TestSlackFailClosed:
    @pytest.fixture()
    def slack_app(self):
        from app.api.slack_routes import router as slack_router

        app = FastAPI()
        app.include_router(slack_router, prefix="/api/v1")
        return app

    @staticmethod
    def _force_env(monkeypatch, env_name):
        # resolve_environment() reads BRIGADE_ENV -> ENV -> ENVIRONMENT.
        monkeypatch.delenv("BRIGADE_ENV", raising=False)
        monkeypatch.delenv("ENV", raising=False)
        monkeypatch.setenv("ENVIRONMENT", env_name)

    def test_prod_no_secret_rejects_503(self, slack_app, monkeypatch):
        import app.api.slack_routes as slack_routes

        self._force_env(monkeypatch, "production")
        monkeypatch.setattr(
            slack_routes, "get_slack_client", lambda: _StubSlack(signing_secret=None)
        )
        client = TestClient(slack_app)
        resp = client.post(
            "/api/v1/slack/events",
            json={"type": "url_verification", "challenge": "xyz"},
        )
        assert resp.status_code == 503, resp.text

    def test_dev_no_secret_skips_verification(self, slack_app, monkeypatch):
        import app.api.slack_routes as slack_routes

        self._force_env(monkeypatch, "development")
        monkeypatch.setattr(
            slack_routes, "get_slack_client", lambda: _StubSlack(signing_secret=None)
        )
        client = TestClient(slack_app)
        resp = client.post(
            "/api/v1/slack/events",
            json={"type": "url_verification", "challenge": "xyz"},
        )
        # Dev skips verification and answers the URL-verification challenge.
        assert resp.status_code == 200, resp.text
        assert resp.json() == {"challenge": "xyz"}

    def test_secret_set_bad_signature_rejects_401(self, slack_app, monkeypatch):
        import app.api.slack_routes as slack_routes

        # Even in dev, a configured secret still fails closed on a bad signature.
        self._force_env(monkeypatch, "development")
        monkeypatch.setattr(
            slack_routes,
            "get_slack_client",
            lambda: _StubSlack(signing_secret="s3kr3t", valid=False),
        )
        client = TestClient(slack_app)
        resp = client.post(
            "/api/v1/slack/events",
            json={"type": "url_verification", "challenge": "xyz"},
        )
        assert resp.status_code == 401, resp.text


# =====================================================================
# Fix 4 — Monitoring alert-webhook egress allowlist
# =====================================================================

class TestMonitoringWebhookAllowlist:
    def test_permissive_by_default(self, monkeypatch):
        import app.agents.monitoring_agent as ma

        monkeypatch.delenv("MONITORING_WEBHOOK_ALLOWLIST", raising=False)
        allowed, reason = ma._webhook_egress_allowed("http://10.0.0.5:9000/hook")
        assert allowed is True
        assert reason == ""

    def test_allowlist_blocks_unlisted_host(self, monkeypatch):
        import app.agents.monitoring_agent as ma

        monkeypatch.setenv("MONITORING_WEBHOOK_ALLOWLIST", "alerts.internal,pagerduty.com")
        blocked, reason = ma._webhook_egress_allowed("https://evil.example.com/x")
        assert blocked is False
        assert "not in MONITORING_WEBHOOK_ALLOWLIST" in reason

    def test_allowlist_allows_listed_and_subdomains(self, monkeypatch):
        import app.agents.monitoring_agent as ma

        monkeypatch.setenv("MONITORING_WEBHOOK_ALLOWLIST", "alerts.internal,pagerduty.com")
        ok_exact, _ = ma._webhook_egress_allowed("http://alerts.internal/notify")
        ok_sub, _ = ma._webhook_egress_allowed("https://events.pagerduty.com/v2/enqueue")
        assert ok_exact is True
        assert ok_sub is True

    def test_allowlist_rejects_unparseable(self, monkeypatch):
        import app.agents.monitoring_agent as ma

        monkeypatch.setenv("MONITORING_WEBHOOK_ALLOWLIST", "alerts.internal")
        blocked, reason = ma._webhook_egress_allowed("not-a-url")
        assert blocked is False
        assert "could not parse a host" in reason
