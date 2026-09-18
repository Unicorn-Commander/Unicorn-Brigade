"""Test that voice provider package exports resolve correctly.

This test verifies the fix for the ImportError on GET /api/v1/voice/health:
the top-level ``app.voice.providers`` package must export
``VoiceProviderRegistry``, ``list_available_providers``, ``get_stt_provider``,
and ``register_builtin_providers`` so that ``voice_routes.py`` and
``voice_settings_routes.py`` can import them without importing from submodules.

On the base branch (before the fix) this test fails with ImportError.
After the fix it passes.
"""

import pytest


def test_import_voice_provider_registry():
    """VoiceProviderRegistry must be importable from the top-level package."""
    from app.voice.providers import VoiceProviderRegistry
    assert VoiceProviderRegistry is not None


def test_import_list_available_providers():
    """list_available_providers must be importable from the top-level package."""
    from app.voice.providers import list_available_providers
    assert callable(list_available_providers)


def test_import_register_builtin_providers():
    """register_builtin_providers must be importable from the top-level package."""
    from app.voice.providers import register_builtin_providers
    assert callable(register_builtin_providers)


def test_import_get_stt_provider():
    """get_stt_provider must be importable from the top-level package."""
    from app.voice.providers import get_stt_provider
    assert callable(get_stt_provider)


def test_import_get_tts_provider():
    """get_tts_provider must remain importable from the top-level package."""
    from app.voice.providers import get_tts_provider
    assert callable(get_tts_provider)


def test_voice_provider_registry_class_methods():
    """VoiceProviderRegistry class methods must be accessible."""
    from app.voice.providers import VoiceProviderRegistry
    assert hasattr(VoiceProviderRegistry, "list_stt_providers")
    assert hasattr(VoiceProviderRegistry, "list_tts_providers")
    assert hasattr(VoiceProviderRegistry, "register_stt")
    assert hasattr(VoiceProviderRegistry, "register_tts")


def test_list_available_providers_callable():
    """list_available_providers() must return a list when called."""
    from app.voice.providers import list_available_providers
    result = list_available_providers()
    assert isinstance(result, list)


def test_voice_routes_import():
    """Simulate the import that voice_routes.py performs at health check."""
    from app.voice.providers import VoiceProviderRegistry, list_available_providers
    assert VoiceProviderRegistry is not None
    assert callable(list_available_providers)
