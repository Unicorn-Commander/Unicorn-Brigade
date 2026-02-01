"""
Base classes for STT and TTS providers.

Provides abstract interfaces that all providers must implement,
ensuring consistent behavior across different backends.
"""

import asyncio
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncIterator, List, Optional, Dict, Any, Union
from pathlib import Path

logger = logging.getLogger(__name__)


# =============================================================================
# Enums
# =============================================================================

class DeviceType(str, Enum):
    """Compute device types."""
    AUTO = "auto"
    CPU = "cpu"
    CUDA = "cuda"
    MPS = "mps"  # Apple Metal Performance Shaders


class ComputeType(str, Enum):
    """Compute precision types."""
    FLOAT32 = "float32"
    FLOAT16 = "float16"
    INT8 = "int8"
    INT8_FLOAT16 = "int8_float16"


class ModelSize(str, Enum):
    """Whisper model sizes."""
    TINY = "tiny"
    TINY_EN = "tiny.en"
    BASE = "base"
    BASE_EN = "base.en"
    SMALL = "small"
    SMALL_EN = "small.en"
    MEDIUM = "medium"
    MEDIUM_EN = "medium.en"
    LARGE_V1 = "large-v1"
    LARGE_V2 = "large-v2"
    LARGE_V3 = "large-v3"
    LARGE_V3_TURBO = "large-v3-turbo"
    DISTIL_LARGE_V2 = "distil-large-v2"
    DISTIL_LARGE_V3 = "distil-large-v3"


# =============================================================================
# STT (Speech-to-Text) Base Classes
# =============================================================================

@dataclass
class STTSegment:
    """A segment of transcribed speech with timing information."""
    text: str
    start: float  # Start time in seconds
    end: float    # End time in seconds
    confidence: float = 1.0
    words: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class STTResult:
    """Result of a speech-to-text transcription."""
    text: str
    segments: List[STTSegment] = field(default_factory=list)
    language: Optional[str] = None
    language_probability: float = 0.0
    duration: float = 0.0
    # Extended metadata
    processing_time: float = 0.0
    model_used: str = ""
    provider: str = ""


@dataclass
class STTConfig:
    """Configuration for STT providers."""
    model: str = "base"
    language: Optional[str] = None
    device: str = "auto"  # auto, cpu, cuda, mps
    compute_type: str = "float16"  # float16, int8, float32
    beam_size: int = 5
    best_of: int = 5
    vad_enabled: bool = True
    vad_filter: bool = True
    vad_threshold: float = 0.5
    word_timestamps: bool = False
    # Audio settings
    sample_rate: int = 16000
    # VAD timing settings
    min_speech_duration_ms: int = 250
    min_silence_duration_ms: int = 500
    speech_pad_ms: int = 400
    # Streaming settings
    chunk_duration_ms: int = 1000
    overlap_duration_ms: int = 100
    # Model path
    model_dir: Optional[str] = None
    # Temperature for decoding
    temperature: float = 0.0
    # CoreML (whisper.cpp on Apple)
    coreml_enabled: bool = True
    # Quantization (MLX)
    quantization: Optional[str] = None

    @classmethod
    def from_env(cls) -> "STTConfig":
        """Create config from environment variables."""
        return cls(
            model=os.getenv("VOICE_STT_MODEL", "base"),
            language=os.getenv("VOICE_STT_LANGUAGE"),
            device=os.getenv("VOICE_STT_DEVICE", "auto"),
            compute_type=os.getenv("VOICE_STT_COMPUTE_TYPE", "float16"),
            vad_filter=os.getenv("VOICE_STT_VAD_FILTER", "true").lower() == "true",
            vad_threshold=float(os.getenv("VOICE_STT_VAD_THRESHOLD", "0.5")),
            model_dir=os.getenv("VOICE_STT_MODEL_DIR"),
            coreml_enabled=os.getenv("VOICE_STT_COREML", "true").lower() == "true",
        )


class STTProvider(ABC):
    """Abstract base class for Speech-to-Text providers."""

    def __init__(self, config: Optional[STTConfig] = None):
        """Initialize the provider with optional configuration."""
        self.config = config or STTConfig.from_env()
        self._initialized = False

    @abstractmethod
    async def transcribe(self, audio: bytes, language: Optional[str] = None, **kwargs) -> str:
        """
        Transcribe audio bytes to text.

        Args:
            audio: Audio data in bytes (WAV, PCM, or supported format)
            language: Optional language code (e.g., "en", "es")

        Returns:
            Transcribed text string
        """
        ...

    @abstractmethod
    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[bytes],
        language: Optional[str] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        Stream transcription for real-time speech recognition.

        Args:
            audio_stream: Async iterator of audio chunks
            language: Optional language code

        Yields:
            Transcribed text chunks as they become available
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for identification."""
        ...

    @property
    def supported_languages(self) -> List[str]:
        """List of supported language codes."""
        # Whisper supports 99+ languages
        return ["en", "es", "fr", "de", "it", "pt", "zh", "ja", "ko", "ru"]

    @property
    def sample_rate(self) -> int:
        """Expected audio sample rate in Hz."""
        return self.config.sample_rate

    @property
    def supports_streaming(self) -> bool:
        """Whether this provider supports streaming transcription."""
        return True

    @property
    def supports_word_timestamps(self) -> bool:
        """Whether this provider supports word-level timestamps."""
        return True

    @property
    def supports_vad(self) -> bool:
        """Whether this provider supports Voice Activity Detection."""
        return True

    async def initialize(self) -> None:
        """
        Initialize the provider (load models, etc.).

        Override this method for provider-specific initialization.
        """
        self._initialized = True

    async def shutdown(self) -> None:
        """
        Clean up provider resources.

        Override this method to release model memory, close connections, etc.
        """
        self._initialized = False

    async def __aenter__(self) -> "STTProvider":
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.shutdown()

    def _detect_device(self) -> str:
        """
        Detect the best available compute device.

        Returns:
            Device string: "cuda", "mps", or "cpu"
        """
        if self.config.device != "auto":
            return self.config.device

        # Check for CUDA
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
        except ImportError:
            pass

        # Check for MPS (Apple Silicon)
        try:
            import torch
            if torch.backends.mps.is_available():
                return "mps"
        except (ImportError, AttributeError):
            pass

        # Check for Apple Silicon without torch
        import platform
        if platform.system() == "Darwin" and platform.machine() == "arm64":
            return "mps"

        return "cpu"

    def _validate_audio(self, audio: bytes) -> bytes:
        """
        Validate and potentially convert audio to expected format.

        Args:
            audio: Raw audio bytes

        Returns:
            Validated/converted audio bytes

        Raises:
            ValueError: If audio format is invalid
        """
        if not audio:
            raise ValueError("Empty audio data")

        # Basic validation - ensure we have at least some audio
        min_bytes = self.config.sample_rate * 2 // 10  # 100ms minimum
        if len(audio) < min_bytes:
            raise ValueError(f"Audio too short: {len(audio)} bytes (minimum {min_bytes})")

        return audio

    def _get_model_path(self) -> str:
        """
        Get the path to the model directory or download location.

        Returns:
            Model directory path
        """
        if self.config.model_dir:
            return self.config.model_dir

        # Default model cache directory
        cache_dir = os.path.expanduser("~/.cache/unicorn-brigade/models/whisper")
        os.makedirs(cache_dir, exist_ok=True)
        return cache_dir


class STTProviderError(Exception):
    """Exception raised by STT providers."""
    pass


# =============================================================================
# TTS (Text-to-Speech) Base Classes
# =============================================================================

@dataclass
class TTSConfig:
    """Configuration for TTS providers."""
    voice: Optional[str] = None
    sample_rate: int = 24000
    language: str = "en"
    speed: float = 1.0
    pitch: float = 1.0
    # Voice cloning settings
    voice_sample_path: Optional[str] = None
    # Model settings
    model_path: Optional[str] = None
    device: str = "auto"  # auto, cpu, cuda, mps, mlx


class TTSProvider(ABC):
    """
    Abstract base class for Text-to-Speech providers.

    All TTS providers must implement this interface to ensure
    consistent behavior across different backends.
    """

    def __init__(self, config: Optional[TTSConfig] = None):
        """
        Initialize the TTS provider.

        Args:
            config: Optional TTSConfig with provider settings
        """
        self.config = config or TTSConfig()
        self._initialized = False

    async def initialize(self) -> None:
        """
        Initialize the provider (load models, etc.).

        Override this method if the provider requires async initialization.
        """
        self._initialized = True

    async def cleanup(self) -> None:
        """
        Clean up provider resources.

        Override this method to release model memory, close connections, etc.
        """
        self._initialized = False

    @abstractmethod
    async def synthesize(self, text: str, voice: Optional[str] = None) -> bytes:
        """
        Synthesize speech from text.

        Args:
            text: The text to synthesize
            voice: Optional voice ID (overrides config.voice)

        Returns:
            Audio data as bytes (PCM format at provider's sample_rate)
        """
        ...

    @abstractmethod
    async def synthesize_stream(
        self,
        text: str,
        voice: Optional[str] = None,
    ) -> AsyncIterator[bytes]:
        """
        Stream synthesized speech for real-time playback.

        Args:
            text: The text to synthesize
            voice: Optional voice ID (overrides config.voice)

        Yields:
            Audio chunks as bytes (PCM format)
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for identification."""
        ...

    @property
    @abstractmethod
    def available_voices(self) -> List[str]:
        """List of available voice IDs."""
        ...

    @property
    def supports_voice_cloning(self) -> bool:
        """Whether this provider supports voice cloning."""
        return False

    @property
    def supports_emotion_control(self) -> bool:
        """Whether this provider supports emotion/style control."""
        return False

    @property
    def supports_streaming(self) -> bool:
        """Whether this provider supports streaming synthesis."""
        return True

    @property
    def sample_rate(self) -> int:
        """Audio sample rate in Hz."""
        return self.config.sample_rate

    @property
    def default_voice(self) -> Optional[str]:
        """Default voice ID if none specified."""
        voices = self.available_voices
        return voices[0] if voices else None

    async def clone_voice(
        self,
        audio_sample: Union[bytes, str, Path],
        voice_name: Optional[str] = None,
    ) -> str:
        """
        Create a cloned voice from an audio sample.

        Args:
            audio_sample: Audio data (bytes) or path to audio file
            voice_name: Optional name for the cloned voice

        Returns:
            Voice ID for the cloned voice

        Raises:
            NotImplementedError: If provider doesn't support voice cloning
        """
        raise NotImplementedError(f"{self.name} does not support voice cloning")

    def get_voice_info(self, voice_id: str) -> Dict[str, Any]:
        """
        Get information about a specific voice.

        Args:
            voice_id: The voice ID to look up

        Returns:
            Dictionary with voice metadata (name, language, style, etc.)
        """
        return {"id": voice_id, "name": voice_id}


class TTSProviderError(Exception):
    """Exception raised by TTS providers."""

    def __init__(self, message: str, provider: Optional[str] = None, cause: Optional[Exception] = None):
        self.provider = provider
        self.cause = cause
        super().__init__(message)


# =============================================================================
# Utility Functions
# =============================================================================

def detect_device() -> str:
    """
    Auto-detect the best available device for inference.

    Returns:
        Device string: 'cuda', 'mps', 'mlx', or 'cpu'
    """
    # Check for CUDA
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
    except ImportError:
        pass

    # Check for Apple Silicon MPS
    try:
        import torch
        if torch.backends.mps.is_available():
            return "mps"
    except (ImportError, AttributeError):
        pass

    # Check for MLX (Apple Silicon)
    try:
        import mlx.core as mx
        # MLX only works on Apple Silicon
        import platform
        if platform.processor() == "arm":
            return "mlx"
    except ImportError:
        pass

    return "cpu"


def audio_to_pcm(
    audio_bytes: bytes,
    input_format: str = "wav",
    target_sample_rate: int = 24000,
    target_channels: int = 1,
) -> bytes:
    """
    Convert audio bytes to PCM format.

    Args:
        audio_bytes: Input audio data
        input_format: Input format (wav, mp3, ogg, etc.)
        target_sample_rate: Target sample rate in Hz
        target_channels: Number of output channels (1=mono, 2=stereo)

    Returns:
        PCM audio data as bytes
    """
    try:
        import soundfile as sf
        import numpy as np
        import io

        # Read audio
        data, sample_rate = sf.read(io.BytesIO(audio_bytes))

        # Convert to mono if needed
        if len(data.shape) > 1 and target_channels == 1:
            data = np.mean(data, axis=1)

        # Resample if needed
        if sample_rate != target_sample_rate:
            try:
                import resampy
                data = resampy.resample(data, sample_rate, target_sample_rate)
            except ImportError:
                logger.warning("resampy not installed, skipping resampling")

        # Convert to int16 PCM
        data = (data * 32767).astype(np.int16)

        return data.tobytes()

    except ImportError:
        logger.warning("soundfile not installed, returning raw bytes")
        return audio_bytes


def pcm_to_wav(
    pcm_bytes: bytes,
    sample_rate: int = 24000,
    channels: int = 1,
    bits_per_sample: int = 16,
) -> bytes:
    """
    Convert PCM bytes to WAV format with proper headers.

    Args:
        pcm_bytes: Raw PCM audio data
        sample_rate: Sample rate in Hz
        channels: Number of channels
        bits_per_sample: Bits per sample (usually 16)

    Returns:
        WAV file as bytes
    """
    import struct

    byte_rate = sample_rate * channels * bits_per_sample // 8
    block_align = channels * bits_per_sample // 8
    data_size = len(pcm_bytes)

    # WAV header
    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF',
        36 + data_size,  # File size minus 8
        b'WAVE',
        b'fmt ',
        16,  # Subchunk1Size (PCM)
        1,   # AudioFormat (PCM)
        channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b'data',
        data_size,
    )

    return header + pcm_bytes
