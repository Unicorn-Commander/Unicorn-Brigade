"""
Amanuensis STT Provider - HTTP client for the Amanuensis Whisper-based STT service.

Calls the Amanuensis API (a self-hosted Whisper STT server) over HTTP
rather than loading a model locally. This is ideal when Amanuensis is
already running as a container (e.g. unicorn-amanuensis on port 9000)
and you want to reuse it from Brigade without duplicating model memory.

Features:
- Multipart form-data upload to OpenAI-compatible /v1/audio/transcriptions
- Health check on initialization
- Graceful connection error handling
- Accumulate-and-transcribe fallback for streaming callers

Requirements:
    pip install aiohttp
"""

import asyncio
import logging
import os
from typing import AsyncIterator, Optional

import aiohttp

from app.voice.providers.base import (
    STTProvider,
    STTConfig,
    STTProviderError,
)

logger = logging.getLogger(__name__)


class AmanuensisSTTProvider(STTProvider):
    """
    STT provider that delegates transcription to the Amanuensis HTTP API.

    Amanuensis exposes an OpenAI-compatible ``/v1/audio/transcriptions``
    endpoint backed by Whisper.  This provider simply POSTs audio to that
    endpoint and returns the resulting text.

    Example:
        provider = AmanuensisSTTProvider()
        await provider.initialize()
        text = await provider.transcribe(wav_bytes)
    """

    def __init__(self, config: Optional[STTConfig] = None):
        """
        Initialize the Amanuensis STT provider.

        Args:
            config: Optional STT configuration.
        """
        super().__init__(config)
        self._base_url: str = os.getenv(
            "AMANUENSIS_URL", "http://unicorn-amanuensis:9000"
        )
        self._session: Optional[aiohttp.ClientSession] = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "amanuensis"

    @property
    def supports_streaming(self) -> bool:
        return False

    @property
    def sample_rate(self) -> int:
        return 16000

    @property
    def supports_word_timestamps(self) -> bool:
        return True

    @property
    def supports_vad(self) -> bool:
        return False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Create an HTTP session and verify that Amanuensis is reachable."""
        if self._initialized:
            return

        logger.info(
            "Initializing Amanuensis STT provider at %s", self._base_url
        )

        self._session = aiohttp.ClientSession()

        # Health check
        try:
            async with self._session.get(
                f"{self._base_url}/health", timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise STTProviderError(
                        f"Amanuensis health check failed (HTTP {resp.status}): {body}"
                    )
                logger.info("Amanuensis health check passed")
        except aiohttp.ClientError as exc:
            await self._session.close()
            self._session = None
            raise STTProviderError(
                f"Cannot reach Amanuensis at {self._base_url}: {exc}"
            ) from exc

        self._initialized = True
        logger.info("Amanuensis STT provider initialized")

    async def shutdown(self) -> None:
        """Close the aiohttp session and release resources."""
        if self._session and not self._session.closed:
            await self._session.close()
            logger.info("Amanuensis HTTP session closed")
        self._session = None
        self._initialized = False

    # ------------------------------------------------------------------
    # Transcription
    # ------------------------------------------------------------------

    async def transcribe(
        self,
        audio: bytes,
        language: Optional[str] = None,
        **kwargs,
    ) -> str:
        """
        Transcribe audio bytes by POSTing to Amanuensis.

        Sends a multipart/form-data request to
        ``{base_url}/v1/audio/transcriptions`` with the audio file,
        model name, and optional language hint.

        Args:
            audio: Audio data in WAV format (16 kHz, 16-bit, mono).
            language: Optional language code (e.g. ``"en"``).
            **kwargs: Reserved for future use.

        Returns:
            The transcribed text string.

        Raises:
            STTProviderError: On connection or API errors.
        """
        if not self._initialized or self._session is None:
            await self.initialize()

        url = f"{self._base_url}/v1/audio/transcriptions"

        form = aiohttp.FormData()
        form.add_field(
            "file",
            audio,
            filename="audio.wav",
            content_type="audio/wav",
        )
        form.add_field("model", "base")
        form.add_field("response_format", "json")

        if language is not None:
            form.add_field("language", language)

        try:
            async with self._session.post(
                url,
                data=form,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise STTProviderError(
                        f"Amanuensis transcription failed (HTTP {resp.status}): {body}"
                    )

                result = await resp.json()
                text = result.get("text", "").strip()
                logger.debug("Amanuensis transcription: %s", text)
                return text

        except aiohttp.ClientError as exc:
            raise STTProviderError(
                f"Connection error during transcription: {exc}"
            ) from exc

    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[bytes],
        language: Optional[str] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        Pseudo-streaming transcription.

        Amanuensis does not support real streaming, so this method
        accumulates all audio chunks into a single buffer and then
        calls :meth:`transcribe` once.  The single result is yielded.

        Args:
            audio_stream: Async iterator of audio chunks.
            language: Optional language code.
            **kwargs: Reserved for future use.

        Yields:
            A single transcribed text string.
        """
        buffer = bytearray()

        async for chunk in audio_stream:
            buffer.extend(chunk)

        if buffer:
            text = await self.transcribe(bytes(buffer), language=language, **kwargs)
            if text:
                yield text
