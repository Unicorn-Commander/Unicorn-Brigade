"""
whisper.cpp STT Provider for Apple Silicon.

Optimized for macOS with CoreML acceleration. Uses either:
- pywhispercpp: Python bindings for whisper.cpp
- subprocess: Direct whisper.cpp binary invocation

Features:
- CoreML acceleration on Apple Silicon
- Model selection (tiny through large-v3-turbo)
- Streaming via whisper-stream
- Low memory footprint

Installation:
    # Option 1: pywhispercpp (recommended)
    pip install pywhispercpp

    # Option 2: Build whisper.cpp from source
    git clone https://github.com/ggerganov/whisper.cpp
    cd whisper.cpp
    make -j WHISPER_COREML=1  # Enable CoreML

    # Download models
    ./models/download-ggml-model.sh base
"""

import asyncio
import logging
import os
import platform
import subprocess
import tempfile
import time
from pathlib import Path
from typing import AsyncIterator, Optional, List

from app.voice.providers.base import (
    STTProvider,
    STTConfig,
    STTResult,
    STTSegment,
)

logger = logging.getLogger(__name__)


# Model name mapping for whisper.cpp
WHISPER_CPP_MODELS = {
    "tiny": "ggml-tiny",
    "tiny.en": "ggml-tiny.en",
    "base": "ggml-base",
    "base.en": "ggml-base.en",
    "small": "ggml-small",
    "small.en": "ggml-small.en",
    "medium": "ggml-medium",
    "medium.en": "ggml-medium.en",
    "large-v1": "ggml-large-v1",
    "large-v2": "ggml-large-v2",
    "large-v3": "ggml-large-v3",
    "large-v3-turbo": "ggml-large-v3-turbo",
}


class WhisperCppProvider(STTProvider):
    """
    whisper.cpp-based STT provider optimized for Apple Silicon.

    Supports both pywhispercpp library and subprocess invocation of
    the whisper.cpp binary. CoreML acceleration is enabled by default
    on Apple Silicon.

    Example:
        provider = WhisperCppProvider(STTConfig(model="base", coreml_enabled=True))
        await provider.initialize()

        text = await provider.transcribe(audio_bytes)

        # With streaming
        async for text in provider.transcribe_stream(audio_stream):
            print(text)
    """

    def __init__(
        self,
        config: Optional[STTConfig] = None,
        binary_path: Optional[str] = None,
        model_path: Optional[str] = None,
    ):
        """
        Initialize the whisper.cpp provider.

        Args:
            config: STT configuration
            binary_path: Path to whisper.cpp binary (for subprocess mode)
            model_path: Path to .bin model file (auto-detected if not provided)
        """
        super().__init__(config)
        self.binary_path = binary_path
        self.model_path = model_path
        self._whisper = None
        self._use_pywhispercpp = True

    @property
    def name(self) -> str:
        return "whisper-cpp"

    @property
    def supports_streaming(self) -> bool:
        # Streaming supported via whisper-stream or chunked processing
        return True

    async def initialize(self) -> None:
        """Initialize the provider and load the model."""
        if self._initialized:
            return

        logger.info(f"Initializing whisper.cpp provider with model: {self.config.model}")

        # Try pywhispercpp first
        try:
            from pywhispercpp.model import Model

            model_name = self.config.model
            model_dir = self._get_model_path()

            # Check for CoreML model on Apple Silicon
            coreml_model = None
            if self._is_apple_silicon() and self.config.coreml_enabled:
                coreml_model = self._find_coreml_model(model_name, model_dir)

            # Initialize model
            self._whisper = Model(
                model=self.model_path or model_name,
                models_dir=model_dir if not self.model_path else None,
                n_threads=os.cpu_count() or 4,
            )

            self._use_pywhispercpp = True
            logger.info("Using pywhispercpp backend")

        except ImportError:
            logger.warning("pywhispercpp not available, falling back to subprocess mode")
            self._use_pywhispercpp = False

            # Verify binary exists
            if self.binary_path and not Path(self.binary_path).exists():
                raise RuntimeError(f"whisper.cpp binary not found: {self.binary_path}")

            # Try to find binary in common locations
            if not self.binary_path:
                self.binary_path = self._find_whisper_binary()

            if not self.binary_path:
                raise RuntimeError(
                    "whisper.cpp not found. Install with: pip install pywhispercpp"
                )

        self._initialized = True
        logger.info(f"whisper.cpp provider initialized (CoreML: {self._is_coreml_available()})")

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

        audio = self._validate_audio(audio)

        if self._use_pywhispercpp:
            return await self._transcribe_pywhispercpp(audio, language, **kwargs)
        else:
            return await self._transcribe_subprocess(audio, language, **kwargs)

    async def _transcribe_pywhispercpp(
        self,
        audio: bytes,
        language: str,
        **kwargs,
    ) -> str:
        """Transcribe using pywhispercpp library."""
        import numpy as np

        # Convert bytes to float32 numpy array
        audio_array = np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32768.0

        # Run transcription in thread pool to not block async loop
        loop = asyncio.get_event_loop()

        def _transcribe():
            segments = self._whisper.transcribe(
                audio_array,
                language=language if language != "auto" else None,
                n_threads=os.cpu_count() or 4,
            )
            return " ".join(seg.text for seg in segments).strip()

        text = await loop.run_in_executor(None, _transcribe)
        return text

    async def _transcribe_subprocess(
        self,
        audio: bytes,
        language: str,
        **kwargs,
    ) -> str:
        """Transcribe using whisper.cpp binary via subprocess."""
        # Write audio to temp WAV file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = f.name
            self._write_wav(f, audio)

        try:
            # Build command
            cmd = [
                self.binary_path,
                "-m", self._get_model_file_path(),
                "-f", temp_path,
                "-l", language if language != "auto" else "auto",
                "-np",  # No print progress
                "-nt",  # No timestamps
            ]

            if self.config.vad_filter:
                cmd.append("-vth")
                cmd.append(str(self.config.vad_threshold))

            # Add threads
            cmd.extend(["-t", str(os.cpu_count() or 4)])

            # Run subprocess
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                logger.error(f"whisper.cpp error: {stderr.decode()}")
                raise RuntimeError(f"whisper.cpp failed: {stderr.decode()}")

            return stdout.decode().strip()

        finally:
            # Cleanup temp file
            try:
                os.unlink(temp_path)
            except Exception:
                pass

    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[bytes],
        language: str = "en",
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        Transcribe streaming audio to streaming text.

        Uses chunked processing with overlap for smoother output.

        Args:
            audio_stream: Async iterator yielding audio chunks
            language: Language code
            **kwargs: Additional options

        Yields:
            Transcribed text chunks
        """
        if not self._initialized:
            await self.initialize()

        # Buffer for accumulating audio
        buffer = bytearray()
        chunk_size = int(
            self.config.sample_rate * 2 * self.config.chunk_duration_ms / 1000
        )
        overlap_size = int(
            self.config.sample_rate * 2 * self.config.overlap_duration_ms / 1000
        )

        last_text = ""

        async for chunk in audio_stream:
            buffer.extend(chunk)

            # Process when we have enough audio
            while len(buffer) >= chunk_size:
                # Get chunk with overlap
                audio_chunk = bytes(buffer[:chunk_size])

                # Transcribe chunk
                try:
                    text = await self.transcribe(audio_chunk, language, **kwargs)

                    # Yield only new text (avoid duplicates from overlap)
                    if text and text != last_text:
                        # Find new portion
                        if last_text and text.startswith(last_text):
                            new_text = text[len(last_text):].strip()
                        else:
                            new_text = text

                        if new_text:
                            yield new_text
                            last_text = text

                except Exception as e:
                    logger.warning(f"Chunk transcription error: {e}")

                # Remove processed audio, keeping overlap
                buffer = buffer[chunk_size - overlap_size:]

        # Process remaining audio
        if len(buffer) > self.config.sample_rate:  # At least 500ms
            try:
                text = await self.transcribe(bytes(buffer), language, **kwargs)
                if text and text != last_text:
                    yield text
            except Exception as e:
                logger.warning(f"Final chunk transcription error: {e}")

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

        if self._use_pywhispercpp:
            result = await self._transcribe_with_segments(audio, language, **kwargs)
        else:
            # Subprocess mode doesn't easily support segments
            text = await self._transcribe_subprocess(audio, language, **kwargs)
            result = STTResult(
                text=text,
                language=language,
                provider=self.name,
                model_used=self.config.model,
            )

        result.processing_time = time.perf_counter() - start_time
        result.duration = len(audio) / (self.config.sample_rate * 2)

        return result

    async def _transcribe_with_segments(
        self,
        audio: bytes,
        language: str,
        **kwargs,
    ) -> STTResult:
        """Transcribe with segment information using pywhispercpp."""
        import numpy as np

        audio_array = np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32768.0

        loop = asyncio.get_event_loop()

        def _transcribe():
            return list(self._whisper.transcribe(
                audio_array,
                language=language if language != "auto" else None,
                n_threads=os.cpu_count() or 4,
            ))

        segments_raw = await loop.run_in_executor(None, _transcribe)

        segments = [
            STTSegment(
                text=seg.text.strip(),
                start=seg.t0 / 100.0,  # Convert to seconds
                end=seg.t1 / 100.0,
            )
            for seg in segments_raw
            if seg.text.strip()
        ]

        full_text = " ".join(seg.text for seg in segments)

        return STTResult(
            text=full_text,
            segments=segments,
            language=language,
            provider=self.name,
            model_used=self.config.model,
        )

    async def shutdown(self) -> None:
        """Clean up resources."""
        self._whisper = None
        self._initialized = False
        logger.info("whisper.cpp provider shutdown")

    def _is_apple_silicon(self) -> bool:
        """Check if running on Apple Silicon."""
        return (
            platform.system() == "Darwin"
            and platform.machine() == "arm64"
        )

    def _is_coreml_available(self) -> bool:
        """Check if CoreML acceleration is available."""
        return self._is_apple_silicon() and self.config.coreml_enabled

    def _find_coreml_model(self, model_name: str, model_dir: str) -> Optional[str]:
        """Find CoreML model file if available."""
        coreml_name = f"ggml-{model_name}-encoder.mlmodelc"
        coreml_path = Path(model_dir) / coreml_name

        if coreml_path.exists():
            return str(coreml_path)

        return None

    def _find_whisper_binary(self) -> Optional[str]:
        """Find whisper.cpp binary in common locations."""
        # Common binary names
        binary_names = ["whisper", "main", "whisper-cpp"]

        # Common locations
        search_paths = [
            Path.home() / "whisper.cpp",
            Path.home() / ".local" / "bin",
            Path("/usr/local/bin"),
            Path("/opt/homebrew/bin"),
            Path.cwd() / "whisper.cpp",
        ]

        for path in search_paths:
            for name in binary_names:
                binary = path / name
                if binary.exists() and os.access(binary, os.X_OK):
                    return str(binary)

        return None

    def _get_model_file_path(self) -> str:
        """Get the full path to the model file."""
        if self.model_path:
            return self.model_path

        model_dir = self._get_model_path()
        model_name = WHISPER_CPP_MODELS.get(self.config.model, f"ggml-{self.config.model}")

        return str(Path(model_dir) / f"{model_name}.bin")

    def _write_wav(self, file, audio: bytes) -> None:
        """Write audio bytes as WAV file."""
        import struct

        sample_rate = self.config.sample_rate
        channels = self.config.channels
        bits_per_sample = 16
        data_size = len(audio)

        # WAV header
        file.write(b"RIFF")
        file.write(struct.pack("<I", 36 + data_size))
        file.write(b"WAVE")

        # fmt chunk
        file.write(b"fmt ")
        file.write(struct.pack("<I", 16))  # Chunk size
        file.write(struct.pack("<H", 1))   # PCM format
        file.write(struct.pack("<H", channels))
        file.write(struct.pack("<I", sample_rate))
        file.write(struct.pack("<I", sample_rate * channels * bits_per_sample // 8))
        file.write(struct.pack("<H", channels * bits_per_sample // 8))
        file.write(struct.pack("<H", bits_per_sample))

        # data chunk
        file.write(b"data")
        file.write(struct.pack("<I", data_size))
        file.write(audio)
