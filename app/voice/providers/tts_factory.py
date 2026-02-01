"""
TTS Provider Factory.

Factory function for creating TTS providers based on configuration
or environment variables. Supports automatic provider selection
and fallback chains.

Environment Variables:
    VOICE_TTS_PROVIDER: Provider name (kokoro, chatterbox, marvis, cosyvoice, custom)
    VOICE_TTS_MODEL: Model name/variant (provider-specific)
    VOICE_TTS_VOICE: Default voice ID
    VOICE_TTS_SAMPLE_RATE: Audio sample rate (22050, 24000, 44100)
    CUSTOM_TTS_MODEL_PATH: Path to custom model file
    CUSTOM_TTS_CONFIG_PATH: Path to custom model config

Usage:
    from app.voice.providers import get_tts_provider

    # Use environment variables
    tts = get_tts_provider()

    # Specify provider explicitly
    tts = get_tts_provider("kokoro")

    # With configuration
    tts = get_tts_provider("chatterbox", voice_sample_path="/path/to/sample.wav")

    # Get available providers
    from app.voice.providers import get_available_providers
    providers = get_available_providers()
"""

import logging
import os
from typing import Optional, Dict, Any, List, Type

from app.voice.providers.base import TTSProvider, TTSConfig, TTSProviderError

logger = logging.getLogger(__name__)

# Provider registry
_PROVIDER_REGISTRY: Dict[str, Type[TTSProvider]] = {}


def register_provider(name: str, provider_class: Type[TTSProvider]) -> None:
    """Register a TTS provider class."""
    _PROVIDER_REGISTRY[name] = provider_class


def _lazy_register_providers() -> None:
    """Lazily register all built-in providers."""
    if _PROVIDER_REGISTRY:
        return

    # Import providers and register them
    try:
        from app.voice.providers.tts_kokoro import KokoroTTSProvider
        register_provider("kokoro", KokoroTTSProvider)
    except ImportError:
        logger.debug("Kokoro provider not available")

    try:
        from app.voice.providers.tts_chatterbox import ChatterboxTTSProvider
        register_provider("chatterbox", ChatterboxTTSProvider)
        register_provider("chatterbox-turbo", ChatterboxTTSProvider)
    except ImportError:
        logger.debug("Chatterbox provider not available")

    try:
        from app.voice.providers.tts_marvis import MarvisTTSProvider
        register_provider("marvis", MarvisTTSProvider)
    except ImportError:
        logger.debug("Marvis provider not available")

    try:
        from app.voice.providers.tts_cosyvoice import CosyVoiceTTSProvider
        register_provider("cosyvoice", CosyVoiceTTSProvider)
    except ImportError:
        logger.debug("CosyVoice provider not available")

    try:
        from app.voice.providers.tts_custom import CustomTTSProvider
        register_provider("custom", CustomTTSProvider)
    except ImportError:
        logger.debug("Custom provider not available")


def get_tts_provider(
    provider_name: Optional[str] = None,
    config: Optional[TTSConfig] = None,
    auto_initialize: bool = False,
    **kwargs,
) -> TTSProvider:
    """
    Get a TTS provider instance.

    Args:
        provider_name: Provider name. If None, uses VOICE_TTS_PROVIDER env var
                      or defaults to "kokoro"
        config: Optional TTSConfig. If None, creates from env vars
        auto_initialize: If True, initialize the provider before returning
        **kwargs: Additional arguments passed to provider constructor

    Returns:
        TTSProvider instance

    Raises:
        TTSProviderError: If provider is not found or initialization fails

    Environment Variables:
        VOICE_TTS_PROVIDER: Default provider name
        VOICE_TTS_MODEL: Model name/variant
        VOICE_TTS_VOICE: Default voice ID
        VOICE_TTS_SAMPLE_RATE: Audio sample rate
        CUSTOM_TTS_MODEL_PATH: Path for custom models
        CUSTOM_TTS_CONFIG_PATH: Config path for custom models
    """
    _lazy_register_providers()

    # Determine provider name
    provider_name = provider_name or os.getenv("VOICE_TTS_PROVIDER", "kokoro")
    provider_name = provider_name.lower()

    # Build config from environment if not provided
    if config is None:
        config = TTSConfig(
            voice=os.getenv("VOICE_TTS_VOICE"),
            sample_rate=int(os.getenv("VOICE_TTS_SAMPLE_RATE", "24000")),
            model_path=os.getenv("CUSTOM_TTS_MODEL_PATH"),
            device=os.getenv("VOICE_TTS_DEVICE", "auto"),
        )

    # Get provider class
    provider_class = _PROVIDER_REGISTRY.get(provider_name)

    if not provider_class:
        available = list(_PROVIDER_REGISTRY.keys())
        raise TTSProviderError(
            f"Unknown TTS provider: '{provider_name}'. "
            f"Available providers: {available}",
            provider=provider_name,
        )

    # Create provider instance with appropriate arguments
    try:
        if provider_name == "chatterbox-turbo":
            provider = provider_class(config, model="chatterbox-turbo", **kwargs)
        elif provider_name == "custom":
            config_path = kwargs.pop("config_path", os.getenv("CUSTOM_TTS_CONFIG_PATH"))
            provider = provider_class(config, config_path=config_path, **kwargs)
        else:
            provider = provider_class(config, **kwargs)

        logger.info(f"Created TTS provider: {provider_name}")

        if auto_initialize:
            import asyncio
            asyncio.get_event_loop().run_until_complete(provider.initialize())

        return provider

    except Exception as e:
        raise TTSProviderError(
            f"Failed to create provider '{provider_name}': {e}",
            provider=provider_name,
            cause=e,
        )


def get_available_providers() -> List[Dict[str, Any]]:
    """
    Get list of available TTS providers with their capabilities.

    Returns:
        List of provider info dictionaries
    """
    _lazy_register_providers()

    providers = []

    for name, provider_class in _PROVIDER_REGISTRY.items():
        try:
            # Create temporary instance to get info
            provider = provider_class()
            info = {
                "name": name,
                "class": provider_class.__name__,
                "sample_rate": provider.sample_rate,
                "supports_voice_cloning": provider.supports_voice_cloning,
                "supports_streaming": provider.supports_streaming,
                "voices": provider.available_voices[:5],  # First 5 voices
            }

            # Check if provider has special availability check
            if hasattr(provider_class, "is_available"):
                info["available"] = provider_class.is_available()
            else:
                info["available"] = True

            providers.append(info)

        except Exception as e:
            providers.append({
                "name": name,
                "available": False,
                "error": str(e),
            })

    return providers


def get_best_available_provider(
    prefer_voice_cloning: bool = False,
    prefer_streaming: bool = True,
    prefer_local: bool = True,
) -> Optional[str]:
    """
    Get the best available TTS provider based on preferences.

    Args:
        prefer_voice_cloning: Prefer providers with voice cloning
        prefer_streaming: Prefer providers with streaming support
        prefer_local: Prefer providers that run locally (no API)

    Returns:
        Provider name or None if no suitable provider found
    """
    _lazy_register_providers()

    candidates = []

    for name, provider_class in _PROVIDER_REGISTRY.items():
        try:
            # Check availability
            if hasattr(provider_class, "is_available"):
                if not provider_class.is_available():
                    continue

            provider = provider_class()

            score = 0

            # Score based on preferences
            if prefer_voice_cloning and provider.supports_voice_cloning:
                score += 10
            if prefer_streaming and provider.supports_streaming:
                score += 5
            if prefer_local:
                # All our providers are local
                score += 3

            candidates.append((name, score))

        except Exception:
            continue

    if not candidates:
        return None

    # Sort by score (highest first)
    candidates.sort(key=lambda x: x[1], reverse=True)

    return candidates[0][0]


async def create_tts_provider(
    provider_name: Optional[str] = None,
    **kwargs,
) -> TTSProvider:
    """
    Async factory function that creates and initializes a TTS provider.

    Args:
        provider_name: Provider name (or from env var)
        **kwargs: Additional arguments

    Returns:
        Initialized TTSProvider
    """
    provider = get_tts_provider(provider_name, **kwargs)
    await provider.initialize()
    return provider


# LiveKit Agents Integration
def create_livekit_tts_plugin(
    provider_name: Optional[str] = None,
    **kwargs,
) -> Any:
    """
    Create a LiveKit Agents compatible TTS plugin.

    This wraps our TTS provider to work with LiveKit's agent framework.

    Args:
        provider_name: Provider name
        **kwargs: Additional arguments

    Returns:
        LiveKit-compatible TTS plugin

    Usage with LiveKit Agents:
        from app.voice.providers.tts_factory import create_livekit_tts_plugin

        tts = create_livekit_tts_plugin("kokoro")
        agent = VoiceAssistant(tts=tts, ...)
    """
    try:
        from livekit.agents import tts as lk_tts

        class BrigadeTTSPlugin(lk_tts.TTS):
            """LiveKit-compatible wrapper for Brigade TTS providers."""

            def __init__(self, provider: TTSProvider):
                self._provider = provider
                self._initialized = False

            async def _ensure_initialized(self):
                if not self._initialized:
                    await self._provider.initialize()
                    self._initialized = True

            @property
            def sample_rate(self) -> int:
                return self._provider.sample_rate

            @property
            def num_channels(self) -> int:
                return 1  # Mono

            async def synthesize(self, text: str) -> lk_tts.SynthesizedAudio:
                await self._ensure_initialized()
                audio = await self._provider.synthesize(text)

                return lk_tts.SynthesizedAudio(
                    frame=lk_tts.AudioFrame(
                        data=audio,
                        sample_rate=self.sample_rate,
                        num_channels=self.num_channels,
                    ),
                    text=text,
                )

            def stream(self, text: str) -> lk_tts.SynthesisStream:
                return BrigadeTTSStream(self._provider, text)

        class BrigadeTTSStream(lk_tts.SynthesisStream):
            """LiveKit-compatible streaming wrapper."""

            def __init__(self, provider: TTSProvider, text: str):
                self._provider = provider
                self._text = text
                self._closed = False

            async def __anext__(self) -> lk_tts.SynthesizedAudio:
                if self._closed:
                    raise StopAsyncIteration

                # Get stream from provider
                chunks = []
                async for chunk in self._provider.synthesize_stream(self._text):
                    chunks.append(chunk)

                self._closed = True

                return lk_tts.SynthesizedAudio(
                    frame=lk_tts.AudioFrame(
                        data=b"".join(chunks),
                        sample_rate=self._provider.sample_rate,
                        num_channels=1,
                    ),
                    text=self._text,
                )

            async def aclose(self):
                self._closed = True

        # Create provider and wrap it
        provider = get_tts_provider(provider_name, **kwargs)
        return BrigadeTTSPlugin(provider)

    except ImportError:
        logger.warning(
            "LiveKit Agents not installed. "
            "Install with: pip install livekit-agents"
        )
        # Return the raw provider as fallback
        return get_tts_provider(provider_name, **kwargs)
