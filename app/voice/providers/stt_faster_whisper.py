"""
faster-whisper STT Provider for CUDA GPUs.

Uses CTranslate2 for optimized inference with INT8 quantization support.
Ideal for systems with NVIDIA GPUs or CPU fallback with INT8.

Features:
- CTranslate2 optimized inference
- INT8/INT8_FLOAT16 quantization for memory efficiency
- Batched transcription support
- Integrated VAD filtering
- Word-level timestamps

Installation:
    pip install faster-whisper

    # For GPU support (CUDA 11.x)
    pip install nvidia-cublas-cu11 nvidia-cudnn-cu11

    # For GPU support (CUDA 12.x)
    pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
"""

import asyncio
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import AsyncIterator, Optional, List

from app.voice.providers.base import (
    STTProvider,
    STTConfig,
    STTResult,
    STTSegment,
    ComputeType,
    DeviceType,
)

logger = logging.getLogger(__name__)


# Compute type mapping for faster-whisper
COMPUTE_TYPE_MAP = {
    ComputeType.FLOAT32: "float32",
    ComputeType.FLOAT16: "float16",
    ComputeType.INT8: "int8",
    ComputeType.INT8_FLOAT16: "int8_float16",
}


class FasterWhisperProvider(STTProvider):
    """
    faster-whisper-based STT provider using CTranslate2.

    Provides optimized Whisper inference with support for:
    - CUDA GPUs with FP16/INT8 quantization
    - CPU with INT8 quantization for memory efficiency
    - Integrated Silero VAD for noise filtering

    Example:
        provider = FasterWhisperProvider(STTConfig(
            model="large-v3-turbo",
            device=DeviceType.CUDA,
            compute_type=ComputeType.INT8_FLOAT16,
        ))
        await provider.initialize()

        text = await provider.transcribe(audio_bytes)

        # With VAD filtering
        result = await provider.transcribe_with_result(
            audio_bytes,
            vad_filter=True,
        )
    """

    def __init__(self, config: Optional[STTConfig] = None):
        """
        Initialize the faster-whisper provider.

        Args:
            config: STT configuration
        """
        super().__init__(config)
        self._model = None
        self._vad_model = None

    @property
    def name(self) -> str:
        return "faster-whisper"

    @property
    def supports_streaming(self) -> bool:
        return True

    @property
    def supports_word_timestamps(self) -> bool:
        return True

    @property
    def supports_vad(self) -> bool:
        return True

    async def initialize(self) -> None:
        """Initialize the provider and load the model."""
        if self._initialized:
            return

        logger.info(f"Initializing faster-whisper provider with model: {self.config.model}")

        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise RuntimeError(
                "faster-whisper not installed. Install with: pip install faster-whisper"
            )

        # Determine device and compute type
        device = self._detect_device()
        compute_type = COMPUTE_TYPE_MAP.get(
            self.config.compute_type, "float16"
        )

        # Adjust compute type for CPU
        if device == "cpu":
            if compute_type in ["float16", "int8_float16"]:
                logger.info(f"CPU doesn't support {compute_type}, using int8")
                compute_type = "int8"

        # Adjust for MPS (not directly supported, use CPU)
        if device == "mps":
            logger.info("MPS not supported by faster-whisper, falling back to CPU")
            device = "cpu"
            compute_type = "int8"

        # Get model path or name
        model_path = self._get_model_path()
        model_name = self.config.model

        # Check if model is already downloaded
        local_model = Path(model_path) / f"faster-whisper-{model_name}"
        if local_model.exists():
            model_name = str(local_model)

        # Load model in thread pool
        loop = asyncio.get_event_loop()

        def _load_model():
            return WhisperModel(
                model_name,
                device=device,
                compute_type=compute_type,
                download_root=model_path,
                cpu_threads=os.cpu_count() or 4,
                num_workers=2,
            )

        logger.info(f"Loading faster-whisper model on {device} with {compute_type}")
        self._model = await loop.run_in_executor(None, _load_model)

        self._initialized = True
        logger.info(f"faster-whisper provider initialized (device: {device}, compute: {compute_type})")

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
            **kwargs: Additional options (vad_filter, beam_size, etc.)

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

        # Convert to numpy array
        import numpy as np
        audio_array = np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32768.0

        # Build transcription options
        vad_filter = kwargs.get("vad_filter", self.config.vad_filter)
        beam_size = kwargs.get("beam_size", self.config.beam_size)
        best_of = kwargs.get("best_of", self.config.best_of)
        temperature = kwargs.get("temperature", self.config.temperature)

        vad_options = None
        if vad_filter:
            vad_options = {
                "threshold": self.config.vad_threshold,
                "min_speech_duration_ms": self.config.min_speech_duration_ms,
                "min_silence_duration_ms": self.config.min_silence_duration_ms,
                "speech_pad_ms": self.config.speech_pad_ms,
            }

        # Run transcription in thread pool
        loop = asyncio.get_event_loop()

        def _transcribe():
            segments, info = self._model.transcribe(
                audio_array,
                language=language if language != "auto" else None,
                beam_size=beam_size,
                best_of=best_of,
                temperature=temperature,
                word_timestamps=True,
                vad_filter=vad_filter,
                vad_parameters=vad_options,
            )
            return list(segments), info

        segments_raw, info = await loop.run_in_executor(None, _transcribe)

        # Build segments
        segments = []
        for seg in segments_raw:
            words = []
            if hasattr(seg, "words") and seg.words:
                words = [
                    {
                        "word": w.word,
                        "start": w.start,
                        "end": w.end,
                        "probability": w.probability,
                    }
                    for w in seg.words
                ]

            segments.append(STTSegment(
                text=seg.text.strip(),
                start=seg.start,
                end=seg.end,
                confidence=getattr(seg, "avg_logprob", 0.0),
                words=words,
            ))

        full_text = " ".join(seg.text for seg in segments)

        processing_time = time.perf_counter() - start_time

        return STTResult(
            text=full_text,
            segments=segments,
            language=info.language or language,
            language_probability=info.language_probability or 1.0,
            duration=info.duration or (len(audio) / (self.config.sample_rate * 2)),
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

        Uses chunked processing with VAD for efficient streaming.

        Args:
            audio_stream: Async iterator yielding audio chunks
            language: Language code
            **kwargs: Additional options

        Yields:
            Transcribed text chunks
        """
        if not self._initialized:
            await self.initialize()

        # Import numpy for audio processing
        import numpy as np

        # Buffer for accumulating audio
        buffer = bytearray()
        chunk_size = int(
            self.config.sample_rate * 2 * self.config.chunk_duration_ms / 1000
        )

        # Track last transcription for deduplication
        last_full_text = ""

        async for chunk in audio_stream:
            buffer.extend(chunk)

            # Process when we have enough audio
            while len(buffer) >= chunk_size:
                # Get chunk
                audio_chunk = bytes(buffer[:chunk_size])
                audio_array = np.frombuffer(audio_chunk, dtype=np.int16).astype(np.float32) / 32768.0

                # Run transcription
                loop = asyncio.get_event_loop()

                def _transcribe():
                    segments, _ = self._model.transcribe(
                        audio_array,
                        language=language if language != "auto" else None,
                        vad_filter=self.config.vad_filter,
                        beam_size=1,  # Faster for streaming
                    )
                    return " ".join(seg.text for seg in segments).strip()

                try:
                    text = await loop.run_in_executor(None, _transcribe)

                    # Yield new text only
                    if text and text != last_full_text:
                        # Find new portion
                        if last_full_text and text.startswith(last_full_text):
                            new_text = text[len(last_full_text):].strip()
                        else:
                            new_text = text

                        if new_text:
                            yield new_text
                            last_full_text = text

                except Exception as e:
                    logger.warning(f"Stream transcription error: {e}")

                # Remove processed audio
                buffer = buffer[chunk_size:]

        # Process remaining audio
        if len(buffer) > self.config.sample_rate:  # At least 500ms
            try:
                audio_array = np.frombuffer(bytes(buffer), dtype=np.int16).astype(np.float32) / 32768.0

                def _transcribe_final():
                    segments, _ = self._model.transcribe(
                        audio_array,
                        language=language if language != "auto" else None,
                        vad_filter=self.config.vad_filter,
                    )
                    return " ".join(seg.text for seg in segments).strip()

                text = await asyncio.get_event_loop().run_in_executor(None, _transcribe_final)

                if text and text != last_full_text:
                    yield text

            except Exception as e:
                logger.warning(f"Final stream transcription error: {e}")

    async def transcribe_batch(
        self,
        audio_files: List[bytes],
        language: str = "en",
        **kwargs,
    ) -> List[STTResult]:
        """
        Transcribe multiple audio files in batch.

        More efficient than individual transcriptions for multiple files.

        Args:
            audio_files: List of audio byte arrays
            language: Language code
            **kwargs: Additional options

        Returns:
            List of STTResult objects
        """
        if not self._initialized:
            await self.initialize()

        import numpy as np

        # Convert all audio to numpy arrays
        audio_arrays = [
            np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32768.0
            for audio in audio_files
        ]

        # Process in thread pool
        loop = asyncio.get_event_loop()

        def _transcribe_batch():
            results = []
            for audio_array in audio_arrays:
                start_time = time.perf_counter()
                segments, info = self._model.transcribe(
                    audio_array,
                    language=language if language != "auto" else None,
                    beam_size=self.config.beam_size,
                    vad_filter=self.config.vad_filter,
                )

                segment_list = list(segments)
                text = " ".join(seg.text for seg in segment_list)

                results.append(STTResult(
                    text=text.strip(),
                    segments=[
                        STTSegment(
                            text=seg.text.strip(),
                            start=seg.start,
                            end=seg.end,
                        )
                        for seg in segment_list
                    ],
                    language=info.language or language,
                    duration=info.duration,
                    processing_time=time.perf_counter() - start_time,
                    model_used=self.config.model,
                    provider=self.name,
                ))

            return results

        return await loop.run_in_executor(None, _transcribe_batch)

    async def detect_language(
        self,
        audio: bytes,
        **kwargs,
    ) -> tuple[str, float]:
        """
        Detect the language of audio without full transcription.

        Args:
            audio: Raw audio bytes

        Returns:
            Tuple of (language_code, probability)
        """
        if not self._initialized:
            await self.initialize()

        import numpy as np
        audio_array = np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32768.0

        loop = asyncio.get_event_loop()

        def _detect():
            # Use first 30 seconds for language detection
            audio_30s = audio_array[:30 * self.config.sample_rate]
            _, probs = self._model.model.detect_language(
                self._model.feature_extractor(audio_30s)
            )
            # Get the top language
            lang = max(probs, key=probs.get)
            return lang, probs[lang]

        return await loop.run_in_executor(None, _detect)

    async def shutdown(self) -> None:
        """Clean up resources."""
        self._model = None
        self._vad_model = None
        self._initialized = False
        logger.info("faster-whisper provider shutdown")

    def _detect_device(self) -> str:
        """Detect the best available device for faster-whisper."""
        if self.config.device != DeviceType.AUTO:
            device = self.config.device.value
            # Validate CUDA availability
            if device == "cuda":
                try:
                    import torch
                    if not torch.cuda.is_available():
                        logger.warning("CUDA requested but not available, falling back to CPU")
                        return "cpu"
                except ImportError:
                    logger.warning("PyTorch not installed, falling back to CPU")
                    return "cpu"
            return device

        # Auto-detect
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
        except ImportError:
            pass

        return "cpu"
