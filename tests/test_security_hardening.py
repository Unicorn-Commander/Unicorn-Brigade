"""
BR-6 enterprise security-hardening tests.

The full ``app.main`` import pulls heavy optional deps (langgraph, apscheduler,
...) that aren't installed in every dev/CI env, so — per the BR-6 brief — these
tests mount the middleware in ISOLATION on a tiny throwaway Starlette app. That
still proves the middleware behavior (security headers present, 413 on oversized
body, 429 after the configured burst) independent of the rest of Brigade.

A final static test asserts the three middlewares + the fail-closed guard are
actually wired into ``app/main.py`` (read as source, so it needs no heavy deps).
"""

import pathlib

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.security.headers import SecurityHeadersMiddleware
from app.security.limits import RequestSizeLimitMiddleware
from app.security.ratelimit import RateLimitMiddleware


def _echo(request):  # noqa: ANN001 - starlette handler
    return JSONResponse({"ok": True})


def _build_app(*, size=None, rate=None, headers=True, headers_kw=None):
    """Tiny Starlette app with the requested security middleware.

    Middleware is added in the SAME order as app/main.py — RequestSizeLimit,
    then RateLimit, then SecurityHeaders LAST — so SecurityHeaders wraps
    outermost and stamps headers on 413/429 rejections too.
    """
    routes = [
        Route("/api/v1/agents/x/chat", _echo, methods=["POST", "GET"]),
        Route("/api/v1/health", _echo, methods=["GET"]),
        Route("/api/v1/documents/process", _echo, methods=["POST"]),
        Route("/docs", _echo, methods=["GET"]),
    ]
    app = Starlette(routes=routes)
    if size is not None:
        app.add_middleware(RequestSizeLimitMiddleware, **size)
    if rate is not None:
        app.add_middleware(RateLimitMiddleware, **rate)
    if headers:
        app.add_middleware(SecurityHeadersMiddleware, **(headers_kw or {}))
    return app


# ─────────────────────────── 1. security headers ───────────────────────────
def test_security_headers_present_on_normal_response():
    client = TestClient(_build_app())
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "content-security-policy" in r.headers
    assert "default-src 'none'" in r.headers["content-security-policy"]


def test_hsts_absent_on_http_present_on_https():
    app = _build_app()
    # Plain http → no HSTS (only sent behind TLS).
    r = TestClient(app).get("/api/v1/health")
    assert "strict-transport-security" not in {k.lower() for k in r.headers}
    # https base_url → TestClient sets scope scheme=https → HSTS present.
    r2 = TestClient(app, base_url="https://testserver").get("/api/v1/health")
    assert "strict-transport-security" in r2.headers
    assert "max-age=" in r2.headers["strict-transport-security"]


def test_hsts_present_behind_tls_terminating_proxy_header():
    # Traefik/Cloudflare terminate TLS and forward X-Forwarded-Proto: https.
    r = TestClient(_build_app()).get(
        "/api/v1/health", headers={"X-Forwarded-Proto": "https"}
    )
    assert "strict-transport-security" in r.headers


def test_csp_exempt_for_interactive_docs():
    r = TestClient(_build_app()).get("/docs")
    # Docs are CSP-exempt (Swagger UI needs scripts) but still get other headers.
    assert "content-security-policy" not in {k.lower() for k in r.headers}
    assert r.headers["x-content-type-options"] == "nosniff"


def test_csp_configurable():
    app = _build_app(headers_kw={"csp": "default-src 'self'"})
    r = TestClient(app).get("/api/v1/health")
    assert r.headers["content-security-policy"] == "default-src 'self'"


# ─────────────────────────── 2. body-size limit → 413 ──────────────────────
def test_oversized_body_rejected_413():
    app = _build_app(size={"max_body_bytes": 1024})  # 1 KB cap
    r = TestClient(app).post("/api/v1/agents/x/chat", content=b"x" * 4096)
    assert r.status_code == 413
    # 413 still carries security headers (SecurityHeaders wraps outermost).
    assert r.headers["x-content-type-options"] == "nosniff"


def test_small_body_allowed():
    app = _build_app(size={"max_body_bytes": 1024})
    r = TestClient(app).post("/api/v1/agents/x/chat", content=b"x" * 100)
    assert r.status_code == 200


def test_upload_path_relaxed_to_higher_cap():
    app = _build_app(
        size={
            "max_body_bytes": 1024,
            "max_upload_bytes": 1_000_000,
            "upload_paths": ("/api/v1/documents",),
        }
    )
    # 4 KB exceeds the 1 KB base cap but is under the 1 MB upload cap → allowed.
    r = TestClient(app).post("/api/v1/documents/process", content=b"x" * 4096)
    assert r.status_code == 200
    # Same size on a non-upload route → rejected.
    r2 = TestClient(app).post("/api/v1/agents/x/chat", content=b"x" * 4096)
    assert r2.status_code == 413


# ─────────────────────────── 3. rate limit → 429 ───────────────────────────
def test_rate_limit_429_after_burst():
    app = _build_app(
        rate={"burst": 3, "refill_per_sec": 0.0, "paths": ("/api/v1/agents",)}
    )
    client = TestClient(app)
    codes = [
        client.post("/api/v1/agents/x/chat", json={}).status_code for _ in range(4)
    ]
    assert codes[:3] == [200, 200, 200]
    assert codes[3] == 429


def test_rate_limit_429_has_retry_after_and_security_headers():
    app = _build_app(
        rate={"burst": 1, "refill_per_sec": 0.0, "paths": ("/api/v1/agents",)}
    )
    client = TestClient(app)
    client.post("/api/v1/agents/x/chat", json={})
    r = client.post("/api/v1/agents/x/chat", json={})
    assert r.status_code == 429
    assert "retry-after" in r.headers
    assert int(r.headers["retry-after"]) >= 1
    # Outer SecurityHeaders still applied to the 429.
    assert r.headers["x-content-type-options"] == "nosniff"


def test_rate_limit_excludes_unprotected_paths():
    app = _build_app(
        rate={"burst": 1, "refill_per_sec": 0.0, "paths": ("/api/v1/agents",)}
    )
    client = TestClient(app)
    # /health is not a protected prefix → never limited.
    codes = [client.get("/api/v1/health").status_code for _ in range(5)]
    assert codes == [200] * 5


def test_rate_limit_is_per_identity():
    app = _build_app(
        rate={"burst": 1, "refill_per_sec": 0.0, "paths": ("/api/v1/agents",)}
    )
    client = TestClient(app)
    a1 = client.post("/api/v1/agents/x/chat", json={}, headers={"X-API-Key": "key-A"})
    a2 = client.post("/api/v1/agents/x/chat", json={}, headers={"X-API-Key": "key-A"})
    b1 = client.post("/api/v1/agents/x/chat", json={}, headers={"X-API-Key": "key-B"})
    assert a1.status_code == 200
    assert a2.status_code == 429  # key-A bucket exhausted
    assert b1.status_code == 200  # key-B has an independent bucket


def test_rate_limit_refills_over_time():
    # burst=1, refill 1000/s → after consuming the token a tiny wait refills it.
    app = _build_app(
        rate={"burst": 1, "refill_per_sec": 1000.0, "paths": ("/api/v1/agents",)}
    )
    client = TestClient(app)
    assert client.post("/api/v1/agents/x/chat", json={}).status_code == 200
    import time

    time.sleep(0.02)  # 20ms * 1000/s = 20 tokens refilled
    assert client.post("/api/v1/agents/x/chat", json={}).status_code == 200


def test_rate_limit_can_be_disabled():
    app = _build_app(
        rate={"enabled": False, "burst": 1, "paths": ("/api/v1/agents",)}
    )
    client = TestClient(app)
    codes = [
        client.post("/api/v1/agents/x/chat", json={}).status_code for _ in range(5)
    ]
    assert codes == [200] * 5


# ─────────────────────── 4. fail-closed AUTH_BYPASS guard ───────────────────
def _clear_env(monkeypatch):
    for var in ("AUTH_BYPASS", "BRIGADE_ENV", "ENV", "ENVIRONMENT"):
        monkeypatch.delenv(var, raising=False)


def test_auth_bypass_refuses_boot_in_production(monkeypatch):
    from app.security import bootstrap

    _clear_env(monkeypatch)
    monkeypatch.setenv("AUTH_BYPASS", "true")
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(bootstrap.InsecureConfigurationError):
        bootstrap.assert_auth_bypass_safe()


def test_auth_bypass_refuses_boot_when_env_unset(monkeypatch):
    # No env var set → resolves to "production" (fail-safe) → refuses to boot.
    from app.security import bootstrap

    _clear_env(monkeypatch)
    monkeypatch.setenv("AUTH_BYPASS", "true")
    with pytest.raises(bootstrap.InsecureConfigurationError):
        bootstrap.assert_auth_bypass_safe()


def test_auth_bypass_allowed_in_development(monkeypatch):
    from app.security import bootstrap

    _clear_env(monkeypatch)
    monkeypatch.setenv("AUTH_BYPASS", "true")
    monkeypatch.setenv("ENVIRONMENT", "development")
    bootstrap.assert_auth_bypass_safe()  # no raise


def test_brigade_env_takes_precedence(monkeypatch):
    # BRIGADE_ENV=production overrides ENVIRONMENT=development → refuses.
    from app.security import bootstrap

    _clear_env(monkeypatch)
    monkeypatch.setenv("AUTH_BYPASS", "true")
    monkeypatch.setenv("BRIGADE_ENV", "production")
    monkeypatch.setenv("ENVIRONMENT", "development")
    with pytest.raises(bootstrap.InsecureConfigurationError):
        bootstrap.assert_auth_bypass_safe()


def test_no_bypass_is_always_safe(monkeypatch):
    from app.security import bootstrap

    _clear_env(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "production")  # prod but no bypass
    bootstrap.assert_auth_bypass_safe()  # no raise


# ─────────────────────── 5. main.py wiring (static) ─────────────────────────
def test_main_wires_security_hardening_block():
    """Prove the middleware + guard are registered in app/main.py without
    importing it (the full import needs heavy optional deps)."""
    main_src = (
        pathlib.Path(__file__).resolve().parents[1] / "app" / "main.py"
    ).read_text()
    assert "add_middleware(SecurityHeadersMiddleware)" in main_src
    assert "add_middleware(RateLimitMiddleware)" in main_src
    assert "add_middleware(RequestSizeLimitMiddleware)" in main_src
    assert "assert_auth_bypass_safe()" in main_src
