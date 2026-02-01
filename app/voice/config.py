"""
Voice configuration module for Unicorn Brigade.

Provides centralized configuration for voice providers (STT and TTS)
that can be loaded from environment variables and updated at runtime.

Usage:
    from app.voice.config import get_voice_config, update_voice_config

    # Get current config
    config = get_voice_config()

    # Update at runtime
    config = update_voice_config({
        "stt_provider": "faster-whisper",
        "tts_voice": "af_bella",
    })
"""

import os
import logging
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class VoiceConfig:
    """
    Centralized voice configuration.

    Combines STT and TTS settings into a single configuration object
    that can be loaded from environment variables or updated at runtime.
    """

    # STT (Speech-to-Text) settings
    stt_provider: str = "faster-whisper"
    stt_model: str = "large-v3-turbo"
    stt_device: str = "auto"  # auto, cpu, cuda, mps
    stt_compute_type: str = "float16"  # float16, int8, float32
    stt_language: str = "en"

    # TTS (Text-to-Speech) settings
    tts_provider: str = "kokoro"
    tts_model: str = "kokoro-82m"
    tts_voice: str = "af_bella"
    tts_sample_rate: int = 24000
    tts_speed: float = 1.0

    # Custom model paths (optional)
    custom_stt_model_path: Optional[str] = None
    custom_tts_model_path: Optional[str] = None

    # VAD (Voice Activity Detection) settings
    vad_enabled: bool = True
    vad_threshold: float = 0.5
    vad_min_speech_duration_ms: int = 250
    vad_min_silence_duration_ms: int = 500

    # LiveKit settings
    livekit_url: str = "ws://localhost:7880"
    livekit_api_key: str = ""
    livekit_api_secret: str = ""

    @classmethod
    def from_env(cls) -> "VoiceConfig":
        """
        Create configuration from environment variables.

        Environment variables:
            VOICE_STT_PROVIDER: STT provider name
            VOICE_STT_MODEL: STT model name
            VOICE_STT_DEVICE: Device for STT (auto, cpu, cuda, mps)
            VOICE_STT_COMPUTE_TYPE: Compute type (float16, int8, float32)
            VOICE_STT_LANGUAGE: Default language code
            VOICE_TTS_PROVIDER: TTS provider name
            VOICE_TTS_MODEL: TTS model name
            VOICE_TTS_VOICE: Default voice ID
            VOICE_TTS_SAMPLE_RATE: Audio sample rate
            VOICE_TTS_SPEED: Speech speed multiplier
            VOICE_STT_MODEL_PATH: Custom STT model path
            VOICE_TTS_MODEL_PATH: Custom TTS model path
            VOICE_VAD_ENABLED: Enable VAD filtering
            VOICE_VAD_THRESHOLD: VAD confidence threshold
            LIVEKIT_URL: LiveKit server URL
            LIVEKIT_API_KEY: LiveKit API key
            LIVEKIT_API_SECRET: LiveKit API secret
        """
        return cls(
            # STT settings
            stt_provider=os.getenv("VOICE_STT_PROVIDER", "faster-whisper"),
            stt_model=os.getenv("VOICE_STT_MODEL", "large-v3-turbo"),
            stt_device=os.getenv("VOICE_STT_DEVICE", "auto"),
            stt_compute_type=os.getenv("VOICE_STT_COMPUTE_TYPE", "float16"),
            stt_language=os.getenv("VOICE_STT_LANGUAGE", "en"),

            # TTS settings
            tts_provider=os.getenv("VOICE_TTS_PROVIDER", "kokoro"),
            tts_model=os.getenv("VOICE_TTS_MODEL", "kokoro-82m"),
            tts_voice=os.getenv("VOICE_TTS_VOICE", "af_bella"),
            tts_sample_rate=int(os.getenv("VOICE_TTS_SAMPLE_RATE", "24000")),
            tts_speed=float(os.getenv("VOICE_TTS_SPEED", "1.0")),

            # Custom model paths
            custom_stt_model_path=os.getenv("VOICE_STT_MODEL_PATH"),
            custom_tts_model_path=os.getenv("VOICE_TTS_MODEL_PATH"),

            # VAD settings
            vad_enabled=os.getenv("VOICE_VAD_ENABLED", "true").lower() == "true",
            vad_threshold=float(os.getenv("VOICE_VAD_THRESHOLD", "0.5")),
            vad_min_speech_duration_ms=int(os.getenv("VOICE_VAD_MIN_SPEECH_MS", "250")),
            vad_min_silence_duration_ms=int(os.getenv("VOICE_VAD_MIN_SILENCE_MS", "500")),

            # LiveKit settings
            livekit_url=os.getenv("LIVEKIT_URL", "ws://localhost:7880"),
            livekit_api_key=os.getenv("LIVEKIT_API_KEY", ""),
            livekit_api_secret=os.getenv("LIVEKIT_API_SECRET", ""),
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VoiceConfig":
        """
        Create configuration from a dictionary.

        Args:
            data: Dictionary with configuration values

        Returns:
            VoiceConfig instance
        """
        # Start with defaults
        config = cls()

        # Update with provided values
        for key, value in data.items():
            if hasattr(config, key) and value is not None:
                setattr(config, key, value)

        return config

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert configuration to dictionary.

        Returns:
            Dictionary representation of config
        """
        return asdict(self)

    def update(self, updates: Dict[str, Any]) -> "VoiceConfig":
        """
        Update configuration with new values.

        Args:
            updates: Dictionary with values to update

        Returns:
            Self for chaining
        """
        for key, value in updates.items():
            if hasattr(self, key) and value is not None:
                setattr(self, key, value)
                logger.debug(f"Updated voice config: {key} = {value}")

        return self

    def get_stt_config(self) -> Dict[str, Any]:
        """Get STT-specific configuration as a dictionary."""
        return {
            "model": self.stt_model,
            "device": self.stt_device,
            "compute_type": self.stt_compute_type,
            "language": self.stt_language,
            "model_path": self.custom_stt_model_path,
            "vad_enabled": self.vad_enabled,
            "vad_threshold": self.vad_threshold,
        }

    def get_tts_config(self) -> Dict[str, Any]:
        """Get TTS-specific configuration as a dictionary."""
        return {
            "model": self.tts_model,
            "voice": self.tts_voice,
            "sample_rate": self.tts_sample_rate,
            "speed": self.tts_speed,
            "model_path": self.custom_tts_model_path,
        }


# Global configuration instance
_voice_config: Optional[VoiceConfig] = None


def get_voice_config() -> VoiceConfig:
    """
    Get the current voice configuration.

    Creates a new configuration from environment variables if none exists.

    Returns:
        VoiceConfig instance
    """
    global _voice_config

    if _voice_config is None:
        _voice_config = VoiceConfig.from_env()
        logger.info(
            f"Voice config initialized: "
            f"STT={_voice_config.stt_provider}/{_voice_config.stt_model}, "
            f"TTS={_voice_config.tts_provider}/{_voice_config.tts_voice}"
        )

    return _voice_config


def update_voice_config(updates: Dict[str, Any]) -> VoiceConfig:
    """
    Update the voice configuration at runtime.

    Args:
        updates: Dictionary with values to update

    Returns:
        Updated VoiceConfig instance
    """
    global _voice_config

    config = get_voice_config()
    config.update(updates)

    logger.info(f"Voice config updated: {list(updates.keys())}")

    return config


def reset_voice_config() -> VoiceConfig:
    """
    Reset voice configuration to defaults from environment.

    Returns:
        Fresh VoiceConfig instance
    """
    global _voice_config

    _voice_config = VoiceConfig.from_env()
    logger.info("Voice config reset to defaults")

    return _voice_config


def set_voice_config(config: VoiceConfig) -> None:
    """
    Set the global voice configuration.

    Args:
        config: VoiceConfig instance to use
    """
    global _voice_config
    _voice_config = config
    logger.info("Voice config replaced")
