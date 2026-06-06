"""Tests for feature flag resolution."""

import importlib
import os


def _reload_features():
    """Re-import features module so env changes take effect."""
    import app.config.features as features
    return importlib.reload(features)


def test_defaults_match_dogfood_posture(monkeypatch):
    """Unset env = current Brigade behavior (full agent suite)."""
    monkeypatch.delenv("BRIGADE_FEDERATION_ONLY", raising=False)
    monkeypatch.delenv("BRIGADE_INTERNAL_AGENTS_ENABLED", raising=False)
    f = _reload_features()
    assert f.FEDERATION_ONLY is False
    assert f.INTERNAL_AGENTS_ENABLED is True


def test_federation_only_disables_internal_agents(monkeypatch):
    """Setting FEDERATION_ONLY implies agents off — belt-and-suspender."""
    monkeypatch.setenv("BRIGADE_FEDERATION_ONLY", "true")
    monkeypatch.delenv("BRIGADE_INTERNAL_AGENTS_ENABLED", raising=False)
    f = _reload_features()
    assert f.FEDERATION_ONLY is True
    assert f.INTERNAL_AGENTS_ENABLED is False


def test_internal_agents_explicit_override(monkeypatch):
    """Operator can force agents on even in federation-only mode (unusual)."""
    monkeypatch.setenv("BRIGADE_FEDERATION_ONLY", "true")
    monkeypatch.setenv("BRIGADE_INTERNAL_AGENTS_ENABLED", "true")
    f = _reload_features()
    assert f.FEDERATION_ONLY is True
    assert f.INTERNAL_AGENTS_ENABLED is True


def test_bool_env_accepts_common_truthy_values(monkeypatch):
    for v in ["1", "true", "TRUE", "yes", "on", "True"]:
        monkeypatch.setenv("BRIGADE_FEDERATION_ONLY", v)
        f = _reload_features()
        assert f.FEDERATION_ONLY is True, f"value {v!r} should be truthy"


def test_bool_env_rejects_falsy_and_garbage(monkeypatch):
    for v in ["0", "false", "no", "off", "", "garbage"]:
        monkeypatch.setenv("BRIGADE_FEDERATION_ONLY", v)
        f = _reload_features()
        assert f.FEDERATION_ONLY is False, f"value {v!r} should be falsy"
