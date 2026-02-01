"""
Kokoro-82M TTS Provider.

Kokoro is a lightweight (82M parameters), high-quality text-to-speech model
that runs efficiently on CPU. It provides natural-sounding speech with
multiple preset voices.

Features:
- 82M parameters - runs on CPU without GPU
- High-quality audio output at 24kHz
- Multiple expressive voices (American & British English)
- Apache 2.0 license
- Fast inference (~0.5x realtime on modern CPU)

Voices:
- af_bella: American female, warm and expressive
- af_heart: American female, soft and friendly
- af_nicole: American female, clear and professional
- af_sarah: American female, energetic
- af_sky: American female, calm and soothing
- am_adam: American male, deep and authoritative
- am_michael: American male, friendly and conversational
- bf_emma: British female, refined and articulate
- bf_isabella: British female, warm and elegant
- bm_george: British male, classic and distinguished
- bm_lewis: British male, modern and engaging

Installation:
    pip install kokoro>=0.9.2

    # Or for ONNX runtime (faster on CPU):
    pip install kokoro-onnx

Usage:
    from app.voice.providers.tts_kokoro import KokoroTTSProvider

    provider = KokoroTTSProvider()
    await provider.initialize()

    audio = await provider.synthesize("Hello world!", voice="af_bella")
"""

import asyncio
import logging
import os
from typing import AsyncIterator, List, Optional, Dict, Any

from app.voice.providers.base import TTSProvider, TTSConfig, TTSProviderError

logger = logging.getLogger(__name__)


class KokoroTTSProvider(TTSProvider):
    """
    Kokoro-82M Text-to-Speech provider.

    A lightweight, high-quality TTS model that runs efficiently on CPU.
    Supports multiple preset voices with natural prosody.
    """

    # Available preset voices
    VOICES = {
        # American Female
        "af_bella": {"name": "Bella", "gender": "female", "accent": "american", "style": "warm"},
        "af_heart": {"name": "Heart", "gender": "female", "accent": "american", "style": "soft"},
        "af_nicole": {"name": "Nicole", "gender": "female", "accent": "american", "style": "professional"},
        "af_sarah": {"name": "Sarah", "gender": "female", "accent": "american", "style": "energetic"},
        "af_sky": {"name": "Sky", "gender": "female", "accent": "american", "style": "calm"},
        # American Male
        "am_adam": {"name": "Adam", "gender": "male", "accent": "american", "style": "authoritative"},
        "am_michael": {"name": "Michael", "gender": "male", "accent": "american", "style": "friendly"},
        # British Female
        "bf_emma": {"name": "Emma", "gender": "female", "accent": "british", "style": "refined"},
        "bf_isabella": {"name": "Isabella", "gender": "female", "accent": "british", "style": "elegant"},
        # British Male
        "bm_george": {"name": "George", "gender": "male", "accent": "british", "style": "classic"},
        "bm_lewis": {"name": "Lewis", "gender": "male", "accent": "british", "style": "modern"},
    }

    DEFAULT_VOICE = "af_bella"
    SAMPLE_RATE = 24000

    def __init__(self, config: Optional[TTSConfig] = None):
        """
        Initialize the Kokoro TTS provider.

        Args:
            config: Optional TTSConfig with settings
        """
        super().__init__(config)
        self._model = None
        self._use_onnx = False

        # Override sample rate to Kokoro's native rate
        self.config.sample_rate = self.SAMPLE_RATE

    async def initialize(self) -> None:
        """Load the Kokoro model."""
        if self._initialized:
            return

        try:
            # Try ONNX version first (faster on CPU)
            try:
                from kokoro_onnx import Kokoro
                self._model = Kokoro()
                self._use_onnx = True
                logger.info("Loaded Kokoro ONNX model")
            except ImportError:
                # Fall back to PyTorch version
                from kokoro import KokoroPipeline
                device = self.config.device if self.config.device != "auto" else "cpu"
                self._model = KokoroPipeline(device=device)
                self._use_onnx = False
                logger.info(f"Loaded Kokoro PyTorch model on {device}")

            self._initialized = True

        except ImportError as e:
            raise TTSProviderError(
                "Kokoro not installed. Install with: pip install kokoro>=0.9.2 or pip install kokoro-onnx",
                provider=self.name,
                cause=e,
            )
        except Exception as e:
            raise TTSProviderError(
                f"Failed to initialize Kokoro: {e}",
                provider=self.name,
                cause=e,
            )

    async def cleanup(self) -> None:
        """Clean up model resources."""
        self._model = None
        self._initialized = False

    async def synthesize(self, text: str, voice: Optional[str] = None) -> bytes:
        """
        Synthesize speech from text.

        Args:
            text: The text to synthesize
            voice: Voice ID (e.g., "af_bella", "am_adam")

        Returns:
            PCM audio bytes at 24kHz, 16-bit mono
        """
        if not self._initialized:
            await self.initialize()

        voice_id = voice or self.config.voice or self.DEFAULT_VOICE

        # Validate voice
        if voice_id not in self.VOICES:
            logger.warning(f"Unknown voice '{voice_id}', using default '{self.DEFAULT_VOICE}'")
            voice_id = self.DEFAULT_VOICE

        try:
            # Run synthesis in thread pool to avoid blocking
            loop = asyncio.get_event_loop()

            if self._use_onnx:
                audio = await loop.run_in_executor(
                    None,
                    lambda: self._synthesize_onnx(text, voice_id),
                )
            else:
                audio = await loop.run_in_executor(
                    None,
                    lambda: self._synthesize_pytorch(text, voice_id),
                )

            return audio

        except Exception as e:
            raise TTSProviderError(
                f"Synthesis failed: {e}",
                provider=self.name,
                cause=e,
            )

    def _synthesize_onnx(self, text: str, voice_id: str) -> bytes:
        """Synthesize using ONNX runtime."""
        import numpy as np

        # Generate audio
        samples, sample_rate = self._model.create(
            text,
            voice=voice_id,
            speed=self.config.speed,
        )

        # Convert to int16 PCM
        audio_int16 = (samples * 32767).astype(np.int16)
        return audio_int16.tobytes()

    def _synthesize_pytorch(self, text: str, voice_id: str) -> bytes:
        """Synthesize using PyTorch."""
        import numpy as np

        # Generate audio
        audio = self._model.generate(
            text,
            voice=voice_id,
            speed=self.config.speed,
        )

        # Ensure numpy array
        if hasattr(audio, "numpy"):
            audio = audio.numpy()

        # Convert to int16 PCM
        audio_int16 = (audio * 32767).astype(np.int16)
        return audio_int16.tobytes()

    async def synthesize_stream(
        self,
        text: str,
        voice: Optional[str] = None,
    ) -> AsyncIterator[bytes]:
        """
        Stream synthesized speech.

        Kokoro doesn't natively support streaming, so we synthesize
        the full audio and yield it in chunks for consistent API.

        Args:
            text: The text to synthesize
            voice: Voice ID

        Yields:
            Audio chunks (PCM bytes)
        """
        # Synthesize full audio
        audio = await self.synthesize(text, voice)

        # Yield in ~20ms chunks at 24kHz
        chunk_samples = int(self.SAMPLE_RATE * 0.02)  # 20ms
        chunk_bytes = chunk_samples * 2  # 16-bit = 2 bytes per sample

        for i in range(0, len(audio), chunk_bytes):
            chunk = audio[i:i + chunk_bytes]
            if chunk:
                yield chunk
                # Small delay to simulate real-time streaming
                await asyncio.sleep(0.01)

    @property
    def name(self) -> str:
        """Provider name."""
        return "kokoro"

    @property
    def available_voices(self) -> List[str]:
        """List of available voice IDs."""
        return list(self.VOICES.keys())

    @property
    def sample_rate(self) -> int:
        """Audio sample rate (24kHz)."""
        return self.SAMPLE_RATE

    @property
    def supports_voice_cloning(self) -> bool:
        """Kokoro does not support voice cloning."""
        return False

    @property
    def supports_streaming(self) -> bool:
        """Streaming is simulated by chunking."""
        return True

    def get_voice_info(self, voice_id: str) -> Dict[str, Any]:
        """Get information about a voice."""
        if voice_id in self.VOICES:
            info = self.VOICES[voice_id].copy()
            info["id"] = voice_id
            return info
        return {"id": voice_id, "name": voice_id}

    def get_voices_by_gender(self, gender: str) -> List[str]:
        """Get voice IDs filtered by gender."""
        return [
            vid for vid, info in self.VOICES.items()
            if info["gender"] == gender.lower()
        ]

    def get_voices_by_accent(self, accent: str) -> List[str]:
        """Get voice IDs filtered by accent."""
        return [
            vid for vid, info in self.VOICES.items()
            if info["accent"] == accent.lower()
        ]
