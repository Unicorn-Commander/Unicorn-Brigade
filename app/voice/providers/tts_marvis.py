"""
Marvis TTS Provider (Apple Silicon Native with MLX).

Marvis TTS is optimized for Apple Silicon using MLX (Metal acceleration).
It provides real-time streaming synthesis with natural, expressive voices.

Features:
- Native Metal acceleration via MLX framework
- Real-time streaming synthesis
- Two expressive voices (af_sky, am_michael)
- Low latency (~50ms first byte)
- Optimized for M1/M2/M3 chips

Requirements:
- Apple Silicon Mac (M1, M2, M3, or newer)
- macOS 12.0 or later
- MLX framework

Installation:
    pip install mlx-audio

Usage:
    from app.voice.providers.tts_marvis import MarvisTTSProvider

    provider = MarvisTTSProvider()
    await provider.initialize()

    # Streaming synthesis (recommended for real-time)
    async for chunk in provider.synthesize_stream("Hello world!"):
        play_audio(chunk)

    # Full synthesis
    audio = await provider.synthesize("Hello world!")
"""

import asyncio
import logging
import os
import platform
from typing import AsyncIterator, List, Optional, Dict, Any

from app.voice.providers.base import TTSProvider, TTSConfig, TTSProviderError

logger = logging.getLogger(__name__)


class MarvisTTSProvider(TTSProvider):
    """
    Marvis Text-to-Speech provider with native Apple Silicon support.

    Uses MLX for Metal-accelerated inference, providing low-latency
    synthesis optimized for M-series chips.
    """

    # Available voices
    VOICES = {
        "af_sky": {
            "name": "Sky",
            "gender": "female",
            "style": "calm",
            "description": "Calm and soothing female voice",
        },
        "am_michael": {
            "name": "Michael",
            "gender": "male",
            "style": "friendly",
            "description": "Friendly and conversational male voice",
        },
    }

    DEFAULT_VOICE = "af_sky"
    SAMPLE_RATE = 24000

    def __init__(self, config: Optional[TTSConfig] = None):
        """
        Initialize the Marvis TTS provider.

        Args:
            config: Optional TTSConfig with settings
        """
        super().__init__(config)
        self._model = None
        self._processor = None

        # Check for Apple Silicon
        if platform.system() != "Darwin" or platform.processor() not in ("arm", "arm64"):
            logger.warning(
                "Marvis TTS is optimized for Apple Silicon. "
                "Performance may be degraded on other platforms."
            )

        # Override sample rate
        self.config.sample_rate = self.SAMPLE_RATE

    async def initialize(self) -> None:
        """Load the Marvis model using MLX."""
        if self._initialized:
            return

        try:
            # Import MLX and mlx-audio
            import mlx.core as mx
            from mlx_audio.tts import load_model, TextProcessor

            # Load model
            logger.info("Loading Marvis TTS model with MLX...")
            self._model = load_model("marvis-tts")
            self._processor = TextProcessor()

            # Warm up with a short synthesis
            _ = self._model.generate(
                self._processor("Hello"),
                voice=self.DEFAULT_VOICE,
            )

            logger.info("Marvis TTS model loaded and warmed up")
            self._initialized = True

        except ImportError as e:
            raise TTSProviderError(
                "MLX Audio not installed. Install with: pip install mlx-audio\n"
                "Note: MLX only works on Apple Silicon Macs.",
                provider=self.name,
                cause=e,
            )
        except Exception as e:
            raise TTSProviderError(
                f"Failed to initialize Marvis TTS: {e}",
                provider=self.name,
                cause=e,
            )

    async def cleanup(self) -> None:
        """Clean up model resources."""
        self._model = None
        self._processor = None
        self._initialized = False

    async def synthesize(self, text: str, voice: Optional[str] = None) -> bytes:
        """
        Synthesize speech from text.

        Args:
            text: The text to synthesize
            voice: Voice ID ("af_sky" or "am_michael")

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
            import mlx.core as mx
            import numpy as np

            loop = asyncio.get_event_loop()

            # Run synthesis in thread pool
            def _synthesize():
                # Process text
                tokens = self._processor(text)

                # Generate audio
                audio = self._model.generate(
                    tokens,
                    voice=voice_id,
                    speed=self.config.speed,
                )

                # Convert to numpy
                audio_np = np.array(audio)

                # Convert to int16 PCM
                return (audio_np * 32767).astype(np.int16).tobytes()

            audio = await loop.run_in_executor(None, _synthesize)
            return audio

        except Exception as e:
            raise TTSProviderError(
                f"Synthesis failed: {e}",
                provider=self.name,
                cause=e,
            )

    async def synthesize_stream(
        self,
        text: str,
        voice: Optional[str] = None,
    ) -> AsyncIterator[bytes]:
        """
        Stream synthesized speech in real-time.

        Marvis supports true streaming synthesis with MLX,
        yielding audio chunks as they are generated.

        Args:
            text: The text to synthesize
            voice: Voice ID

        Yields:
            Audio chunks (PCM bytes)
        """
        if not self._initialized:
            await self.initialize()

        voice_id = voice or self.config.voice or self.DEFAULT_VOICE

        if voice_id not in self.VOICES:
            voice_id = self.DEFAULT_VOICE

        try:
            import mlx.core as mx
            import numpy as np

            # Process text
            tokens = self._processor(text)

            # Check if model supports streaming
            if hasattr(self._model, "generate_stream"):
                # Native streaming
                async for chunk in self._stream_native(tokens, voice_id):
                    yield chunk
            else:
                # Fall back to chunked synthesis
                audio = await self.synthesize(text, voice)

                # Yield in 20ms chunks
                chunk_samples = int(self.SAMPLE_RATE * 0.02)
                chunk_bytes = chunk_samples * 2

                for i in range(0, len(audio), chunk_bytes):
                    chunk = audio[i:i + chunk_bytes]
                    if chunk:
                        yield chunk
                        await asyncio.sleep(0.005)  # Small delay for flow control

        except Exception as e:
            raise TTSProviderError(
                f"Streaming synthesis failed: {e}",
                provider=self.name,
                cause=e,
            )

    async def _stream_native(
        self,
        tokens: Any,
        voice_id: str,
    ) -> AsyncIterator[bytes]:
        """Native streaming using MLX's stream API."""
        import mlx.core as mx
        import numpy as np

        loop = asyncio.get_event_loop()
        queue = asyncio.Queue()
        finished = asyncio.Event()

        def generate_chunks():
            """Generate audio chunks in a thread."""
            try:
                for chunk in self._model.generate_stream(
                    tokens,
                    voice=voice_id,
                    speed=self.config.speed,
                ):
                    # Evaluate MLX array (forces computation)
                    mx.eval(chunk)

                    # Convert to numpy and then to PCM
                    chunk_np = np.array(chunk)
                    chunk_int16 = (chunk_np * 32767).astype(np.int16)

                    asyncio.run_coroutine_threadsafe(
                        queue.put(chunk_int16.tobytes()),
                        loop,
                    )
            finally:
                asyncio.run_coroutine_threadsafe(finished.set(), loop)

        # Start generation
        loop.run_in_executor(None, generate_chunks)

        # Yield chunks
        while not finished.is_set() or not queue.empty():
            try:
                chunk = await asyncio.wait_for(queue.get(), timeout=0.05)
                yield chunk
            except asyncio.TimeoutError:
                continue

    @property
    def name(self) -> str:
        """Provider name."""
        return "marvis"

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
        """Marvis does not support voice cloning."""
        return False

    @property
    def supports_streaming(self) -> bool:
        """Marvis supports real-time streaming."""
        return True

    def get_voice_info(self, voice_id: str) -> Dict[str, Any]:
        """Get information about a voice."""
        if voice_id in self.VOICES:
            info = self.VOICES[voice_id].copy()
            info["id"] = voice_id
            return info
        return {"id": voice_id, "name": voice_id}

    @staticmethod
    def is_available() -> bool:
        """Check if Marvis TTS is available on this system."""
        # Check for Apple Silicon
        if platform.system() != "Darwin":
            return False

        if platform.processor() not in ("arm", "arm64"):
            return False

        # Check for MLX
        try:
            import mlx.core
            return True
        except ImportError:
            return False
