"""Test that voice provider package exports resolve correctly.

This test verifies the fix for the ImportError on GET /api/v1/voice/health:
the top-level ``app.voice.providers`` package must export
``VoiceProviderRegistry``, ``list_available_providers``, ``get_stt_provider``,
and ``register_builtin_providers`` so that ``voice_routes.py`` and
``voice_settings_routes.py`` can import them without importing from submodules.

On the base branch (before the fix) this test fails with ImportError.
After the fix it passes.
"""

import subprocess
import sys


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


def test_health_http_without_optional_provider_libraries():
    """A fresh process must serve health with optional STT/TTS SDKs absent."""
    code = """
import sys
for name in ('faster_whisper', 'pywhispercpp', 'mlx', 'mlx_whisper',
             'kokoro', 'chatterbox', 'cosyvoice', 'onnxruntime'):
    sys.modules[name] = None
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.voice.providers import VoiceProviderRegistry, list_available_providers
from app.api.voice_routes import router
assert isinstance(VoiceProviderRegistry.list_stt_providers(), list)
assert isinstance(VoiceProviderRegistry.list_tts_providers(), list)
assert list_available_providers() == []
app = FastAPI()
app.include_router(router, prefix='/api/v1')
with TestClient(app) as client:
    response = client.get('/api/v1/voice/health')
    assert response.status_code == 200, response.status_code
    data = response.json()
    assert data['self_hosted_providers']['stt']['available'] == []
    assert isinstance(data['self_hosted_providers']['tts']['registered'], list)
print('voice-health-http-200-optional-sdks-absent')
"""
    result = subprocess.run([sys.executable, "-c", code], capture_output=True,
                            text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert "voice-health-http-200-optional-sdks-absent" in result.stdout
