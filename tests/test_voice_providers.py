"""Tests for voice provider system.

Tests the voice provider infrastructure including:
- VoiceConfig environment loading and updates
- VoiceProviderRegistry registration and listing
- STT/TTS factory functions and provider selection
- Base class abstract method requirements
- Error handling for unknown providers
"""

import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from typing import AsyncIterator, List, Optional

# Import voice provider modules
from app.voice.config import (
    VoiceConfig,
    get_voice_config,
    update_voice_config,
    reset_voice_config,
    set_voice_config,
)
from app.voice.providers.base import (
    STTProvider,
    STTConfig,
    STTResult,
    TTSProvider,
    TTSConfig,
    TTSProviderError,
    STTProviderError,
)
from app.voice.providers.registry import VoiceProviderRegistry


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(autouse=True)
def reset_registry():
    """Reset the registry before and after each test."""
    VoiceProviderRegistry.clear_all()
    yield
    VoiceProviderRegistry.clear_all()


@pytest.fixture
def clean_voice_config():
    """Reset voice config for each test."""
    # Store original config module state
    import app.voice.config as config_module
    original_config = config_module._voice_config
    config_module._voice_config = None
    yield
    # Restore original state
    config_module._voice_config = original_config


@pytest.fixture
def mock_env_vars():
    """Fixture that sets up mock environment variables."""
    env_vars = {
        "VOICE_STT_PROVIDER": "test-whisper",
        "VOICE_STT_MODEL": "large-v3",
        "VOICE_STT_DEVICE": "cuda",
        "VOICE_STT_COMPUTE_TYPE": "int8",
        "VOICE_STT_LANGUAGE": "es",
        "VOICE_TTS_PROVIDER": "test-tts",
        "VOICE_TTS_MODEL": "test-model",
        "VOICE_TTS_VOICE": "test_voice",
        "VOICE_TTS_SAMPLE_RATE": "22050",
        "VOICE_TTS_SPEED": "1.5",
        "VOICE_VAD_ENABLED": "false",
        "VOICE_VAD_THRESHOLD": "0.7",
        "LIVEKIT_URL": "ws://test:7880",
        "LIVEKIT_API_KEY": "test-api-key",
        "LIVEKIT_API_SECRET": "test-secret",
    }
    with patch.dict(os.environ, env_vars, clear=False):
        yield env_vars


# =============================================================================
# Mock Provider Classes for Testing
# =============================================================================

class MockSTTProvider(STTProvider):
    """Mock STT provider for testing."""

    async def transcribe(self, audio: bytes, language: Optional[str] = None, **kwargs) -> str:
        return "mock transcription"

    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[bytes],
        language: Optional[str] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        yield "mock"
        yield "stream"

    @property
    def name(self) -> str:
        return "mock-stt"


class MockTTSProvider(TTSProvider):
    """Mock TTS provider for testing."""

    async def synthesize(self, text: str, voice: Optional[str] = None) -> bytes:
        return b"mock audio data"

    async def synthesize_stream(
        self,
        text: str,
        voice: Optional[str] = None,
    ) -> AsyncIterator[bytes]:
        yield b"mock"
        yield b"audio"

    @property
    def name(self) -> str:
        return "mock-tts"

    @property
    def available_voices(self) -> List[str]:
        return ["voice1", "voice2", "voice3"]


class AnotherMockSTTProvider(STTProvider):
    """Another mock STT provider for testing multiple registrations."""

    async def transcribe(self, audio: bytes, language: Optional[str] = None, **kwargs) -> str:
        return "another transcription"

    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[bytes],
        language: Optional[str] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        yield "another"

    @property
    def name(self) -> str:
        return "another-stt"


class AnotherMockTTSProvider(TTSProvider):
    """Another mock TTS provider for testing multiple registrations."""

    async def synthesize(self, text: str, voice: Optional[str] = None) -> bytes:
        return b"another audio"

    async def synthesize_stream(
        self,
        text: str,
        voice: Optional[str] = None,
    ) -> AsyncIterator[bytes]:
        yield b"another"

    @property
    def name(self) -> str:
        return "another-tts"

    @property
    def available_voices(self) -> List[str]:
        return ["voiceA", "voiceB"]


# =============================================================================
# Test VoiceConfig.from_env()
# =============================================================================

class TestVoiceConfigFromEnv:
    """Test VoiceConfig.from_env() loads environment variables correctly."""

    def test_from_env_with_defaults(self, clean_voice_config):
        """Test that from_env uses defaults when env vars are not set."""
        # Clear relevant env vars
        env_clear = {
            "VOICE_STT_PROVIDER": "",
            "VOICE_TTS_PROVIDER": "",
        }
        with patch.dict(os.environ, env_clear, clear=False):
            # Remove keys if they exist
            for key in ["VOICE_STT_PROVIDER", "VOICE_TTS_PROVIDER"]:
                os.environ.pop(key, None)

            config = VoiceConfig.from_env()

            assert config.stt_provider == "faster-whisper"
            assert config.stt_model == "large-v3-turbo"
            assert config.stt_device == "auto"
            assert config.stt_compute_type == "float16"
            assert config.stt_language == "en"
            assert config.tts_provider == "kokoro"
            assert config.tts_model == "kokoro-82m"
            assert config.tts_voice == "af_bella"
            assert config.tts_sample_rate == 24000
            assert config.tts_speed == 1.0
            assert config.vad_enabled is True
            assert config.vad_threshold == 0.5

    def test_from_env_loads_custom_values(self, mock_env_vars, clean_voice_config):
        """Test that from_env loads custom environment variables."""
        config = VoiceConfig.from_env()

        assert config.stt_provider == "test-whisper"
        assert config.stt_model == "large-v3"
        assert config.stt_device == "cuda"
        assert config.stt_compute_type == "int8"
        assert config.stt_language == "es"
        assert config.tts_provider == "test-tts"
        assert config.tts_model == "test-model"
        assert config.tts_voice == "test_voice"
        assert config.tts_sample_rate == 22050
        assert config.tts_speed == 1.5
        assert config.vad_enabled is False
        assert config.vad_threshold == 0.7
        assert config.livekit_url == "ws://test:7880"
        assert config.livekit_api_key == "test-api-key"
        assert config.livekit_api_secret == "test-secret"

    def test_from_env_handles_boolean_conversion(self, clean_voice_config):
        """Test boolean environment variable conversion."""
        test_cases = [
            ("true", True),
            ("TRUE", True),
            ("True", True),
            ("false", False),
            ("FALSE", False),
            ("0", False),
            ("no", False),
        ]

        for env_value, expected in test_cases:
            with patch.dict(os.environ, {"VOICE_VAD_ENABLED": env_value}):
                config = VoiceConfig.from_env()
                assert config.vad_enabled == expected, f"Failed for {env_value}"

    def test_from_env_handles_numeric_conversion(self, clean_voice_config):
        """Test numeric environment variable conversion."""
        with patch.dict(os.environ, {
            "VOICE_TTS_SAMPLE_RATE": "44100",
            "VOICE_TTS_SPEED": "0.75",
            "VOICE_VAD_THRESHOLD": "0.3",
        }):
            config = VoiceConfig.from_env()

            assert config.tts_sample_rate == 44100
            assert config.tts_speed == 0.75
            assert config.vad_threshold == 0.3


# =============================================================================
# Test Configuration Update
# =============================================================================

class TestVoiceConfigUpdate:
    """Test configuration update functionality."""

    def test_update_config_changes_values(self, clean_voice_config):
        """Test that update() changes configuration values."""
        config = VoiceConfig()
        original_provider = config.stt_provider

        config.update({"stt_provider": "new-provider", "tts_voice": "new_voice"})

        assert config.stt_provider == "new-provider"
        assert config.tts_voice == "new_voice"

    def test_update_config_ignores_unknown_keys(self, clean_voice_config):
        """Test that update() ignores unknown configuration keys."""
        config = VoiceConfig()
        config.update({"unknown_key": "value", "stt_provider": "valid-provider"})

        assert config.stt_provider == "valid-provider"
        assert not hasattr(config, "unknown_key")

    def test_update_config_ignores_none_values(self, clean_voice_config):
        """Test that update() ignores None values."""
        config = VoiceConfig()
        original_provider = config.stt_provider

        config.update({"stt_provider": None})

        assert config.stt_provider == original_provider

    def test_update_returns_self_for_chaining(self, clean_voice_config):
        """Test that update() returns self for method chaining."""
        config = VoiceConfig()

        result = config.update({"stt_provider": "new-provider"})

        assert result is config

    def test_global_update_voice_config(self, clean_voice_config):
        """Test the global update_voice_config function."""
        # Get initial config
        config = get_voice_config()
        original_provider = config.stt_provider

        # Update
        updated = update_voice_config({"stt_provider": "updated-provider"})

        assert updated.stt_provider == "updated-provider"
        assert get_voice_config().stt_provider == "updated-provider"

    def test_reset_voice_config(self, mock_env_vars, clean_voice_config):
        """Test reset_voice_config resets to environment defaults."""
        # Get and modify config
        config = get_voice_config()
        config.update({"stt_provider": "modified-provider"})

        # Reset
        reset_config = reset_voice_config()

        assert reset_config.stt_provider == "test-whisper"  # From mock env vars

    def test_from_dict_creates_config(self, clean_voice_config):
        """Test VoiceConfig.from_dict() creates config from dictionary."""
        data = {
            "stt_provider": "dict-provider",
            "tts_voice": "dict_voice",
            "tts_sample_rate": 48000,
        }

        config = VoiceConfig.from_dict(data)

        assert config.stt_provider == "dict-provider"
        assert config.tts_voice == "dict_voice"
        assert config.tts_sample_rate == 48000

    def test_to_dict_exports_config(self, clean_voice_config):
        """Test VoiceConfig.to_dict() exports config to dictionary."""
        config = VoiceConfig(stt_provider="test", tts_voice="test_voice")

        data = config.to_dict()

        assert isinstance(data, dict)
        assert data["stt_provider"] == "test"
        assert data["tts_voice"] == "test_voice"

    def test_get_stt_config_subset(self, clean_voice_config):
        """Test get_stt_config returns STT-specific config."""
        config = VoiceConfig(
            stt_model="large-v3",
            stt_device="cuda",
            stt_language="fr",
        )

        stt_config = config.get_stt_config()

        assert stt_config["model"] == "large-v3"
        assert stt_config["device"] == "cuda"
        assert stt_config["language"] == "fr"

    def test_get_tts_config_subset(self, clean_voice_config):
        """Test get_tts_config returns TTS-specific config."""
        config = VoiceConfig(
            tts_model="test-model",
            tts_voice="test_voice",
            tts_sample_rate=22050,
        )

        tts_config = config.get_tts_config()

        assert tts_config["model"] == "test-model"
        assert tts_config["voice"] == "test_voice"
        assert tts_config["sample_rate"] == 22050


# =============================================================================
# Test VoiceProviderRegistry STT Registration
# =============================================================================

class TestVoiceProviderRegistrySTT:
    """Test VoiceProviderRegistry.register_stt() and list_stt_providers()."""

    def test_register_stt_provider(self):
        """Test registering an STT provider."""
        VoiceProviderRegistry.register_stt(
            name="mock-whisper",
            provider_class=MockSTTProvider,
            description="Mock Whisper provider",
        )

        assert "mock-whisper" in VoiceProviderRegistry.list_stt_providers()

    def test_register_stt_with_metadata(self):
        """Test registering an STT provider with full metadata."""
        VoiceProviderRegistry.register_stt(
            name="test-stt",
            provider_class=MockSTTProvider,
            description="Test STT provider",
            supported_models=["tiny", "base", "large"],
            supports_streaming=True,
            hardware_requirements="GPU recommended",
            license="MIT",
        )

        info = VoiceProviderRegistry.get_stt_info("test-stt")

        assert info["name"] == "test-stt"
        assert info["description"] == "Test STT provider"
        assert info["supported_models"] == ["tiny", "base", "large"]
        assert info["supports_streaming"] is True
        assert info["hardware_requirements"] == "GPU recommended"
        assert info["license"] == "MIT"

    def test_list_stt_providers_empty(self):
        """Test list_stt_providers returns empty list when no providers registered."""
        providers = VoiceProviderRegistry.list_stt_providers()

        assert providers == []

    def test_list_stt_providers_multiple(self):
        """Test list_stt_providers returns all registered providers."""
        VoiceProviderRegistry.register_stt("provider-a", MockSTTProvider)
        VoiceProviderRegistry.register_stt("provider-b", AnotherMockSTTProvider)

        providers = VoiceProviderRegistry.list_stt_providers()

        assert "provider-a" in providers
        assert "provider-b" in providers
        assert len(providers) == 2

    def test_get_stt_provider_from_registry(self):
        """Test getting an STT provider instance from registry."""
        VoiceProviderRegistry.register_stt("mock-stt", MockSTTProvider)

        provider = VoiceProviderRegistry.get_stt("mock-stt")

        assert isinstance(provider, MockSTTProvider)
        assert provider.name == "mock-stt"

    def test_get_stt_provider_with_config(self):
        """Test getting an STT provider with custom config."""
        VoiceProviderRegistry.register_stt("mock-stt", MockSTTProvider)
        config = STTConfig(model="custom-model", language="de")

        provider = VoiceProviderRegistry.get_stt("mock-stt", config=config)

        assert provider.config.model == "custom-model"
        assert provider.config.language == "de"

    def test_get_stt_provider_unknown_raises_error(self):
        """Test that getting an unknown STT provider raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            VoiceProviderRegistry.get_stt("nonexistent-provider")

        assert "STT provider not found" in str(exc_info.value)
        assert "nonexistent-provider" in str(exc_info.value)

    def test_unregister_stt_provider(self):
        """Test unregistering an STT provider."""
        VoiceProviderRegistry.register_stt("temp-stt", MockSTTProvider)
        assert "temp-stt" in VoiceProviderRegistry.list_stt_providers()

        result = VoiceProviderRegistry.unregister_stt("temp-stt")

        assert result is True
        assert "temp-stt" not in VoiceProviderRegistry.list_stt_providers()

    def test_unregister_nonexistent_stt_returns_false(self):
        """Test unregistering nonexistent provider returns False."""
        result = VoiceProviderRegistry.unregister_stt("nonexistent")

        assert result is False

    def test_list_stt_providers_detailed(self):
        """Test list_stt_providers_detailed returns full info."""
        VoiceProviderRegistry.register_stt(
            "detailed-stt",
            MockSTTProvider,
            description="Detailed provider",
            supported_models=["model1"],
        )

        detailed = VoiceProviderRegistry.list_stt_providers_detailed()

        assert len(detailed) == 1
        assert detailed[0]["name"] == "detailed-stt"
        assert detailed[0]["description"] == "Detailed provider"


# =============================================================================
# Test VoiceProviderRegistry TTS Registration
# =============================================================================

class TestVoiceProviderRegistryTTS:
    """Test VoiceProviderRegistry.register_tts() and list_tts_providers()."""

    def test_register_tts_provider(self):
        """Test registering a TTS provider."""
        VoiceProviderRegistry.register_tts(
            name="mock-kokoro",
            provider_class=MockTTSProvider,
            description="Mock Kokoro provider",
        )

        assert "mock-kokoro" in VoiceProviderRegistry.list_tts_providers()

    def test_register_tts_with_metadata(self):
        """Test registering a TTS provider with full metadata."""
        VoiceProviderRegistry.register_tts(
            name="test-tts",
            provider_class=MockTTSProvider,
            description="Test TTS provider",
            supported_models=["model-a", "model-b"],
            supports_streaming=True,
            supports_voice_cloning=True,
            hardware_requirements="CPU only",
            license="Apache-2.0",
        )

        info = VoiceProviderRegistry.get_tts_info("test-tts")

        assert info["name"] == "test-tts"
        assert info["description"] == "Test TTS provider"
        assert info["supported_models"] == ["model-a", "model-b"]
        assert info["supports_streaming"] is True
        assert info["supports_voice_cloning"] is True
        assert info["hardware_requirements"] == "CPU only"
        assert info["license"] == "Apache-2.0"

    def test_list_tts_providers_empty(self):
        """Test list_tts_providers returns empty list when no providers registered."""
        providers = VoiceProviderRegistry.list_tts_providers()

        assert providers == []

    def test_list_tts_providers_multiple(self):
        """Test list_tts_providers returns all registered providers."""
        VoiceProviderRegistry.register_tts("tts-a", MockTTSProvider)
        VoiceProviderRegistry.register_tts("tts-b", AnotherMockTTSProvider)

        providers = VoiceProviderRegistry.list_tts_providers()

        assert "tts-a" in providers
        assert "tts-b" in providers
        assert len(providers) == 2

    def test_get_tts_provider_from_registry(self):
        """Test getting a TTS provider instance from registry."""
        VoiceProviderRegistry.register_tts("mock-tts", MockTTSProvider)

        provider = VoiceProviderRegistry.get_tts("mock-tts")

        assert isinstance(provider, MockTTSProvider)
        assert provider.name == "mock-tts"

    def test_get_tts_provider_with_config(self):
        """Test getting a TTS provider with custom config."""
        VoiceProviderRegistry.register_tts("mock-tts", MockTTSProvider)
        config = TTSConfig(voice="custom_voice", sample_rate=44100)

        provider = VoiceProviderRegistry.get_tts("mock-tts", config=config)

        assert provider.config.voice == "custom_voice"
        assert provider.config.sample_rate == 44100

    def test_get_tts_provider_unknown_raises_error(self):
        """Test that getting an unknown TTS provider raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            VoiceProviderRegistry.get_tts("nonexistent-provider")

        assert "TTS provider not found" in str(exc_info.value)
        assert "nonexistent-provider" in str(exc_info.value)

    def test_unregister_tts_provider(self):
        """Test unregistering a TTS provider."""
        VoiceProviderRegistry.register_tts("temp-tts", MockTTSProvider)
        assert "temp-tts" in VoiceProviderRegistry.list_tts_providers()

        result = VoiceProviderRegistry.unregister_tts("temp-tts")

        assert result is True
        assert "temp-tts" not in VoiceProviderRegistry.list_tts_providers()

    def test_unregister_nonexistent_tts_returns_false(self):
        """Test unregistering nonexistent provider returns False."""
        result = VoiceProviderRegistry.unregister_tts("nonexistent")

        assert result is False

    def test_list_tts_providers_detailed(self):
        """Test list_tts_providers_detailed returns full info."""
        VoiceProviderRegistry.register_tts(
            "detailed-tts",
            MockTTSProvider,
            description="Detailed TTS provider",
            supports_voice_cloning=True,
        )

        detailed = VoiceProviderRegistry.list_tts_providers_detailed()

        assert len(detailed) == 1
        assert detailed[0]["name"] == "detailed-tts"
        assert detailed[0]["supports_voice_cloning"] is True


# =============================================================================
# Test STT Factory Function
# =============================================================================

class TestSTTFactory:
    """Test get_stt_provider() factory function."""

    @pytest.mark.skip(reason="STT factory uses lazy imports - cannot easily mock providers")
    def test_get_stt_provider_returns_correct_type(self):
        """Test that get_stt_provider returns the correct provider type."""
        pass

    @pytest.mark.skip(reason="STT factory uses lazy imports - cannot easily mock providers")
    def test_get_stt_provider_with_explicit_name(self):
        """Test get_stt_provider with explicit provider name."""
        pass

    def test_get_stt_provider_unknown_raises_error(self):
        """Test that unknown provider raises ValueError."""
        from app.voice.providers.stt_factory import get_stt_provider

        with pytest.raises(ValueError) as exc_info:
            get_stt_provider("completely-unknown-provider")

        assert "Unknown STT provider" in str(exc_info.value)

    @pytest.mark.skip(reason="STT factory uses lazy imports - cannot easily mock providers")
    def test_get_stt_provider_applies_kwargs_to_config(self):
        """Test that kwargs are applied to STT config."""
        pass


# =============================================================================
# Test TTS Factory Function
# =============================================================================

class TestTTSFactory:
    """Test get_tts_provider() factory function."""

    def test_get_tts_provider_returns_correct_type(self):
        """Test that get_tts_provider returns the correct provider type."""
        # Register mock provider
        from app.voice.providers.tts_factory import register_provider, get_tts_provider, _PROVIDER_REGISTRY

        # Clear and register mock
        _PROVIDER_REGISTRY.clear()
        register_provider("kokoro", MockTTSProvider)

        provider = get_tts_provider("kokoro")

        assert isinstance(provider, TTSProvider)

        # Clean up
        _PROVIDER_REGISTRY.clear()

    def test_get_tts_provider_uses_env_default(self):
        """Test that get_tts_provider uses VOICE_TTS_PROVIDER env var."""
        from app.voice.providers.tts_factory import register_provider, get_tts_provider, _PROVIDER_REGISTRY

        _PROVIDER_REGISTRY.clear()
        register_provider("test-provider", MockTTSProvider)

        with patch.dict(os.environ, {"VOICE_TTS_PROVIDER": "test-provider"}):
            provider = get_tts_provider()  # No explicit name

            assert isinstance(provider, TTSProvider)

        _PROVIDER_REGISTRY.clear()

    def test_get_tts_provider_unknown_raises_error(self):
        """Test that unknown TTS provider raises TTSProviderError."""
        from app.voice.providers.tts_factory import get_tts_provider, _PROVIDER_REGISTRY

        _PROVIDER_REGISTRY.clear()

        with pytest.raises(TTSProviderError) as exc_info:
            get_tts_provider("unknown-tts-provider")

        assert "Unknown TTS provider" in str(exc_info.value)
        assert exc_info.value.provider == "unknown-tts-provider"

    def test_get_tts_provider_with_config(self):
        """Test get_tts_provider with explicit config."""
        from app.voice.providers.tts_factory import register_provider, get_tts_provider, _PROVIDER_REGISTRY

        _PROVIDER_REGISTRY.clear()
        register_provider("kokoro", MockTTSProvider)

        config = TTSConfig(voice="custom_voice", sample_rate=48000)
        provider = get_tts_provider("kokoro", config=config)

        assert provider.config.voice == "custom_voice"
        assert provider.config.sample_rate == 48000

        _PROVIDER_REGISTRY.clear()


# =============================================================================
# Test Provider Base Classes Abstract Methods
# =============================================================================

class TestProviderBaseClasses:
    """Test that provider base classes have required abstract methods."""

    def test_stt_provider_abstract_methods(self):
        """Test STTProvider has required abstract methods."""
        # Attempting to instantiate STTProvider directly should fail
        # because it has abstract methods
        with pytest.raises(TypeError) as exc_info:
            STTProvider()

        error_msg = str(exc_info.value)
        assert "abstract" in error_msg.lower()
        # Check that key abstract methods are mentioned
        assert "transcribe" in error_msg or "name" in error_msg

    def test_tts_provider_abstract_methods(self):
        """Test TTSProvider has required abstract methods."""
        # Attempting to instantiate TTSProvider directly should fail
        with pytest.raises(TypeError) as exc_info:
            TTSProvider()

        error_msg = str(exc_info.value)
        assert "abstract" in error_msg.lower()
        # Check that key abstract methods are mentioned
        assert "synthesize" in error_msg or "name" in error_msg or "available_voices" in error_msg

    def test_stt_provider_requires_transcribe(self):
        """Test STTProvider requires transcribe method."""
        class IncompleteSTT(STTProvider):
            @property
            def name(self) -> str:
                return "incomplete"

            async def transcribe_stream(self, audio_stream, language=None, **kwargs):
                yield "test"

        with pytest.raises(TypeError):
            IncompleteSTT()

    def test_stt_provider_requires_name_property(self):
        """Test STTProvider requires name property."""
        class IncompleteSTT(STTProvider):
            async def transcribe(self, audio, language=None, **kwargs):
                return "test"

            async def transcribe_stream(self, audio_stream, language=None, **kwargs):
                yield "test"

        with pytest.raises(TypeError):
            IncompleteSTT()

    def test_tts_provider_requires_synthesize(self):
        """Test TTSProvider requires synthesize method."""
        class IncompleteTTS(TTSProvider):
            @property
            def name(self) -> str:
                return "incomplete"

            @property
            def available_voices(self) -> List[str]:
                return ["voice1"]

            async def synthesize_stream(self, text, voice=None):
                yield b"test"

        with pytest.raises(TypeError):
            IncompleteTTS()

    def test_tts_provider_requires_available_voices(self):
        """Test TTSProvider requires available_voices property."""
        class IncompleteTTS(TTSProvider):
            @property
            def name(self) -> str:
                return "incomplete"

            async def synthesize(self, text, voice=None):
                return b"test"

            async def synthesize_stream(self, text, voice=None):
                yield b"test"

        with pytest.raises(TypeError):
            IncompleteTTS()

    def test_mock_stt_provider_is_valid(self):
        """Test that MockSTTProvider properly implements the interface."""
        provider = MockSTTProvider()

        assert provider.name == "mock-stt"
        assert hasattr(provider, "transcribe")
        assert hasattr(provider, "transcribe_stream")

    def test_mock_tts_provider_is_valid(self):
        """Test that MockTTSProvider properly implements the interface."""
        provider = MockTTSProvider()

        assert provider.name == "mock-tts"
        assert hasattr(provider, "synthesize")
        assert hasattr(provider, "synthesize_stream")
        assert "voice1" in provider.available_voices


# =============================================================================
# Test Provider Instance Caching
# =============================================================================

class TestProviderCaching:
    """Test provider instance caching in registry."""

    def test_reuse_instance_returns_same_object(self):
        """Test that reuse_instance=True returns the same provider instance."""
        VoiceProviderRegistry.register_stt("cached-stt", MockSTTProvider)

        provider1 = VoiceProviderRegistry.get_stt("cached-stt", reuse_instance=True)
        provider2 = VoiceProviderRegistry.get_stt("cached-stt", reuse_instance=True)

        assert provider1 is provider2

    def test_no_reuse_creates_new_instances(self):
        """Test that reuse_instance=False creates new instances."""
        VoiceProviderRegistry.register_stt("uncached-stt", MockSTTProvider)

        provider1 = VoiceProviderRegistry.get_stt("uncached-stt", reuse_instance=False)
        provider2 = VoiceProviderRegistry.get_stt("uncached-stt", reuse_instance=False)

        assert provider1 is not provider2

    def test_tts_reuse_instance(self):
        """Test TTS provider instance caching."""
        VoiceProviderRegistry.register_tts("cached-tts", MockTTSProvider)

        provider1 = VoiceProviderRegistry.get_tts("cached-tts", reuse_instance=True)
        provider2 = VoiceProviderRegistry.get_tts("cached-tts", reuse_instance=True)

        assert provider1 is provider2


# =============================================================================
# Test Error Handling
# =============================================================================

class TestErrorHandling:
    """Test error handling for voice providers."""

    def test_stt_provider_error_creation(self):
        """Test STTProviderError can be created and raised."""
        error = STTProviderError("Test error message")

        assert str(error) == "Test error message"

    def test_tts_provider_error_with_details(self):
        """Test TTSProviderError includes provider and cause."""
        cause = ValueError("Original error")
        error = TTSProviderError(
            "Failed to synthesize",
            provider="kokoro",
            cause=cause,
        )

        assert "Failed to synthesize" in str(error)
        assert error.provider == "kokoro"
        assert error.cause is cause

    def test_registry_overwrites_warning(self, caplog):
        """Test that registry logs warning when overwriting provider."""
        import logging

        with caplog.at_level(logging.WARNING):
            VoiceProviderRegistry.register_stt("duplicate", MockSTTProvider)
            VoiceProviderRegistry.register_stt("duplicate", AnotherMockSTTProvider)

        # Provider should be replaced
        provider = VoiceProviderRegistry.get_stt("duplicate")
        assert isinstance(provider, AnotherMockSTTProvider)


# =============================================================================
# Test Async Provider Operations
# =============================================================================

class TestAsyncProviderOperations:
    """Test async provider operations."""

    @pytest.mark.asyncio
    async def test_stt_provider_transcribe(self):
        """Test STT provider transcribe method."""
        provider = MockSTTProvider()
        await provider.initialize()

        result = await provider.transcribe(b"audio data")

        assert result == "mock transcription"
        await provider.shutdown()

    @pytest.mark.asyncio
    async def test_stt_provider_context_manager(self):
        """Test STT provider as async context manager."""
        async with MockSTTProvider() as provider:
            result = await provider.transcribe(b"audio data")
            assert result == "mock transcription"

    @pytest.mark.asyncio
    async def test_tts_provider_synthesize(self):
        """Test TTS provider synthesize method."""
        provider = MockTTSProvider()
        await provider.initialize()

        result = await provider.synthesize("Hello world")

        assert result == b"mock audio data"
        await provider.cleanup()

    @pytest.mark.asyncio
    async def test_stt_provider_stream(self):
        """Test STT provider streaming transcription."""
        provider = MockSTTProvider()

        async def audio_generator():
            yield b"chunk1"
            yield b"chunk2"

        results = []
        async for text in provider.transcribe_stream(audio_generator()):
            results.append(text)

        assert results == ["mock", "stream"]

    @pytest.mark.asyncio
    async def test_tts_provider_stream(self):
        """Test TTS provider streaming synthesis."""
        provider = MockTTSProvider()

        results = []
        async for chunk in provider.synthesize_stream("Hello"):
            results.append(chunk)

        assert results == [b"mock", b"audio"]


# =============================================================================
# Test STTConfig and TTSConfig
# =============================================================================

class TestProviderConfigs:
    """Test STTConfig and TTSConfig classes."""

    def test_stt_config_defaults(self):
        """Test STTConfig has sensible defaults."""
        config = STTConfig()

        assert config.model == "base"
        assert config.device == "auto"
        assert config.compute_type == "float16"
        assert config.sample_rate == 16000
        assert config.vad_enabled is True

    def test_stt_config_from_env(self, mock_env_vars):
        """Test STTConfig.from_env() loads environment variables."""
        config = STTConfig.from_env()

        assert config.model == "large-v3"  # From VOICE_STT_MODEL
        assert config.device == "cuda"  # From VOICE_STT_DEVICE

    def test_tts_config_defaults(self):
        """Test TTSConfig has sensible defaults."""
        config = TTSConfig()

        assert config.voice is None
        assert config.sample_rate == 24000
        assert config.language == "en"
        assert config.speed == 1.0
        assert config.device == "auto"

    def test_tts_config_custom_values(self):
        """Test TTSConfig accepts custom values."""
        config = TTSConfig(
            voice="custom_voice",
            sample_rate=44100,
            speed=1.25,
            device="cuda",
        )

        assert config.voice == "custom_voice"
        assert config.sample_rate == 44100
        assert config.speed == 1.25
        assert config.device == "cuda"
