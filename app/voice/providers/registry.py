"""
Central registry for voice providers (STT and TTS).

This module provides a singleton registry for managing voice providers,
enabling dynamic registration, discovery, and instantiation of providers.

Usage:
    from app.voice.providers.registry import VoiceProviderRegistry

    # Register a provider
    VoiceProviderRegistry.register_stt("faster-whisper", FasterWhisperProvider)

    # Get a provider instance
    stt = VoiceProviderRegistry.get_stt("faster-whisper", model="large-v3-turbo")

    # List available providers
    providers = VoiceProviderRegistry.list_stt_providers()
"""

import logging
from typing import Dict, Type, List, Optional, Any

from app.voice.providers.base import (
    STTProvider,
    STTConfig,
    TTSProvider,
    TTSConfig,
)

logger = logging.getLogger(__name__)


class VoiceProviderRegistry:
    """
    Central registry for all voice providers.

    This is a singleton class that manages registration and retrieval
    of STT and TTS providers.
    """

    # Class-level registries
    _stt_providers: Dict[str, Type[STTProvider]] = {}
    _tts_providers: Dict[str, Type[TTSProvider]] = {}

    # Provider metadata (descriptions, requirements, etc.)
    _stt_metadata: Dict[str, Dict[str, Any]] = {}
    _tts_metadata: Dict[str, Dict[str, Any]] = {}

    # Singleton instances (for providers that should be reused)
    _stt_instances: Dict[str, STTProvider] = {}
    _tts_instances: Dict[str, TTSProvider] = {}

    # =========================================================================
    # STT Provider Registration
    # =========================================================================

    @classmethod
    def register_stt(
        cls,
        name: str,
        provider_class: Type[STTProvider],
        description: str = "",
        supported_models: Optional[List[str]] = None,
        supports_streaming: bool = True,
        hardware_requirements: str = "CPU (GPU optional)",
        license: str = "MIT",
    ) -> None:
        """
        Register an STT provider.

        Args:
            name: Unique provider name (e.g., "faster-whisper")
            provider_class: The provider class to register
            description: Human-readable description
            supported_models: List of supported model names
            supports_streaming: Whether streaming is supported
            hardware_requirements: Hardware requirements description
            license: License information
        """
        if name in cls._stt_providers:
            logger.warning(f"Overwriting existing STT provider: {name}")

        cls._stt_providers[name] = provider_class
        cls._stt_metadata[name] = {
            "description": description or f"{name} STT provider",
            "supported_models": supported_models or [],
            "supports_streaming": supports_streaming,
            "hardware_requirements": hardware_requirements,
            "license": license,
        }

        logger.info(f"Registered STT provider: {name}")

    @classmethod
    def unregister_stt(cls, name: str) -> bool:
        """
        Unregister an STT provider.

        Args:
            name: Provider name to unregister

        Returns:
            True if provider was unregistered, False if not found
        """
        if name in cls._stt_providers:
            del cls._stt_providers[name]
            cls._stt_metadata.pop(name, None)

            # Clean up any cached instance
            if name in cls._stt_instances:
                del cls._stt_instances[name]

            logger.info(f"Unregistered STT provider: {name}")
            return True

        return False

    @classmethod
    def get_stt(
        cls,
        name: str,
        config: Optional[STTConfig] = None,
        reuse_instance: bool = False,
        **kwargs
    ) -> STTProvider:
        """
        Get an STT provider instance.

        Args:
            name: Provider name
            config: Optional configuration (if None, uses defaults)
            reuse_instance: If True, return cached instance if available
            **kwargs: Additional arguments passed to config

        Returns:
            STTProvider instance

        Raises:
            ValueError: If provider not found
        """
        if name not in cls._stt_providers:
            available = ", ".join(cls._stt_providers.keys())
            raise ValueError(
                f"STT provider not found: {name}. Available: {available}"
            )

        # Return cached instance if requested and available
        if reuse_instance and name in cls._stt_instances:
            return cls._stt_instances[name]

        # Create config if not provided
        if config is None:
            config = STTConfig()

        # Apply kwargs to config
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)

        # Create provider instance
        provider = cls._stt_providers[name](config)

        # Cache if requested
        if reuse_instance:
            cls._stt_instances[name] = provider

        return provider

    @classmethod
    def list_stt_providers(cls) -> List[str]:
        """
        List registered STT provider names.

        Returns:
            List of provider names
        """
        return list(cls._stt_providers.keys())

    @classmethod
    def get_stt_info(cls, name: str) -> Dict[str, Any]:
        """
        Get detailed information about an STT provider.

        Args:
            name: Provider name

        Returns:
            Dictionary with provider information

        Raises:
            ValueError: If provider not found
        """
        if name not in cls._stt_providers:
            raise ValueError(f"STT provider not found: {name}")

        metadata = cls._stt_metadata.get(name, {})

        return {
            "name": name,
            "description": metadata.get("description", ""),
            "supported_models": metadata.get("supported_models", []),
            "supports_streaming": metadata.get("supports_streaming", True),
            "hardware_requirements": metadata.get("hardware_requirements", ""),
            "license": metadata.get("license", ""),
        }

    @classmethod
    def list_stt_providers_detailed(cls) -> List[Dict[str, Any]]:
        """
        List all STT providers with detailed information.

        Returns:
            List of provider info dictionaries
        """
        return [cls.get_stt_info(name) for name in cls._stt_providers.keys()]

    # =========================================================================
    # TTS Provider Registration
    # =========================================================================

    @classmethod
    def register_tts(
        cls,
        name: str,
        provider_class: Type[TTSProvider],
        description: str = "",
        supported_models: Optional[List[str]] = None,
        supports_streaming: bool = True,
        supports_voice_cloning: bool = False,
        hardware_requirements: str = "CPU (GPU optional)",
        license: str = "Apache-2.0",
    ) -> None:
        """
        Register a TTS provider.

        Args:
            name: Unique provider name (e.g., "kokoro")
            provider_class: The provider class to register
            description: Human-readable description
            supported_models: List of supported model names
            supports_streaming: Whether streaming is supported
            supports_voice_cloning: Whether voice cloning is supported
            hardware_requirements: Hardware requirements description
            license: License information
        """
        if name in cls._tts_providers:
            logger.warning(f"Overwriting existing TTS provider: {name}")

        cls._tts_providers[name] = provider_class
        cls._tts_metadata[name] = {
            "description": description or f"{name} TTS provider",
            "supported_models": supported_models or [],
            "supports_streaming": supports_streaming,
            "supports_voice_cloning": supports_voice_cloning,
            "hardware_requirements": hardware_requirements,
            "license": license,
        }

        logger.info(f"Registered TTS provider: {name}")

    @classmethod
    def unregister_tts(cls, name: str) -> bool:
        """
        Unregister a TTS provider.

        Args:
            name: Provider name to unregister

        Returns:
            True if provider was unregistered, False if not found
        """
        if name in cls._tts_providers:
            del cls._tts_providers[name]
            cls._tts_metadata.pop(name, None)

            # Clean up any cached instance
            if name in cls._tts_instances:
                del cls._tts_instances[name]

            logger.info(f"Unregistered TTS provider: {name}")
            return True

        return False

    @classmethod
    def get_tts(
        cls,
        name: str,
        config: Optional[TTSConfig] = None,
        reuse_instance: bool = False,
        **kwargs
    ) -> TTSProvider:
        """
        Get a TTS provider instance.

        Args:
            name: Provider name
            config: Optional configuration (if None, uses defaults)
            reuse_instance: If True, return cached instance if available
            **kwargs: Additional arguments passed to config

        Returns:
            TTSProvider instance

        Raises:
            ValueError: If provider not found
        """
        if name not in cls._tts_providers:
            available = ", ".join(cls._tts_providers.keys())
            raise ValueError(
                f"TTS provider not found: {name}. Available: {available}"
            )

        # Return cached instance if requested and available
        if reuse_instance and name in cls._tts_instances:
            return cls._tts_instances[name]

        # Create config if not provided
        if config is None:
            config = TTSConfig()

        # Apply kwargs to config
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)

        # Create provider instance
        provider = cls._tts_providers[name](config)

        # Cache if requested
        if reuse_instance:
            cls._tts_instances[name] = provider

        return provider

    @classmethod
    def list_tts_providers(cls) -> List[str]:
        """
        List registered TTS provider names.

        Returns:
            List of provider names
        """
        return list(cls._tts_providers.keys())

    @classmethod
    def get_tts_info(cls, name: str) -> Dict[str, Any]:
        """
        Get detailed information about a TTS provider.

        Args:
            name: Provider name

        Returns:
            Dictionary with provider information

        Raises:
            ValueError: If provider not found
        """
        if name not in cls._tts_providers:
            raise ValueError(f"TTS provider not found: {name}")

        metadata = cls._tts_metadata.get(name, {})

        return {
            "name": name,
            "description": metadata.get("description", ""),
            "supported_models": metadata.get("supported_models", []),
            "supports_streaming": metadata.get("supports_streaming", True),
            "supports_voice_cloning": metadata.get("supports_voice_cloning", False),
            "hardware_requirements": metadata.get("hardware_requirements", ""),
            "license": metadata.get("license", ""),
        }

    @classmethod
    def list_tts_providers_detailed(cls) -> List[Dict[str, Any]]:
        """
        List all TTS providers with detailed information.

        Returns:
            List of provider info dictionaries
        """
        return [cls.get_tts_info(name) for name in cls._tts_providers.keys()]

    # =========================================================================
    # Utility Methods
    # =========================================================================

    @classmethod
    def clear_all(cls) -> None:
        """Clear all registered providers (mainly for testing)."""
        cls._stt_providers.clear()
        cls._tts_providers.clear()
        cls._stt_metadata.clear()
        cls._tts_metadata.clear()
        cls._stt_instances.clear()
        cls._tts_instances.clear()

    @classmethod
    async def shutdown_all(cls) -> None:
        """Shutdown all cached provider instances."""
        for provider in cls._stt_instances.values():
            try:
                await provider.shutdown()
            except Exception as e:
                logger.error(f"Error shutting down STT provider: {e}")

        for provider in cls._tts_instances.values():
            try:
                await provider.shutdown()
            except Exception as e:
                logger.error(f"Error shutting down TTS provider: {e}")

        cls._stt_instances.clear()
        cls._tts_instances.clear()


def register_builtin_providers() -> None:
    """
    Register all built-in voice providers.

    This function is called during application startup to register
    the default STT and TTS providers.
    """
    # Import providers here to avoid circular imports
    from app.voice.providers.stt_faster_whisper import FasterWhisperProvider
    from app.voice.providers.stt_whisper_cpp import WhisperCppProvider
    from app.voice.providers.stt_mlx_whisper import MLXWhisperProvider
    from app.voice.providers.tts_kokoro import KokoroTTSProvider

    # Register STT providers
    VoiceProviderRegistry.register_stt(
        name="faster-whisper",
        provider_class=FasterWhisperProvider,
        description="CTranslate2-optimized Whisper for CUDA GPUs with INT8 support",
        supported_models=[
            "tiny", "tiny.en", "base", "base.en", "small", "small.en",
            "medium", "medium.en", "large-v1", "large-v2", "large-v3",
            "large-v3-turbo", "distil-large-v2", "distil-large-v3"
        ],
        supports_streaming=True,
        hardware_requirements="CUDA GPU recommended, CPU supported",
        license="MIT",
    )

    VoiceProviderRegistry.register_stt(
        name="whisper-cpp",
        provider_class=WhisperCppProvider,
        description="Optimized C++ implementation with CoreML support for Apple Silicon",
        supported_models=[
            "tiny", "tiny.en", "base", "base.en", "small", "small.en",
            "medium", "medium.en", "large-v1", "large-v2", "large-v3",
            "large-v3-turbo"
        ],
        supports_streaming=True,
        hardware_requirements="Apple Silicon (CoreML) or CPU",
        license="MIT",
    )

    VoiceProviderRegistry.register_stt(
        name="mlx-whisper",
        provider_class=MLXWhisperProvider,
        description="Native Metal acceleration for Apple Silicon using MLX framework",
        supported_models=[
            "tiny", "tiny.en", "base", "base.en", "small", "small.en",
            "medium", "medium.en", "large-v3", "large-v3-turbo"
        ],
        supports_streaming=True,
        hardware_requirements="Apple Silicon required (M1/M2/M3)",
        license="MIT",
    )

    # Register TTS providers
    VoiceProviderRegistry.register_tts(
        name="kokoro",
        provider_class=KokoroTTSProvider,
        description="High-quality, fast TTS with expressive voices (Apache-2.0)",
        supported_models=["kokoro-82m"],
        supports_streaming=True,
        supports_voice_cloning=False,
        hardware_requirements="CPU (GPU optional for faster inference)",
        license="Apache-2.0",
    )

    logger.info("Registered built-in voice providers")
