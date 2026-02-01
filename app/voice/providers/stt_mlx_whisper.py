"""
MLX Whisper STT Provider for Apple Silicon.

Uses Apple's MLX framework for native Metal acceleration on Apple Silicon.
Optimized for low-latency inference with unified memory architecture.

Features:
- Native Metal acceleration
- Unified memory (no CPU-GPU transfer overhead)
- Quantization support (4-bit, 8-bit)
- Streaming transcription
- Optimized for M1/M2/M3 chips

Installation:
    pip install mlx-whisper

Note: Only works on Apple Silicon Macs (M1, M2, M3, etc.)
"""

import asyncio
import logging
import os
import platform
import time
from pathlib import Path
from typing import AsyncIterator, Optional

from app.voice.providers.base import (
    STTProvider,
    STTConfig,
    STTResult,
    STTSegment,
)

logger = logging.getLogger(__name__)


# Model name mapping for mlx-whisper (uses Hugging Face naming)
MLX_MODEL_MAP = {
    "tiny": "mlx-community/whisper-tiny-mlx",
    "tiny.en": "mlx-community/whisper-tiny.en-mlx",
    "base": "mlx-community/whisper-base-mlx",
    "base.en": "mlx-community/whisper-base.en-mlx",
    "small": "mlx-community/whisper-small-mlx",
    "small.en": "mlx-community/whisper-small.en-mlx",
    "medium": "mlx-community/whisper-medium-mlx",
    "medium.en": "mlx-community/whisper-medium.en-mlx",
    "large-v1": "mlx-community/whisper-large-mlx",
    "large-v2": "mlx-community/whisper-large-v2-mlx",
    "large-v3": "mlx-community/whisper-large-v3-mlx",
    "large-v3-turbo": "mlx-community/whisper-large-v3-turbo",
    # Quantized versions
    "large-v3-4bit": "mlx-community/whisper-large-v3-mlx-4bit",
    "large-v3-turbo-4bit": "mlx-community/whisper-large-v3-turbo-q4",
}


class MLXWhisperProvider(STTProvider):
    """
    MLX Whisper-based STT provider for Apple Silicon.

    Leverages Apple's MLX framework for optimal performance on M-series chips.
    Uses unified memory architecture for zero-copy data transfer between CPU and GPU.

    Example:
        provider = MLXWhisperProvider(STTConfig(
            model="large-v3-turbo",
            quantization="4bit",  # Optional quantization
        ))
        await provider.initialize()

        text = await provider.transcribe(audio_bytes)

        # With streaming
        async for text in provider.transcribe_stream(audio_stream):
            print(text)
    """

    def __init__(self, config: Optional[STTConfig] = None):
        """
        Initialize the MLX Whisper provider.

        Args:
            config: STT configuration
        """
        super().__init__(config)
        self._validate_platform()

    def _validate_platform(self) -> None:
        """Validate that we're running on Apple Silicon."""
        if platform.system() != "Darwin":
            raise RuntimeError("MLX Whisper only works on macOS")

        if platform.machine() != "arm64":
            raise RuntimeError("MLX Whisper requires Apple Silicon (M1/M2/M3)")

    @property
    def name(self) -> str:
        return "mlx-whisper"

    @property
    def supports_streaming(self) -> bool:
        return True

    @property
    def supports_word_timestamps(self) -> bool:
        return True

    async def initialize(self) -> None:
        """Initialize the provider and load the model."""
        if self._initialized:
            return

        logger.info(f"Initializing MLX Whisper provider with model: {self.config.model}")

        try:
            import mlx_whisper
        except ImportError:
            raise RuntimeError(
                "mlx-whisper not installed. Install with: pip install mlx-whisper"
            )

        # Determine model path
        model_name = self._get_model_name()

        # Pre-load model to cache (mlx_whisper loads lazily)
        # We do a test transcription to trigger model loading
        loop = asyncio.get_event_loop()

        def _warmup():
            import numpy as np
            # Create 1 second of silence for warmup
            silence = np.zeros(self.config.sample_rate, dtype=np.float32)
            try:
                mlx_whisper.transcribe(
                    silence,
                    path_or_hf_repo=model_name,
                    language=self.config.language if self.config.language != "auto" else None,
                )
            except Exception as e:
                logger.warning(f"Warmup transcription warning: {e}")

        logger.info(f"Loading MLX Whisper model: {model_name}")
        await loop.run_in_executor(None, _warmup)

        self._initialized = True
        logger.info("MLX Whisper provider initialized")

    async def transcribe(
        self,
        audio: bytes,
        language: str = "en",
        **kwargs,
    ) -> str:
        """
        Transcribe audio bytes to text.

        Args:
            audio: Raw PCM audio bytes (16kHz, 16-bit, mono)
            language: Language code
            **kwargs: Additional options

        Returns:
            Transcribed text
        """
        if not self._initialized:
            await self.initialize()

        result = await self.transcribe_with_result(audio, language, **kwargs)
        return result.text

    async def transcribe_with_result(
        self,
        audio: bytes,
        language: str = "en",
        **kwargs,
    ) -> STTResult:
        """
        Transcribe audio and return detailed result with segments.

        Args:
            audio: Raw audio bytes
            language: Language code
            **kwargs: Additional options

        Returns:
            STTResult with text, segments, and metadata
        """
        if not self._initialized:
            await self.initialize()

        audio = self._validate_audio(audio)
        start_time = time.perf_counter()

        import mlx_whisper
        import numpy as np

        # Convert to float32 numpy array
        audio_array = np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32768.0

        model_name = self._get_model_name()

        # Build transcription options
        word_timestamps = kwargs.get("word_timestamps", True)

        # Run transcription in thread pool
        loop = asyncio.get_event_loop()

        def _transcribe():
            return mlx_whisper.transcribe(
                audio_array,
                path_or_hf_repo=model_name,
                language=language if language != "auto" else None,
                word_timestamps=word_timestamps,
                fp16=True,  # Use FP16 for faster inference
            )

        result = await loop.run_in_executor(None, _transcribe)

        # Extract segments
        segments = []
        for seg in result.get("segments", []):
            words = []
            if word_timestamps and "words" in seg:
                words = [
                    {
                        "word": w.get("word", ""),
                        "start": w.get("start", 0),
                        "end": w.get("end", 0),
                        "probability": w.get("probability", 1.0),
                    }
                    for w in seg.get("words", [])
                ]

            segments.append(STTSegment(
                text=seg.get("text", "").strip(),
                start=seg.get("start", 0),
                end=seg.get("end", 0),
                confidence=seg.get("avg_logprob", 0.0),
                words=words,
            ))

        full_text = result.get("text", "").strip()

        processing_time = time.perf_counter() - start_time
        duration = len(audio) / (self.config.sample_rate * 2)

        return STTResult(
            text=full_text,
            segments=segments,
            language=result.get("language", language),
            duration=duration,
            processing_time=processing_time,
            model_used=self.config.model,
            provider=self.name,
        )

    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[bytes],
        language: str = "en",
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        Transcribe streaming audio to streaming text.

        Uses chunked processing for streaming output.

        Args:
            audio_stream: Async iterator yielding audio chunks
            language: Language code
            **kwargs: Additional options

        Yields:
            Transcribed text chunks
        """
        if not self._initialized:
            await self.initialize()

        import mlx_whisper
        import numpy as np

        # Buffer for accumulating audio
        buffer = bytearray()
        chunk_size = int(
            self.config.sample_rate * 2 * self.config.chunk_duration_ms / 1000
        )
        overlap_size = int(
            self.config.sample_rate * 2 * self.config.overlap_duration_ms / 1000
        )

        model_name = self._get_model_name()
        last_text = ""

        async for chunk in audio_stream:
            buffer.extend(chunk)

            # Process when we have enough audio
            while len(buffer) >= chunk_size:
                # Get chunk with overlap consideration
                audio_chunk = bytes(buffer[:chunk_size])
                audio_array = np.frombuffer(audio_chunk, dtype=np.int16).astype(np.float32) / 32768.0

                # Run transcription
                loop = asyncio.get_event_loop()

                def _transcribe():
                    return mlx_whisper.transcribe(
                        audio_array,
                        path_or_hf_repo=model_name,
                        language=language if language != "auto" else None,
                        word_timestamps=False,  # Faster for streaming
                        fp16=True,
                    )

                try:
                    result = await loop.run_in_executor(None, _transcribe)
                    text = result.get("text", "").strip()

                    # Yield new text only
                    if text and text != last_text:
                        if last_text and text.startswith(last_text):
                            new_text = text[len(last_text):].strip()
                        else:
                            new_text = text

                        if new_text:
                            yield new_text
                            last_text = text

                except Exception as e:
                    logger.warning(f"Stream chunk transcription error: {e}")

                # Remove processed audio, keeping overlap
                buffer = buffer[chunk_size - overlap_size:]

        # Process remaining audio
        if len(buffer) > self.config.sample_rate:  # At least 500ms
            try:
                audio_array = np.frombuffer(bytes(buffer), dtype=np.int16).astype(np.float32) / 32768.0

                def _transcribe_final():
                    return mlx_whisper.transcribe(
                        audio_array,
                        path_or_hf_repo=model_name,
                        language=language if language != "auto" else None,
                        fp16=True,
                    )

                result = await asyncio.get_event_loop().run_in_executor(None, _transcribe_final)
                text = result.get("text", "").strip()

                if text and text != last_text:
                    yield text

            except Exception as e:
                logger.warning(f"Final stream transcription error: {e}")

    async def transcribe_file(
        self,
        file_path: str,
        language: str = "en",
        **kwargs,
    ) -> STTResult:
        """
        Transcribe an audio file directly.

        MLX Whisper can process files directly, which may be more efficient
        than loading and converting audio manually.

        Args:
            file_path: Path to audio file (WAV, MP3, etc.)
            language: Language code
            **kwargs: Additional options

        Returns:
            STTResult with transcription
        """
        if not self._initialized:
            await self.initialize()

        import mlx_whisper

        start_time = time.perf_counter()
        model_name = self._get_model_name()

        loop = asyncio.get_event_loop()

        def _transcribe():
            return mlx_whisper.transcribe(
                file_path,
                path_or_hf_repo=model_name,
                language=language if language != "auto" else None,
                word_timestamps=True,
                fp16=True,
            )

        result = await loop.run_in_executor(None, _transcribe)

        # Extract segments
        segments = []
        for seg in result.get("segments", []):
            segments.append(STTSegment(
                text=seg.get("text", "").strip(),
                start=seg.get("start", 0),
                end=seg.get("end", 0),
            ))

        processing_time = time.perf_counter() - start_time

        return STTResult(
            text=result.get("text", "").strip(),
            segments=segments,
            language=result.get("language", language),
            processing_time=processing_time,
            model_used=self.config.model,
            provider=self.name,
        )

    async def shutdown(self) -> None:
        """Clean up resources."""
        # MLX manages memory automatically through Python's garbage collector
        # and unified memory architecture
        import gc
        gc.collect()

        self._initialized = False
        logger.info("MLX Whisper provider shutdown")

    def _get_model_name(self) -> str:
        """
        Get the model name or path for mlx_whisper.

        Returns:
            Hugging Face model ID or local path
        """
        model = self.config.model

        # Check for quantization suffix
        if self.config.quantization == "4bit":
            if f"{model}-4bit" in MLX_MODEL_MAP:
                model = f"{model}-4bit"
            else:
                logger.warning(f"4-bit quantization not available for {model}")

        # Check if it's a known model
        if model in MLX_MODEL_MAP:
            return MLX_MODEL_MAP[model]

        # Check if it's a local path
        if Path(model).exists():
            return model

        # Assume it's a Hugging Face model ID
        return model

    def _detect_device(self) -> str:
        """MLX always uses Metal/GPU on Apple Silicon."""
        return "mps"

    def get_memory_usage(self) -> dict:
        """
        Get current MLX memory usage.

        Returns:
            Dictionary with memory stats
        """
        try:
            import mlx.core as mx

            return {
                "peak_memory_bytes": mx.metal.get_peak_memory(),
                "active_memory_bytes": mx.metal.get_active_memory(),
                "cache_memory_bytes": mx.metal.get_cache_memory(),
            }
        except Exception as e:
            logger.warning(f"Could not get MLX memory usage: {e}")
            return {}

    def clear_cache(self) -> None:
        """Clear MLX memory cache."""
        try:
            import mlx.core as mx
            mx.metal.clear_cache()
            logger.info("MLX cache cleared")
        except Exception as e:
            logger.warning(f"Could not clear MLX cache: {e}")
