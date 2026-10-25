"""
Audit-remediation tests: secret-default removal + SSRF (DNS-rebinding TOCTOU)
hardening across builtin_tools, advanced_tools, the a2a async callback, and the
LiveKit voice worker.

Kept dependency-light and offline: the SSRF/pin tests mock the resolver
(``socket.getaddrinfo``) and the httpx base transport so nothing touches the
network, while still proving the connection is PINNED to the validated IP with
Host + TLS SNI preserved.
"""

import pathlib
import socket

import httpx
import pytest

import app.llm.builtin_tools as builtin_tools
from app.llm.builtin_tools import (
    build_egress_guarded_transport,
    http_request_handler,
    validate_url_egress,
    web_search_handler,
)


def _repo_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (_repo_root() / rel).read_text()


def _fake_getaddrinfo_returning(ip: str):
    """Return a getaddrinfo stub that always resolves to ``ip`` (IPv4)."""

    def _fake(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (ip, port))]

    return _fake


# ───────────────── (a) web_search degrades cleanly without SERPER key ─────────
@pytest.mark.asyncio
async def test_web_search_clean_error_when_serper_key_empty(monkeypatch):
    monkeypatch.setattr(builtin_tools, "SERPER_API_KEY", "")
    # Must NOT raise, and must return a clean structured error (degraded result).
    result = await web_search_handler("anything", provider="serper")
    assert result["success"] is False
    assert result["results"] == []
    assert "SERPER_API_KEY" in result["error"]


def test_no_serper_key_literal_in_source():
    src = _read("app/llm/builtin_tools.py")
    assert "REMOVED" not in src
    assert 'os.getenv("SERPER_API_KEY", "")' in src


# ───────────────── (b) egress guard + connect path reject internal ────────────
def test_validate_url_egress_blocks_metadata_ip_literal():
    allowed, err = validate_url_egress("http://169.254.169.254/latest/meta-data/")
    assert allowed is False
    assert "169.254.169.254" in err


def test_validate_url_egress_blocks_host_resolving_to_loopback(monkeypatch):
    monkeypatch.setattr(
        builtin_tools.socket, "getaddrinfo", _fake_getaddrinfo_returning("127.0.0.1")
    )
    allowed, err = validate_url_egress("http://rebind.test/")
    assert allowed is False
    assert "non-public" in err


@pytest.mark.asyncio
async def test_http_request_blocked_when_host_resolves_to_loopback(monkeypatch):
    monkeypatch.setattr(
        builtin_tools.socket, "getaddrinfo", _fake_getaddrinfo_returning("127.0.0.1")
    )
    result = await http_request_handler("http://rebind.test/")
    assert result["success"] is False
    assert "SSRF guard" in result["error"]


def test_build_transport_blocks_internal_ip_literal():
    transport, reason = build_egress_guarded_transport("http://127.0.0.1:8100/")
    assert transport is None
    assert reason and "private/reserved" in reason


@pytest.mark.asyncio
async def test_pinned_connection_defeats_dns_rebinding(monkeypatch):
    """The guard resolves to a PUBLIC ip; the actual connection must go to THAT
    ip (pinned) with Host + TLS SNI preserved — so a resolver that rebinds to
    127.0.0.1 at connect time can never be reached."""
    public_ip = "93.184.216.34"
    monkeypatch.setattr(
        builtin_tools.socket, "getaddrinfo", _fake_getaddrinfo_returning(public_ip)
    )

    captured = {}

    async def fake_super(self, request):
        # This stands in for the real network connect: record where we'd connect.
        captured["connect_host"] = request.url.host
        captured["host_header"] = request.headers.get("host")
        captured["sni"] = request.extensions.get("sni_hostname")
        return httpx.Response(200, json={"ok": True}, request=request)

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", fake_super)

    result = await http_request_handler("https://rebind.test/path")
    assert result["success"] is True
    assert captured["connect_host"] == public_ip  # pinned, NOT re-resolved
    assert captured["host_header"] == "rebind.test"  # Host header preserved
    assert captured["sni"] == "rebind.test"  # TLS SNI + cert host preserved


# ───────────────── (c) a2a callback rejects internal callback_url ─────────────
@pytest.mark.asyncio
async def test_a2a_callback_rejects_internal_url():
    from app.protocols.a2a import A2AServer

    server = A2AServer.__new__(A2AServer)  # _post_callback needs no constructed state
    for bad in (
        "http://127.0.0.1:8100/cb",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.5/internal",
    ):
        sent = await server._post_callback(bad, {"x": 1}, None)
        assert sent is False, f"callback to {bad} should have been blocked"


@pytest.mark.asyncio
async def test_a2a_callback_pins_and_sends_for_public_url(monkeypatch):
    from app.protocols.a2a import A2AServer

    public_ip = "93.184.216.34"
    monkeypatch.setattr(
        builtin_tools.socket, "getaddrinfo", _fake_getaddrinfo_returning(public_ip)
    )
    captured = {}

    async def fake_super(self, request):
        captured["connect_host"] = request.url.host
        return httpx.Response(200, request=request)

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", fake_super)

    server = A2AServer.__new__(A2AServer)
    sent = await server._post_callback("http://good.test/cb", {"x": 1}, None)
    assert sent is True
    assert captured["connect_host"] == public_ip  # pinned to validated IP


# ───────────────── S6: LiveKit voice worker refuses dev creds in prod ─────────
def _clear_env(monkeypatch):
    for var in ("BRIGADE_ENV", "ENV", "ENVIRONMENT"):
        monkeypatch.delenv(var, raising=False)


def test_livekit_refuses_dev_creds_in_prod(monkeypatch):
    from app.security.bootstrap import InsecureConfigurationError
    from app.voice.livekit_agent import assert_livekit_creds_safe

    _clear_env(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(InsecureConfigurationError):
        assert_livekit_creds_safe("devkey", "REMOVED")


def test_livekit_refuses_empty_creds_in_prod(monkeypatch):
    from app.security.bootstrap import InsecureConfigurationError
    from app.voice.livekit_agent import assert_livekit_creds_safe

    _clear_env(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(InsecureConfigurationError):
        assert_livekit_creds_safe("", "")


def test_livekit_allows_dev_creds_in_development(monkeypatch):
    from app.voice.livekit_agent import assert_livekit_creds_safe

    _clear_env(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "development")
    assert_livekit_creds_safe("devkey", "REMOVED")  # no raise


def test_livekit_allows_real_creds_in_prod(monkeypatch):
    from app.voice.livekit_agent import assert_livekit_creds_safe

    _clear_env(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "production")
    # Real-looking, non-dev credentials must pass in prod.
    assert_livekit_creds_safe("APIabc123real", "a-long-real-livekit-secret-value")


# ───────────────── static: no hardcoded secret literals remain ────────────────
def test_crisis_litellm_key_default_removed():
    if not (pathlib.Path(__file__).resolve().parents[1] / "app/api/crisis_routes.py").exists():
        # The crisis feature is private to Magic Unicorn's deployment and absent
        # from the public build (app/private_features.py), so there is nothing to audit.
        pytest.skip("crisis feature not installed in this build")
    src = _read("app/api/crisis_routes.py")
    assert "REMOVED" not in src
    assert 'os.getenv("LITELLM_API_KEY", "")' in src


def test_livekit_cred_defaults_removed():
    src = _read("app/voice/livekit_agent.py")
    assert 'os.getenv("LIVEKIT_API_KEY", "")' in src
    assert 'os.getenv("LIVEKIT_API_SECRET", "")' in src
