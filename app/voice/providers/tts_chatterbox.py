"""
Chatterbox TTS Provider.

Chatterbox is a state-of-the-art text-to-speech model with voice cloning
and emotion control capabilities. It can clone any voice from a 5-10 second
audio sample.

Features:
- Voice cloning from 5-10 second samples
- Emotion exaggeration control (0.0 to 1.0+)
- Paralinguistic tags: [laugh], [cough], [sigh], [gasp], [clear throat]
- Natural prosody and intonation
- MIT license

Models:
- chatterbox: Full model with best quality
- chatterbox-turbo: Faster inference with slightly lower quality

Installation:
    pip install chatterbox-tts

Usage:
    from app.voice.providers.tts_chatterbox import ChatterboxTTSProvider

    # Basic usage with default voice
    provider = ChatterboxTTSProvider()
    await provider.initialize()
    audio = await provider.synthesize("Hello! [laugh] That's funny.")

    # With voice cloning
    config = TTSConfig(voice_sample_path="/path/to/sample.wav")
    provider = ChatterboxTTSProvider(config)
    await provider.initialize()
    cloned_voice = await provider.clone_voice("/path/to/sample.wav", "my_voice")
    audio = await provider.synthesize("Hello in my cloned voice!", voice=cloned_voice)

    # With emotion control
    audio = await provider.synthesize_with_emotion(
        "I'm so excited!",
        emotion_exaggeration=0.8,
    )
"""

import asyncio
import logging
import os
import uuid
import tempfile
from pathlib import Path
from typing import AsyncIterator, List, Optional, Dict, Any, Union

from app.voice.providers.base import TTSProvider, TTSConfig, TTSProviderError

logger = logging.getLogger(__name__)


class ChatterboxTTSProvider(TTSProvider):
    """
    Chatterbox Text-to-Speech provider with voice cloning.

    Supports emotion control and paralinguistic tags for
    natural-sounding speech synthesis.
    """

    # Paralinguistic tags supported by Chatterbox
    PARALINGUISTIC_TAGS = [
        "[laugh]",
        "[cough]",
        "[sigh]",
        "[gasp]",
        "[clear throat]",
        "[hmm]",
        "[uh]",
        "[um]",
    ]

    DEFAULT_VOICE = "default"
    SAMPLE_RATE = 24000

    def __init__(
        self,
        config: Optional[TTSConfig] = None,
        model: str = "chatterbox",  # or "chatterbox-turbo"
        emotion_exaggeration: float = 0.5,
    ):
        """
        Initialize the Chatterbox TTS provider.

        Args:
            config: Optional TTSConfig with settings
            model: Model variant ("chatterbox" or "chatterbox-turbo")
            emotion_exaggeration: Default emotion intensity (0.0 to 1.0+)
        """
        super().__init__(config)
        self._model_name = model
        self._emotion_exaggeration = emotion_exaggeration
        self._model = None
        self._cloned_voices: Dict[str, Any] = {}

        # Override sample rate
        self.config.sample_rate = self.SAMPLE_RATE

    async def initialize(self) -> None:
        """Load the Chatterbox model."""
        if self._initialized:
            return

        try:
            from chatterbox.tts import ChatterboxTTS

            # Determine device
            device = self.config.device
            if device == "auto":
                from app.voice.providers.base import detect_device
                device = detect_device()
                if device == "mlx":
                    device = "cpu"  # Chatterbox doesn't support MLX

            # Load model
            if self._model_name == "chatterbox-turbo":
                self._model = ChatterboxTTS.from_pretrained(
                    "resemble-ai/chatterbox-turbo",
                    device=device,
                )
            else:
                self._model = ChatterboxTTS.from_pretrained(
                    "resemble-ai/chatterbox",
                    device=device,
                )

            logger.info(f"Loaded Chatterbox model '{self._model_name}' on {device}")

            # Load voice sample if provided
            if self.config.voice_sample_path:
                voice_id = await self.clone_voice(
                    self.config.voice_sample_path,
                    voice_name="config_voice",
                )
                self.config.voice = voice_id

            self._initialized = True

        except ImportError as e:
            raise TTSProviderError(
                "Chatterbox not installed. Install with: pip install chatterbox-tts",
                provider=self.name,
                cause=e,
            )
        except Exception as e:
            raise TTSProviderError(
                f"Failed to initialize Chatterbox: {e}",
                provider=self.name,
                cause=e,
            )

    async def cleanup(self) -> None:
        """Clean up model resources."""
        self._model = None
        self._cloned_voices.clear()
        self._initialized = False

    async def synthesize(self, text: str, voice: Optional[str] = None) -> bytes:
        """
        Synthesize speech from text.

        Supports paralinguistic tags like [laugh], [cough], etc.

        Args:
            text: The text to synthesize (can include paralinguistic tags)
            voice: Voice ID (use cloned voice ID or "default")

        Returns:
            PCM audio bytes at 24kHz, 16-bit mono
        """
        return await self.synthesize_with_emotion(
            text,
            voice=voice,
            emotion_exaggeration=self._emotion_exaggeration,
        )

    async def synthesize_with_emotion(
        self,
        text: str,
        voice: Optional[str] = None,
        emotion_exaggeration: float = 0.5,
    ) -> bytes:
        """
        Synthesize speech with emotion control.

        Args:
            text: The text to synthesize
            voice: Voice ID
            emotion_exaggeration: Emotion intensity (0.0=neutral, 1.0=expressive)

        Returns:
            PCM audio bytes
        """
        if not self._initialized:
            await self.initialize()

        voice_id = voice or self.config.voice or self.DEFAULT_VOICE

        try:
            loop = asyncio.get_event_loop()

            # Get voice embedding if using cloned voice
            voice_embedding = None
            if voice_id in self._cloned_voices:
                voice_embedding = self._cloned_voices[voice_id]

            audio = await loop.run_in_executor(
                None,
                lambda: self._synthesize_internal(
                    text,
                    voice_embedding,
                    emotion_exaggeration,
                ),
            )

            return audio

        except Exception as e:
            raise TTSProviderError(
                f"Synthesis failed: {e}",
                provider=self.name,
                cause=e,
            )

    def _synthesize_internal(
        self,
        text: str,
        voice_embedding: Optional[Any],
        emotion_exaggeration: float,
    ) -> bytes:
        """Internal synthesis method (runs in thread pool)."""
        import numpy as np

        # Generate audio
        if voice_embedding is not None:
            audio = self._model.generate(
                text,
                speaker_embedding=voice_embedding,
                exaggeration=emotion_exaggeration,
            )
        else:
            audio = self._model.generate(
                text,
                exaggeration=emotion_exaggeration,
            )

        # Convert to numpy if tensor
        if hasattr(audio, "numpy"):
            audio = audio.numpy()
        elif hasattr(audio, "cpu"):
            audio = audio.cpu().numpy()

        # Flatten if needed
        if len(audio.shape) > 1:
            audio = audio.flatten()

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

        Args:
            text: The text to synthesize
            voice: Voice ID

        Yields:
            Audio chunks (PCM bytes)
        """
        if not self._initialized:
            await self.initialize()

        voice_id = voice or self.config.voice or self.DEFAULT_VOICE
        voice_embedding = self._cloned_voices.get(voice_id)

        try:
            # Chatterbox supports streaming through its generate_stream method
            loop = asyncio.get_event_loop()

            # Check if streaming is supported
            if hasattr(self._model, "generate_stream"):
                # Use native streaming
                async for chunk in self._stream_native(text, voice_embedding):
                    yield chunk
            else:
                # Fall back to chunked full synthesis
                audio = await self.synthesize(text, voice)

                chunk_samples = int(self.SAMPLE_RATE * 0.02)
                chunk_bytes = chunk_samples * 2

                for i in range(0, len(audio), chunk_bytes):
                    chunk = audio[i:i + chunk_bytes]
                    if chunk:
                        yield chunk
                        await asyncio.sleep(0.01)

        except Exception as e:
            raise TTSProviderError(
                f"Streaming synthesis failed: {e}",
                provider=self.name,
                cause=e,
            )

    async def _stream_native(
        self,
        text: str,
        voice_embedding: Optional[Any],
    ) -> AsyncIterator[bytes]:
        """Native streaming using Chatterbox's stream API."""
        import numpy as np

        loop = asyncio.get_event_loop()

        # Create a queue for chunks
        queue = asyncio.Queue()
        finished = asyncio.Event()

        def generate_chunks():
            """Run generation in thread and put chunks in queue."""
            try:
                for chunk in self._model.generate_stream(
                    text,
                    speaker_embedding=voice_embedding,
                    exaggeration=self._emotion_exaggeration,
                ):
                    # Convert chunk to PCM
                    if hasattr(chunk, "numpy"):
                        chunk = chunk.numpy()
                    elif hasattr(chunk, "cpu"):
                        chunk = chunk.cpu().numpy()

                    if len(chunk.shape) > 1:
                        chunk = chunk.flatten()

                    chunk_int16 = (chunk * 32767).astype(np.int16)
                    asyncio.run_coroutine_threadsafe(
                        queue.put(chunk_int16.tobytes()),
                        loop,
                    )
            finally:
                asyncio.run_coroutine_threadsafe(finished.set(), loop)

        # Start generation in background
        loop.run_in_executor(None, generate_chunks)

        # Yield chunks as they become available
        while not finished.is_set() or not queue.empty():
            try:
                chunk = await asyncio.wait_for(queue.get(), timeout=0.1)
                yield chunk
            except asyncio.TimeoutError:
                continue

    async def clone_voice(
        self,
        audio_sample: Union[bytes, str, Path],
        voice_name: Optional[str] = None,
    ) -> str:
        """
        Clone a voice from an audio sample.

        Args:
            audio_sample: Path to audio file or audio bytes (5-10 seconds recommended)
            voice_name: Optional name for the cloned voice

        Returns:
            Voice ID for the cloned voice
        """
        if not self._initialized:
            await self.initialize()

        # Generate voice ID
        voice_id = voice_name or f"cloned_{uuid.uuid4().hex[:8]}"

        try:
            loop = asyncio.get_event_loop()

            # Handle different input types
            if isinstance(audio_sample, (str, Path)):
                audio_path = str(audio_sample)
            else:
                # Write bytes to temp file
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    f.write(audio_sample)
                    audio_path = f.name

            # Extract voice embedding
            embedding = await loop.run_in_executor(
                None,
                lambda: self._model.extract_speaker_embedding(audio_path),
            )

            # Store embedding
            self._cloned_voices[voice_id] = embedding

            logger.info(f"Cloned voice '{voice_id}' from {audio_path}")
            return voice_id

        except Exception as e:
            raise TTSProviderError(
                f"Voice cloning failed: {e}",
                provider=self.name,
                cause=e,
            )

    @property
    def name(self) -> str:
        """Provider name."""
        return f"chatterbox-{self._model_name.split('-')[-1] if '-' in self._model_name else 'full'}"

    @property
    def available_voices(self) -> List[str]:
        """List of available voice IDs (default + cloned)."""
        voices = [self.DEFAULT_VOICE]
        voices.extend(self._cloned_voices.keys())
        return voices

    @property
    def sample_rate(self) -> int:
        """Audio sample rate (24kHz)."""
        return self.SAMPLE_RATE

    @property
    def supports_voice_cloning(self) -> bool:
        """Chatterbox supports voice cloning."""
        return True

    @property
    def supports_emotion_control(self) -> bool:
        """Chatterbox supports emotion control."""
        return True

    @property
    def supports_streaming(self) -> bool:
        """Chatterbox supports streaming."""
        return True

    def get_voice_info(self, voice_id: str) -> Dict[str, Any]:
        """Get information about a voice."""
        if voice_id == self.DEFAULT_VOICE:
            return {
                "id": voice_id,
                "name": "Default",
                "cloned": False,
            }
        elif voice_id in self._cloned_voices:
            return {
                "id": voice_id,
                "name": voice_id,
                "cloned": True,
            }
        return {"id": voice_id, "name": voice_id}

    @staticmethod
    def supported_paralinguistic_tags() -> List[str]:
        """Get list of supported paralinguistic tags."""
        return ChatterboxTTSProvider.PARALINGUISTIC_TAGS
