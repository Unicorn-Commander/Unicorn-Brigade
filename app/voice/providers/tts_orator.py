"""
Unicorn Orator (Pocket TTS) Provider.

Connects to the Unicorn Orator HTTP API, a self-hosted Pocket TTS service
(Kyutai Labs, 100M params) running at port 8880. Provides ~3.5x realtime
synthesis on CPU with 8 built-in voices mapped to Brigade agents.

Features:
- 100M parameters - fast CPU inference (~3.5x realtime)
- 8 built-in voices mapped to agent personas
- 24kHz audio output
- Voice cloning support
- HTTP API (no local model loading required)

Voices:
- alba: Detective Holmes (default)
- marius: Gunny
- javert: The General
- jean: Carter Knox
- fantine: Fantine
- cosette: Cosette
- eponine: Eponine
- azelma: Azelma

Usage:
    from app.voice.providers.tts_orator import OratorTTSProvider

    provider = OratorTTSProvider()
    await provider.initialize()

    audio = await provider.synthesize("Hello world!", voice="jean")
"""

import asyncio
import io
import logging
import os
import struct
from typing import AsyncIterator, Dict, Any, List, Optional, Union
from pathlib import Path

import aiohttp
import numpy as np

from app.voice.providers.base import TTSProvider, TTSConfig, TTSProviderError

logger = logging.getLogger(__name__)


class OratorTTSProvider(TTSProvider):
    """
    Unicorn Orator (Pocket TTS) Text-to-Speech provider.

    Calls the Orator HTTP API for synthesis. The Orator service wraps
    Pocket TTS (Kyutai Labs, 100M params) in a FastAPI server with
    OpenAI-compatible endpoints.
    """

    # Voice ID to agent/display name mapping
    VOICES = {
        "alba": "Detective Holmes",
        "marius": "Gunny",
        "javert": "The General",
        "jean": "Carter Knox",
        "fantine": "Fantine",
        "cosette": "Cosette",
        "eponine": "Eponine",
        "azelma": "Azelma",
    }

    DEFAULT_VOICE = "alba"
    SAMPLE_RATE = 24000

    def __init__(self, config: Optional[TTSConfig] = None, **kwargs):
        """
        Initialize the Orator TTS provider.

        Args:
            config: Optional TTSConfig with settings
            **kwargs: Additional keyword arguments (ignored)
        """
        super().__init__(config)
        self._base_url = os.getenv("ORATOR_URL", "http://unicorn-orator:8880")
        self._session: Optional[aiohttp.ClientSession] = None
        self._available_voices: List[str] = list(self.VOICES.keys())

        # Override sample rate to Orator's native rate
        self.config.sample_rate = self.SAMPLE_RATE

    async def initialize(self) -> None:
        """
        Initialize the provider by creating an HTTP session and verifying
        connectivity to the Orator service.
        """
        if self._initialized:
            return

        try:
            self._session = aiohttp.ClientSession()

            # Verify the service is healthy
            try:
                async with self._session.get(
                    f"{self._base_url}/health", timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status != 200:
                        logger.warning(
                            f"Orator health check returned status {resp.status}"
                        )
                    else:
                        logger.info("Orator service health check passed")
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.warning(
                    f"Orator health check failed (service may not be ready yet): {e}"
                )

            # Dynamically populate voice list from the service
            try:
                async with self._session.get(
                    f"{self._base_url}/voices", timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        # Accept a list of voice IDs or a dict with voice info
                        if isinstance(data, list):
                            self._available_voices = data
                        elif isinstance(data, dict) and "voices" in data:
                            voices = data["voices"]
                            if isinstance(voices, list):
                                self._available_voices = voices
                            elif isinstance(voices, dict):
                                self._available_voices = list(voices.keys())
                        logger.info(
                            f"Loaded {len(self._available_voices)} voices from Orator"
                        )
                    else:
                        logger.warning(
                            f"Orator /voices returned status {resp.status}, "
                            f"using default voice list"
                        )
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.warning(
                    f"Could not fetch voices from Orator, using defaults: {e}"
                )

            self._initialized = True
            logger.info(
                f"Orator TTS provider initialized (url={self._base_url}, "
                f"voices={len(self._available_voices)})"
            )

        except Exception as e:
            # Clean up session on failure
            if self._session and not self._session.closed:
                await self._session.close()
                self._session = None
            raise TTSProviderError(
                f"Failed to initialize Orator TTS provider: {e}",
                provider=self.name,
                cause=e,
            )

    async def cleanup(self) -> None:
        """Close the aiohttp session and release resources."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
        self._initialized = False
        logger.info("Orator TTS provider cleaned up")

    async def synthesize(self, text: str, voice: Optional[str] = None) -> bytes:
        """
        Synthesize speech from text via the Orator HTTP API.

        Sends text to the Orator /v1/audio/speech endpoint and receives
        WAV audio. The WAV is decoded to raw PCM int16 bytes.

        Args:
            text: The text to synthesize
            voice: Voice ID (e.g., "jean", "alba"). Overrides config.voice.

        Returns:
            PCM audio bytes at 24kHz, 16-bit mono
        """
        if not self._initialized:
            await self.initialize()

        voice_id = voice or self.config.voice or self.DEFAULT_VOICE
        speed = self.config.speed or 1.0

        payload = {
            "text": text,
            "voice": voice_id,
            "speed": speed,
        }

        try:
            async with self._session.post(
                f"{self._base_url}/v1/audio/speech",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                if resp.status != 200:
                    error_body = await resp.text()
                    raise TTSProviderError(
                        f"Orator synthesis failed with status {resp.status}: {error_body}",
                        provider=self.name,
                    )

                wav_bytes = await resp.read()

            # Convert WAV to raw PCM int16 bytes
            pcm_bytes = self._wav_to_pcm(wav_bytes)
            return pcm_bytes

        except aiohttp.ClientError as e:
            raise TTSProviderError(
                f"Connection error during synthesis: {e}",
                provider=self.name,
                cause=e,
            )
        except TTSProviderError:
            raise
        except Exception as e:
            raise TTSProviderError(
                f"Unexpected error during synthesis: {e}",
                provider=self.name,
                cause=e,
            )

    def _wav_to_pcm(self, wav_bytes: bytes) -> bytes:
        """
        Convert WAV audio bytes to raw PCM int16 bytes.

        Uses soundfile to properly decode the WAV regardless of header
        variations, then converts the float32 samples to int16 PCM.

        Args:
            wav_bytes: WAV file content as bytes

        Returns:
            Raw PCM int16 bytes (mono, 24kHz)
        """
        try:
            import soundfile as sf

            audio_data, sample_rate = sf.read(io.BytesIO(wav_bytes), dtype="float32")

            # Convert to mono if stereo
            if len(audio_data.shape) > 1:
                audio_data = np.mean(audio_data, axis=1)

            # Convert float32 [-1.0, 1.0] to int16
            audio_int16 = (audio_data * 32767).astype(np.int16)
            return audio_int16.tobytes()

        except ImportError:
            # Fallback: parse WAV header manually to find the data chunk
            logger.warning(
                "soundfile not available, falling back to manual WAV parsing"
            )
            return self._wav_to_pcm_manual(wav_bytes)

    def _wav_to_pcm_manual(self, wav_bytes: bytes) -> bytes:
        """
        Fallback WAV-to-PCM conversion using manual header parsing.

        Searches for the 'data' chunk marker in the WAV header and returns
        everything after the chunk size field.

        Args:
            wav_bytes: WAV file content as bytes

        Returns:
            Raw PCM bytes from the data chunk
        """
        # Find the 'data' sub-chunk
        data_marker = wav_bytes.find(b"data")
        if data_marker == -1:
            raise TTSProviderError(
                "Invalid WAV: could not find 'data' chunk",
                provider=self.name,
            )

        # The 4 bytes after 'data' are the chunk size (little-endian uint32)
        chunk_size_offset = data_marker + 4
        if chunk_size_offset + 4 > len(wav_bytes):
            raise TTSProviderError(
                "Invalid WAV: truncated data chunk header",
                provider=self.name,
            )

        (data_size,) = struct.unpack_from("<I", wav_bytes, chunk_size_offset)
        data_start = chunk_size_offset + 4

        return wav_bytes[data_start : data_start + data_size]

    async def synthesize_stream(
        self,
        text: str,
        voice: Optional[str] = None,
    ) -> AsyncIterator[bytes]:
        """
        Stream synthesized speech in ~20ms chunks.

        Orator does not natively support streaming, so we synthesize the
        full audio first and then yield it in small chunks suitable for
        real-time playback.

        Args:
            text: The text to synthesize
            voice: Voice ID

        Yields:
            Audio chunks (PCM int16 bytes, ~20ms each)
        """
        # Synthesize the full audio
        audio = await self.synthesize(text, voice)

        # Yield in ~20ms chunks at 24kHz, 16-bit (2 bytes per sample)
        chunk_size = int(self.SAMPLE_RATE * 0.02) * 2  # 480 samples * 2 bytes = 960
        for i in range(0, len(audio), chunk_size):
            chunk = audio[i : i + chunk_size]
            if chunk:
                yield chunk
                # Small delay to simulate real-time streaming
                await asyncio.sleep(0.01)

    @property
    def name(self) -> str:
        """Provider name."""
        return "orator"

    @property
    def available_voices(self) -> List[str]:
        """List of available voice IDs."""
        return self._available_voices

    @property
    def supports_voice_cloning(self) -> bool:
        """Orator supports voice cloning via the /v1/voices/clone endpoint."""
        return True

    @property
    def supports_streaming(self) -> bool:
        """Streaming is simulated by chunking full synthesis output."""
        return True

    @property
    def sample_rate(self) -> int:
        """Audio sample rate (24kHz)."""
        return self.SAMPLE_RATE

    async def clone_voice(
        self,
        audio_sample: Union[bytes, str, Path],
        voice_name: Optional[str] = None,
    ) -> str:
        """
        Create a cloned voice from an audio sample.

        Posts a multipart form to the Orator /v1/voices/clone endpoint
        with the audio sample and optional voice name.

        Args:
            audio_sample: Audio data (bytes) or path to audio file
            voice_name: Optional name for the cloned voice

        Returns:
            Voice ID for the cloned voice
        """
        if not self._initialized:
            await self.initialize()

        # Read audio file if a path was provided
        if isinstance(audio_sample, (str, Path)):
            audio_path = Path(audio_sample)
            if not audio_path.exists():
                raise TTSProviderError(
                    f"Audio sample file not found: {audio_path}",
                    provider=self.name,
                )
            audio_sample = audio_path.read_bytes()

        try:
            form = aiohttp.FormData()
            if voice_name:
                form.add_field("name", voice_name)
            form.add_field(
                "audio",
                audio_sample,
                filename="sample.wav",
                content_type="audio/wav",
            )

            async with self._session.post(
                f"{self._base_url}/v1/voices/clone",
                data=form,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                if resp.status != 200:
                    error_body = await resp.text()
                    raise TTSProviderError(
                        f"Voice cloning failed with status {resp.status}: {error_body}",
                        provider=self.name,
                    )

                result = await resp.json()
                cloned_name = result.get("name", result.get("voice_id", voice_name))

                # Add the cloned voice to our available list
                if cloned_name and cloned_name not in self._available_voices:
                    self._available_voices.append(cloned_name)

                logger.info(f"Cloned voice created: {cloned_name}")
                return cloned_name

        except aiohttp.ClientError as e:
            raise TTSProviderError(
                f"Connection error during voice cloning: {e}",
                provider=self.name,
                cause=e,
            )
        except TTSProviderError:
            raise
        except Exception as e:
            raise TTSProviderError(
                f"Unexpected error during voice cloning: {e}",
                provider=self.name,
                cause=e,
            )

    def get_voice_info(self, voice_id: str) -> Dict[str, Any]:
        """
        Get information about a specific voice.

        Args:
            voice_id: The voice ID to look up

        Returns:
            Dictionary with voice metadata
        """
        return {
            "id": voice_id,
            "name": self.VOICES.get(voice_id, voice_id),
            "engine": "pocket-tts",
        }
