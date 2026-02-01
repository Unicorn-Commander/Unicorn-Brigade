"""
Voice module for LiveKit-based voice agent interactions.

This module provides:
- LiveKitVoiceAgent: Voice agent worker that connects to LiveKit rooms
- VoiceRoomManager: Manages voice room lifecycle
- Self-hosted TTS providers:
  - Kokoro: Lightweight 82M model, runs on CPU (Apache 2.0)
  - Chatterbox: Voice cloning with emotion control (MIT)
  - Marvis: Apple Silicon native with MLX acceleration
  - CosyVoice: Ultra-low latency (~150ms), voice cloning
  - Custom: Load your own ONNX/PyTorch models

Usage:
    from app.voice import LiveKitVoiceAgent, VoiceRoomManager

    # Create a voice room for an agent
    room_manager = VoiceRoomManager()
    room = await room_manager.create_room(agent_id="col-finance")

    # Voice agent connects automatically when room is created

    # Using self-hosted TTS providers
    from app.voice.providers import get_tts_provider

    # Default provider (Kokoro)
    tts = get_tts_provider()
    await tts.initialize()
    audio = await tts.synthesize("Hello world!", voice="af_bella")

    # Voice cloning with Chatterbox
    tts = get_tts_provider("chatterbox")
    await tts.initialize()
    voice_id = await tts.clone_voice("/path/to/sample.wav")
    audio = await tts.synthesize("Hello in your voice!", voice=voice_id)

    # Streaming for real-time playback
    async for chunk in tts.synthesize_stream("Hello world!"):
        play_audio(chunk)

Environment Variables:
    VOICE_TTS_PROVIDER: kokoro, chatterbox, marvis, cosyvoice, custom
    VOICE_TTS_VOICE: default voice ID
    VOICE_TTS_SAMPLE_RATE: 22050, 24000, 44100
    CUSTOM_TTS_MODEL_PATH: path for custom models
"""

from app.voice.livekit_agent import (
    LiveKitVoiceAgent,
    VoiceRoomManager,
    VoiceConfig as LiveKitVoiceConfig,
    VoiceConfig,  # Also export without alias for backward compatibility
    STTProvider as STTProviderEnum,
    TTSProvider as TTSProviderEnum,
)

# Import TTS providers
from app.voice.providers import (
    # Base classes
    STTProvider,
    STTResult,
    STTSegment,
    STTConfig,
    STTProviderError,
    TTSProvider,
    TTSConfig,
    TTSProviderError,
    # Utilities
    detect_device,
    audio_to_pcm,
    pcm_to_wav,
    # TTS Factory
    get_tts_provider,
    get_available_providers,
    get_best_available_provider,
    create_tts_provider,
    create_livekit_tts_plugin,
)

__all__ = [
    # LiveKit Agent
    "LiveKitVoiceAgent",
    "VoiceRoomManager",
    "VoiceConfig",
    "LiveKitVoiceConfig",
    "STTProviderEnum",
    "TTSProviderEnum",
    # Self-hosted STT Base
    "STTProvider",
    "STTResult",
    "STTSegment",
    "STTConfig",
    "STTProviderError",
    # Self-hosted TTS Base
    "TTSProvider",
    "TTSConfig",
    "TTSProviderError",
    # TTS Factory
    "get_tts_provider",
    "get_available_providers",
    "get_best_available_provider",
    "create_tts_provider",
    "create_livekit_tts_plugin",
    # Utilities
    "detect_device",
    "audio_to_pcm",
    "pcm_to_wav",
]
