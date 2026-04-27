"""
STT Provider Factory.

Provides factory functions for creating STT providers based on
environment configuration or explicit selection.

Usage:
    from app.voice.providers import get_stt_provider

    # Auto-select based on environment
    stt = get_stt_provider()

    # Explicit selection
    stt = get_stt_provider("faster-whisper", model="large-v3-turbo")

    # Use with LiveKit Agents
    from app.voice.providers import LiveKitSTTAdapter
    stt_adapter = LiveKitSTTAdapter(get_stt_provider())
"""

import asyncio
import logging
import os
import platform
from typing import Optional, List, Dict, Any

from app.voice.providers.base import STTConfig, STTProvider, DeviceType, ComputeType

logger = logging.getLogger(__name__)


def get_default_provider() -> str:
    """
    Determine the default STT provider based on the system.

    Returns:
        Provider name: "mlx-whisper" for Apple Silicon, "faster-whisper" otherwise
    """
    # Check environment variable first
    env_provider = os.getenv("VOICE_STT_PROVIDER")
    if env_provider:
        return env_provider

    # Auto-detect based on hardware
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        # Apple Silicon - prefer MLX or whisper.cpp with CoreML
        try:
            import mlx.core
            return "mlx-whisper"
        except ImportError:
            pass

        try:
            import pywhispercpp
            return "whisper-cpp"
        except ImportError:
            pass

    # CUDA available - use faster-whisper
    try:
        import torch
        if torch.cuda.is_available():
            return "faster-whisper"
    except ImportError:
        pass

    # Fallback to faster-whisper (works on CPU too)
    return "faster-whisper"


def list_available_providers() -> List[str]:
    """
    List STT providers that are actually available (dependencies installed).

    Returns:
        List of available provider names
    """
    available = []

    # Check faster-whisper
    try:
        import faster_whisper
        available.append("faster-whisper")
    except ImportError:
        pass

    # Check whisper.cpp
    try:
        import pywhispercpp
        available.append("whisper-cpp")
    except ImportError:
        pass

    # Check MLX Whisper
    try:
        import mlx_whisper
        available.append("mlx-whisper")
    except ImportError:
        pass

    # Amanuensis is HTTP-based, always available
    available.append("amanuensis")

    return available


def is_provider_available(provider_name: str) -> bool:
    """
    Check if a specific provider is available.

    Args:
        provider_name: Provider name to check

    Returns:
        True if provider is available
    """
    return provider_name.lower() in list_available_providers()


def get_provider_info(provider_name: str) -> Dict[str, Any]:
    """
    Get information about a specific provider.

    Args:
        provider_name: Provider name

    Returns:
        Dictionary with provider capabilities
    """
    provider_name = provider_name.lower()
    provider = get_stt_provider(provider_name)

    return {
        "name": provider.name,
        "supports_streaming": provider.supports_streaming,
        "supports_word_timestamps": provider.supports_word_timestamps,
        "supports_vad": provider.supports_vad,
        "available": is_provider_available(provider_name),
    }


def get_stt_provider(
    provider_name: Optional[str] = None,
    config: Optional[STTConfig] = None,
    **kwargs
) -> STTProvider:
    """
    Get an STT provider instance.

    Args:
        provider_name: Provider name (auto-detected if not specified)
        config: Optional STTConfig (created from env if not specified)
        **kwargs: Additional config options

    Returns:
        STTProvider instance

    Raises:
        ImportError: If required dependencies are not installed
        ValueError: If provider is not recognized
    """
    # Determine provider
    if provider_name is None:
        provider_name = get_default_provider()

    provider_name = provider_name.lower()

    # Create config from env if not provided
    if config is None:
        config = STTConfig.from_env()

    # Apply kwargs to config
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)

    # Create provider
    if provider_name == "faster-whisper":
        from app.voice.providers.stt_faster_whisper import FasterWhisperProvider
        return FasterWhisperProvider(config)

    elif provider_name in ("whisper-cpp", "whispercpp"):
        from app.voice.providers.stt_whisper_cpp import WhisperCppProvider
        return WhisperCppProvider(config)

    elif provider_name in ("mlx-whisper", "mlxwhisper"):
        from app.voice.providers.stt_mlx_whisper import MLXWhisperProvider
        return MLXWhisperProvider(config)

    elif provider_name == "amanuensis":
        from app.voice.providers.stt_amanuensis import AmanuensisSTTProvider
        return AmanuensisSTTProvider(config)

    else:
        available = list_available_providers()
        raise ValueError(
            f"Unknown STT provider: {provider_name}. "
            f"Available: {available}"
        )


# ============================================================================
# LiveKit Agents Integration
# ============================================================================

class LiveKitSTTAdapter:
    """
    Adapter to use self-hosted STT providers with LiveKit Agents.

    This adapter wraps our STTProvider interface to be compatible with
    LiveKit's STT plugin interface.

    Usage:
        from livekit.agents import AutoSubscribe, JobContext, WorkerOptions
        from app.voice.providers import get_stt_provider, LiveKitSTTAdapter

        stt_provider = get_stt_provider("mlx-whisper")
        stt_adapter = LiveKitSTTAdapter(stt_provider)

        # Use in agent pipeline
        agent = VoicePipelineAgent(
            stt=stt_adapter,
            ...
        )
    """

    def __init__(self, provider: STTProvider):
        """
        Initialize the adapter.

        Args:
            provider: Self-hosted STT provider instance
        """
        self.provider = provider
        self._initialized = False

    async def _ensure_initialized(self):
        """Ensure provider is initialized."""
        if not self._initialized:
            await self.provider.initialize()
            self._initialized = True

    async def recognize(self, audio_data: bytes) -> str:
        """
        Recognize speech from audio data.

        This method matches LiveKit's STT interface.

        Args:
            audio_data: Raw audio bytes

        Returns:
            Transcribed text
        """
        await self._ensure_initialized()
        return await self.provider.transcribe(
            audio_data,
            language=self.provider.config.language,
        )

    def stream(self):
        """
        Create a streaming recognition session.

        Returns:
            LiveKitSTTStream instance
        """
        return LiveKitSTTStream(self.provider)

    async def close(self):
        """Clean up resources."""
        await self.provider.shutdown()


class LiveKitSTTStream:
    """
    Streaming STT session compatible with LiveKit Agents.

    Wraps the provider's transcribe_stream method.
    """

    def __init__(self, provider: STTProvider):
        self.provider = provider
        self._audio_queue: Optional[asyncio.Queue] = None
        self._result_queue: Optional[asyncio.Queue] = None
        self._task: Optional[asyncio.Task] = None
        self._closed = False

    async def __aenter__(self):
        """Start the streaming session."""
        self._audio_queue = asyncio.Queue()
        self._result_queue = asyncio.Queue()

        # Start processing task
        self._task = asyncio.create_task(self._process_stream())

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """End the streaming session."""
        self._closed = True
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def push_frame(self, audio_frame):
        """
        Push an audio frame for processing.

        Args:
            audio_frame: Audio frame (bytes or frame object with .data attribute)
        """
        if self._audio_queue and not self._closed:
            # Handle both raw bytes and frame objects
            if hasattr(audio_frame, "data"):
                audio_data = audio_frame.data
            else:
                audio_data = audio_frame

            await self._audio_queue.put(audio_data)

    async def flush(self):
        """Flush any remaining audio and get final results."""
        if self._audio_queue:
            await self._audio_queue.put(None)  # Signal end

    async def _process_stream(self):
        """Process audio stream in background."""
        async def audio_generator():
            while True:
                if self._audio_queue is None:
                    break
                chunk = await self._audio_queue.get()
                if chunk is None:
                    break
                yield chunk

        try:
            async for text in self.provider.transcribe_stream(audio_generator()):
                if self._result_queue:
                    await self._result_queue.put(text)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Stream processing error: {e}")
        finally:
            if self._result_queue:
                await self._result_queue.put(None)

    def __aiter__(self):
        """Iterate over transcription results."""
        return self

    async def __anext__(self):
        """Get next transcription result."""
        if self._result_queue is None or self._closed:
            raise StopAsyncIteration

        result = await self._result_queue.get()
        if result is None:
            raise StopAsyncIteration

        return result


# ============================================================================
# Utility Functions
# ============================================================================

async def transcribe_audio(
    audio: bytes,
    provider_name: Optional[str] = None,
    language: str = "en",
    **kwargs,
) -> str:
    """
    Convenience function to transcribe audio with minimal setup.

    Creates a provider, transcribes, and cleans up.

    Args:
        audio: Raw audio bytes
        provider_name: Optional provider name
        language: Language code
        **kwargs: Additional config options

    Returns:
        Transcribed text
    """
    provider = get_stt_provider(provider_name, **kwargs)

    try:
        await provider.initialize()
        return await provider.transcribe(audio, language)
    finally:
        await provider.shutdown()


async def transcribe_file(
    file_path: str,
    provider_name: Optional[str] = None,
    language: str = "en",
    **kwargs,
) -> str:
    """
    Convenience function to transcribe an audio file.

    Args:
        file_path: Path to audio file
        provider_name: Optional provider name
        language: Language code
        **kwargs: Additional config options

    Returns:
        Transcribed text
    """
    # Read and convert file to raw audio
    import wave

    with wave.open(file_path, "rb") as wav:
        audio = wav.readframes(wav.getnframes())

    return await transcribe_audio(audio, provider_name, language, **kwargs)
