"""
CosyVoice TTS Provider.

CosyVoice2-0.5B is an ultra-low latency text-to-speech model with
voice cloning capabilities. It achieves ~150ms latency to first audio
chunk, making it ideal for real-time applications.

Features:
- Ultra-low latency (~150ms first byte)
- Voice cloning with short samples
- Streaming synthesis support
- Multi-language support (English, Chinese, Japanese, Korean)
- Apache 2.0 license

Installation:
    # CosyVoice may need to be installed from git
    pip install git+https://github.com/FunAudioLLM/CosyVoice.git

    # Or if available on PyPI:
    pip install cosyvoice

Usage:
    from app.voice.providers.tts_cosyvoice import CosyVoiceTTSProvider

    provider = CosyVoiceTTSProvider()
    await provider.initialize()

    # Basic synthesis
    audio = await provider.synthesize("Hello world!")

    # Voice cloning
    cloned = await provider.clone_voice("/path/to/sample.wav")
    audio = await provider.synthesize("Hello in cloned voice!", voice=cloned)

    # Streaming (recommended for low latency)
    async for chunk in provider.synthesize_stream("Hello world!"):
        play_audio(chunk)
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


class CosyVoiceTTSProvider(TTSProvider):
    """
    CosyVoice2 Text-to-Speech provider with ultra-low latency.

    Provides streaming synthesis with voice cloning support.
    Optimized for real-time conversational AI applications.
    """

    # Preset voices (if available in the model)
    PRESET_VOICES = {
        "default": {"name": "Default", "language": "en"},
        "male_en": {"name": "Male English", "language": "en", "gender": "male"},
        "female_en": {"name": "Female English", "language": "en", "gender": "female"},
        "male_zh": {"name": "Male Chinese", "language": "zh", "gender": "male"},
        "female_zh": {"name": "Female Chinese", "language": "zh", "gender": "female"},
    }

    DEFAULT_VOICE = "default"
    SAMPLE_RATE = 22050  # CosyVoice typically uses 22.05kHz

    def __init__(
        self,
        config: Optional[TTSConfig] = None,
        model_size: str = "0.5B",
    ):
        """
        Initialize the CosyVoice TTS provider.

        Args:
            config: Optional TTSConfig with settings
            model_size: Model size ("0.5B" is default)
        """
        super().__init__(config)
        self._model_size = model_size
        self._model = None
        self._cloned_voices: Dict[str, Any] = {}

        # CosyVoice uses 22.05kHz by default
        self.config.sample_rate = self.SAMPLE_RATE

    async def initialize(self) -> None:
        """Load the CosyVoice model."""
        if self._initialized:
            return

        try:
            # Try different import paths for CosyVoice
            try:
                from cosyvoice import CosyVoice2
                self._model = CosyVoice2.from_pretrained(
                    f"CosyVoice2-{self._model_size}",
                )
            except ImportError:
                # Alternative import structure
                from cosyvoice.cli.cosyvoice import CosyVoice
                self._model = CosyVoice("CosyVoice-300M-SFT")

            # Determine device
            device = self.config.device
            if device == "auto":
                from app.voice.providers.base import detect_device
                device = detect_device()
                if device == "mlx":
                    device = "cpu"  # CosyVoice doesn't support MLX

            # Move model to device if supported
            if hasattr(self._model, "to"):
                self._model.to(device)

            logger.info(f"Loaded CosyVoice model on {device}")

            # Load default voice sample if provided
            if self.config.voice_sample_path:
                voice_id = await self.clone_voice(
                    self.config.voice_sample_path,
                    voice_name="config_voice",
                )
                self.config.voice = voice_id

            self._initialized = True

        except ImportError as e:
            raise TTSProviderError(
                "CosyVoice not installed. Install with:\n"
                "pip install git+https://github.com/FunAudioLLM/CosyVoice.git\n"
                "or: pip install cosyvoice",
                provider=self.name,
                cause=e,
            )
        except Exception as e:
            raise TTSProviderError(
                f"Failed to initialize CosyVoice: {e}",
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

        Args:
            text: The text to synthesize
            voice: Voice ID (preset or cloned)

        Returns:
            PCM audio bytes at 22.05kHz, 16-bit mono
        """
        if not self._initialized:
            await self.initialize()

        voice_id = voice or self.config.voice or self.DEFAULT_VOICE

        try:
            loop = asyncio.get_event_loop()

            # Get voice data
            voice_prompt = None
            if voice_id in self._cloned_voices:
                voice_prompt = self._cloned_voices[voice_id]

            audio = await loop.run_in_executor(
                None,
                lambda: self._synthesize_internal(text, voice_prompt),
            )

            return audio

        except Exception as e:
            raise TTSProviderError(
                f"Synthesis failed: {e}",
                provider=self.name,
                cause=e,
            )

    def _synthesize_internal(self, text: str, voice_prompt: Optional[Any]) -> bytes:
        """Internal synthesis method."""
        import numpy as np

        # Generate audio
        if voice_prompt is not None:
            # Use cloned voice
            if hasattr(self._model, "inference_zero_shot"):
                # Zero-shot voice cloning
                audio = self._model.inference_zero_shot(
                    text,
                    voice_prompt["text"],
                    voice_prompt["audio"],
                )
            else:
                audio = self._model.generate(
                    text,
                    prompt_speech=voice_prompt["audio"],
                )
        else:
            # Use default voice
            if hasattr(self._model, "inference_sft"):
                audio = self._model.inference_sft(text, "default")
            else:
                audio = self._model.generate(text)

        # Handle generator output (streaming)
        if hasattr(audio, "__iter__") and not isinstance(audio, np.ndarray):
            chunks = list(audio)
            audio = np.concatenate(chunks) if chunks else np.array([])

        # Convert to numpy if needed
        if hasattr(audio, "numpy"):
            audio = audio.numpy()
        elif hasattr(audio, "cpu"):
            audio = audio.cpu().numpy()

        # Flatten
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
        Stream synthesized speech with ultra-low latency.

        CosyVoice is optimized for streaming, achieving ~150ms
        latency to first audio chunk.

        Args:
            text: The text to synthesize
            voice: Voice ID

        Yields:
            Audio chunks (PCM bytes)
        """
        if not self._initialized:
            await self.initialize()

        voice_id = voice or self.config.voice or self.DEFAULT_VOICE
        voice_prompt = self._cloned_voices.get(voice_id)

        try:
            # Check for streaming support
            if hasattr(self._model, "inference_zero_shot_stream") or hasattr(self._model, "generate_stream"):
                async for chunk in self._stream_native(text, voice_prompt):
                    yield chunk
            else:
                # Fall back to chunked synthesis
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
        voice_prompt: Optional[Any],
    ) -> AsyncIterator[bytes]:
        """Native streaming synthesis."""
        import numpy as np

        loop = asyncio.get_event_loop()
        queue = asyncio.Queue()
        finished = asyncio.Event()

        def generate_chunks():
            """Generate audio chunks in thread."""
            try:
                # Select appropriate streaming method
                if voice_prompt is not None and hasattr(self._model, "inference_zero_shot_stream"):
                    stream = self._model.inference_zero_shot_stream(
                        text,
                        voice_prompt["text"],
                        voice_prompt["audio"],
                    )
                elif hasattr(self._model, "generate_stream"):
                    stream = self._model.generate_stream(text)
                else:
                    # Fall back to regular generation
                    audio = self._synthesize_internal(text, voice_prompt)
                    asyncio.run_coroutine_threadsafe(queue.put(audio), loop)
                    return

                for chunk in stream:
                    # Convert chunk
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

        loop.run_in_executor(None, generate_chunks)

        while not finished.is_set() or not queue.empty():
            try:
                chunk = await asyncio.wait_for(queue.get(), timeout=0.05)
                yield chunk
            except asyncio.TimeoutError:
                continue

    async def clone_voice(
        self,
        audio_sample: Union[bytes, str, Path],
        voice_name: Optional[str] = None,
        prompt_text: Optional[str] = None,
    ) -> str:
        """
        Clone a voice from an audio sample.

        CosyVoice works best with a short audio sample and the
        corresponding transcript for zero-shot cloning.

        Args:
            audio_sample: Path to audio file or audio bytes
            voice_name: Optional name for the cloned voice
            prompt_text: Transcript of the audio (improves quality)

        Returns:
            Voice ID for the cloned voice
        """
        if not self._initialized:
            await self.initialize()

        voice_id = voice_name or f"cloned_{uuid.uuid4().hex[:8]}"

        try:
            import numpy as np

            # Load audio
            if isinstance(audio_sample, (str, Path)):
                audio_path = str(audio_sample)
                try:
                    import soundfile as sf
                    audio_data, sr = sf.read(audio_path)

                    # Resample if needed
                    if sr != self.SAMPLE_RATE:
                        try:
                            import resampy
                            audio_data = resampy.resample(audio_data, sr, self.SAMPLE_RATE)
                        except ImportError:
                            logger.warning("resampy not available for resampling")
                except ImportError:
                    # Use model's built-in loading
                    audio_data = audio_path
            else:
                # Bytes - write to temp file
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    f.write(audio_sample)
                    audio_path = f.name

                import soundfile as sf
                audio_data, _ = sf.read(audio_path)

            # Store voice data
            self._cloned_voices[voice_id] = {
                "audio": audio_data,
                "text": prompt_text or "",
                "path": audio_path if isinstance(audio_sample, (str, Path)) else None,
            }

            logger.info(f"Cloned voice '{voice_id}'")
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
        return "cosyvoice"

    @property
    def available_voices(self) -> List[str]:
        """List of available voice IDs."""
        voices = list(self.PRESET_VOICES.keys())
        voices.extend(self._cloned_voices.keys())
        return voices

    @property
    def sample_rate(self) -> int:
        """Audio sample rate (22.05kHz)."""
        return self.SAMPLE_RATE

    @property
    def supports_voice_cloning(self) -> bool:
        """CosyVoice supports voice cloning."""
        return True

    @property
    def supports_streaming(self) -> bool:
        """CosyVoice supports ultra-low latency streaming."""
        return True

    def get_voice_info(self, voice_id: str) -> Dict[str, Any]:
        """Get information about a voice."""
        if voice_id in self.PRESET_VOICES:
            info = self.PRESET_VOICES[voice_id].copy()
            info["id"] = voice_id
            info["cloned"] = False
            return info
        elif voice_id in self._cloned_voices:
            return {
                "id": voice_id,
                "name": voice_id,
                "cloned": True,
                "has_transcript": bool(self._cloned_voices[voice_id].get("text")),
            }
        return {"id": voice_id, "name": voice_id}
