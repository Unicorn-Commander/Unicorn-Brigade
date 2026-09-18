"""
Self-hosted Voice Providers for Unicorn Brigade voice system.

This module provides self-hosted STT (Speech-to-Text) and TTS (Text-to-Speech)
providers optimized for different hardware and use cases.

TTS Providers (Text-to-Speech):
- kokoro: Lightweight 82M model, runs on CPU, multiple voices (Apache 2.0)
- chatterbox: Voice cloning with emotion control (MIT license)
- marvis: Apple Silicon native with MLX/Metal acceleration
- cosyvoice: Ultra-low latency (~150ms), voice cloning
- custom: Load your own ONNX/PyTorch models

STT Providers (Speech-to-Text):
- whisper.cpp: Optimized for Apple Silicon with CoreML acceleration
- faster-whisper: CTranslate2-based, ideal for CUDA GPUs with INT8 support
- mlx-whisper: Native Metal acceleration for Apple Silicon

TTS Usage:
    from app.voice.providers import get_tts_provider

    # Auto-select based on environment variables
    tts = get_tts_provider()

    # Or specify explicitly
    tts = get_tts_provider("kokoro")
    await tts.initialize()

    # Synthesize audio
    audio = await tts.synthesize("Hello world!", voice="af_bella")

    # Stream synthesis
    async for chunk in tts.synthesize_stream("Hello world!"):
        play_audio(chunk)

Environment Variables:
    # TTS Configuration
    VOICE_TTS_PROVIDER: kokoro, chatterbox, marvis, cosyvoice, custom
    VOICE_TTS_MODEL: model name or path (provider-specific)
    VOICE_TTS_VOICE: default voice ID
    VOICE_TTS_SAMPLE_RATE: 22050, 24000, 44100 (default: 24000)
    VOICE_TTS_DEVICE: auto, cpu, cuda, mps (default: auto)
    CUSTOM_TTS_MODEL_PATH: path for custom ONNX/PyTorch models
    CUSTOM_TTS_CONFIG_PATH: path for custom model config
"""

# Base classes
from app.voice.providers.base import (
    # Enums
    DeviceType,
    ComputeType,
    ModelSize,
    # STT
    STTProvider,
    STTResult,
    STTSegment,
    STTConfig,
    STTProviderError,
    # TTS
    TTSProvider,
    TTSConfig,
    TTSProviderError,
    # Utilities
    detect_device,
    audio_to_pcm,
    pcm_to_wav,
)

# Central provider registry
from app.voice.providers.registry import (
    VoiceProviderRegistry,
    register_builtin_providers,
)

# STT Factory
from app.voice.providers.stt_factory import (
    get_stt_provider,
    get_default_provider,
    list_available_providers,
    is_provider_available,
    get_provider_info,
)

# TTS Factory
from app.voice.providers.tts_factory import (
    get_tts_provider,
    get_available_providers,
    get_best_available_provider,
    create_tts_provider,
    create_livekit_tts_plugin,
    register_provider,
)

# TTS Providers (lazy import to avoid dependency issues)
def _get_kokoro_provider():
    from app.voice.providers.tts_kokoro import KokoroTTSProvider
    return KokoroTTSProvider

def _get_chatterbox_provider():
    from app.voice.providers.tts_chatterbox import ChatterboxTTSProvider
    return ChatterboxTTSProvider

def _get_marvis_provider():
    from app.voice.providers.tts_marvis import MarvisTTSProvider
    return MarvisTTSProvider

def _get_cosyvoice_provider():
    from app.voice.providers.tts_cosyvoice import CosyVoiceTTSProvider
    return CosyVoiceTTSProvider

def _get_custom_provider():
    from app.voice.providers.tts_custom import CustomTTSProvider
    return CustomTTSProvider


__all__ = [
    # Enums
    "DeviceType",
    "ComputeType",
    "ModelSize",
    # Base classes - STT
    "STTProvider",
    "STTResult",
    "STTSegment",
    "STTConfig",
    "STTProviderError",
    # Base classes - TTS
    "TTSProvider",
    "TTSConfig",
    "TTSProviderError",
    # Utility functions
    "detect_device",
    "audio_to_pcm",
    "pcm_to_wav",
    # Central provider registry
    "VoiceProviderRegistry",
    "register_builtin_providers",
    # STT Factory
    "get_stt_provider",
    "get_default_provider",
    "list_available_providers",
    "is_provider_available",
    "get_provider_info",
    # TTS Factory
    "get_tts_provider",
    "get_available_providers",
    "get_best_available_provider",
    "create_tts_provider",
    "create_livekit_tts_plugin",
    "register_provider",
    # Lazy provider getters
    "_get_kokoro_provider",
    "_get_chatterbox_provider",
    "_get_marvis_provider",
    "_get_cosyvoice_provider",
    "_get_custom_provider",
]
