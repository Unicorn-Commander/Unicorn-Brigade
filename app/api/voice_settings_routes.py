"""
Voice Settings API Routes.

Provides endpoints for managing voice provider settings,
listing available providers, and testing STT/TTS functionality.

Endpoints:
    GET  /api/v1/voice/settings           - Get current voice config
    PUT  /api/v1/voice/settings           - Update voice config
    GET  /api/v1/voice/providers          - List all available providers
    GET  /api/v1/voice/providers/stt      - List STT providers with details
    GET  /api/v1/voice/providers/tts      - List TTS providers with details
    GET  /api/v1/voice/voices             - List available voices for current TTS
    POST /api/v1/voice/test/stt           - Test STT with audio upload
    POST /api/v1/voice/test/tts           - Test TTS, returns audio
"""

import io
import logging
import tempfile
from typing import Annotated, Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, UploadFile, File, Query, Depends
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.voice.config import (
    get_voice_config,
    update_voice_config,
    reset_voice_config,
    VoiceConfig,
)
from app.voice.providers import (
    VoiceProviderRegistry,
    register_builtin_providers,
)
from app.auth.middleware import require_operator, require_admin, AuthUser

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================================================
# Pydantic Models
# ============================================================================

class VoiceSettingsRequest(BaseModel):
    """Request model for updating voice settings."""
    stt_provider: Optional[str] = Field(None, description="STT provider name")
    stt_model: Optional[str] = Field(None, description="STT model name")
    stt_device: Optional[str] = Field(None, description="Device: auto, cpu, cuda, mps")
    stt_compute_type: Optional[str] = Field(None, description="Compute type: float16, int8, float32")
    stt_language: Optional[str] = Field(None, description="Default language code")

    tts_provider: Optional[str] = Field(None, description="TTS provider name")
    tts_model: Optional[str] = Field(None, description="TTS model name")
    tts_voice: Optional[str] = Field(None, description="Default voice ID")
    tts_sample_rate: Optional[int] = Field(None, description="Audio sample rate")
    tts_speed: Optional[float] = Field(None, description="Speech speed multiplier")

    vad_enabled: Optional[bool] = Field(None, description="Enable VAD filtering")
    vad_threshold: Optional[float] = Field(None, description="VAD confidence threshold")

    custom_stt_model_path: Optional[str] = Field(None, description="Custom STT model path")
    custom_tts_model_path: Optional[str] = Field(None, description="Custom TTS model path")

    class Config:
        json_schema_extra = {
            "example": {
                "stt_provider": "faster-whisper",
                "stt_model": "large-v3-turbo",
                "tts_voice": "af_bella",
            }
        }


class VoiceSettingsResponse(BaseModel):
    """Response model for voice settings."""
    stt_provider: str
    stt_model: str
    stt_device: str
    stt_compute_type: str
    stt_language: str

    tts_provider: str
    tts_model: str
    tts_voice: str
    tts_sample_rate: int
    tts_speed: float

    vad_enabled: bool
    vad_threshold: float

    custom_stt_model_path: Optional[str]
    custom_tts_model_path: Optional[str]

    livekit_url: str

    class Config:
        json_schema_extra = {
            "example": {
                "stt_provider": "faster-whisper",
                "stt_model": "large-v3-turbo",
                "stt_device": "auto",
                "stt_compute_type": "float16",
                "stt_language": "en",
                "tts_provider": "kokoro",
                "tts_model": "kokoro-82m",
                "tts_voice": "af_bella",
                "tts_sample_rate": 24000,
                "tts_speed": 1.0,
                "vad_enabled": True,
                "vad_threshold": 0.5,
                "custom_stt_model_path": None,
                "custom_tts_model_path": None,
                "livekit_url": "ws://localhost:7880",
            }
        }


class ProviderInfo(BaseModel):
    """Information about a voice provider."""
    name: str
    description: str
    supported_models: List[str]
    supports_streaming: bool
    supports_voice_cloning: bool = False
    license: str
    hardware_requirements: str

    class Config:
        json_schema_extra = {
            "example": {
                "name": "faster-whisper",
                "description": "CTranslate2-optimized Whisper for CUDA GPUs",
                "supported_models": ["large-v3-turbo", "large-v3", "medium"],
                "supports_streaming": True,
                "supports_voice_cloning": False,
                "license": "MIT",
                "hardware_requirements": "CUDA GPU recommended, CPU supported",
            }
        }


class VoiceInfo(BaseModel):
    """Information about an available voice."""
    id: str
    name: str
    gender: Optional[str] = None
    accent: Optional[str] = None
    style: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "id": "af_bella",
                "name": "Bella",
                "gender": "female",
                "accent": "american",
                "style": "warm",
            }
        }


class STTTestResponse(BaseModel):
    """Response from STT test."""
    text: str
    language: Optional[str]
    duration: float
    processing_time: float
    provider: str
    model: str


class TTSTestRequest(BaseModel):
    """Request for TTS test."""
    text: str = Field(..., description="Text to synthesize")
    voice: Optional[str] = Field(None, description="Voice ID to use")
    speed: Optional[float] = Field(1.0, description="Speech speed multiplier")

    class Config:
        json_schema_extra = {
            "example": {
                "text": "Hello, this is a test of the text-to-speech system.",
                "voice": "af_bella",
                "speed": 1.0,
            }
        }


# ============================================================================
# Settings Endpoints
# ============================================================================

@router.get("/voice/settings", response_model=VoiceSettingsResponse)
async def get_settings():
    """
    Get current voice configuration.

    Returns all current STT and TTS settings.
    """
    config = get_voice_config()

    return VoiceSettingsResponse(
        stt_provider=config.stt_provider,
        stt_model=config.stt_model,
        stt_device=config.stt_device,
        stt_compute_type=config.stt_compute_type,
        stt_language=config.stt_language,
        tts_provider=config.tts_provider,
        tts_model=config.tts_model,
        tts_voice=config.tts_voice,
        tts_sample_rate=config.tts_sample_rate,
        tts_speed=config.tts_speed,
        vad_enabled=config.vad_enabled,
        vad_threshold=config.vad_threshold,
        custom_stt_model_path=config.custom_stt_model_path,
        custom_tts_model_path=config.custom_tts_model_path,
        livekit_url=config.livekit_url,
    )


@router.put("/voice/settings", response_model=VoiceSettingsResponse)
async def update_settings(
    request: VoiceSettingsRequest,
    user: Annotated[AuthUser, Depends(require_admin)] = None,
):
    """
    Update voice configuration.

    Only provided fields will be updated; others remain unchanged.
    """
    # Convert request to dict, filtering out None values
    updates = {k: v for k, v in request.model_dump().items() if v is not None}

    if not updates:
        raise HTTPException(status_code=400, detail="No settings provided to update")

    # Validate provider if changing
    if "stt_provider" in updates:
        stt_providers = VoiceProviderRegistry.list_stt_providers()
        if updates["stt_provider"] not in stt_providers:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid STT provider: {updates['stt_provider']}. "
                       f"Available: {', '.join(stt_providers)}"
            )

    if "tts_provider" in updates:
        tts_providers = VoiceProviderRegistry.list_tts_providers()
        if updates["tts_provider"] not in tts_providers:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid TTS provider: {updates['tts_provider']}. "
                       f"Available: {', '.join(tts_providers)}"
            )

    # Update config
    config = update_voice_config(updates)

    logger.info(f"Voice settings updated: {list(updates.keys())}")

    return VoiceSettingsResponse(
        stt_provider=config.stt_provider,
        stt_model=config.stt_model,
        stt_device=config.stt_device,
        stt_compute_type=config.stt_compute_type,
        stt_language=config.stt_language,
        tts_provider=config.tts_provider,
        tts_model=config.tts_model,
        tts_voice=config.tts_voice,
        tts_sample_rate=config.tts_sample_rate,
        tts_speed=config.tts_speed,
        vad_enabled=config.vad_enabled,
        vad_threshold=config.vad_threshold,
        custom_stt_model_path=config.custom_stt_model_path,
        custom_tts_model_path=config.custom_tts_model_path,
        livekit_url=config.livekit_url,
    )


@router.post("/voice/settings/reset", response_model=VoiceSettingsResponse)
async def reset_settings(
    user: Annotated[AuthUser, Depends(require_admin)] = None,
):
    """
    Reset voice configuration to defaults from environment.
    """
    config = reset_voice_config()

    logger.info("Voice settings reset to defaults")

    return VoiceSettingsResponse(
        stt_provider=config.stt_provider,
        stt_model=config.stt_model,
        stt_device=config.stt_device,
        stt_compute_type=config.stt_compute_type,
        stt_language=config.stt_language,
        tts_provider=config.tts_provider,
        tts_model=config.tts_model,
        tts_voice=config.tts_voice,
        tts_sample_rate=config.tts_sample_rate,
        tts_speed=config.tts_speed,
        vad_enabled=config.vad_enabled,
        vad_threshold=config.vad_threshold,
        custom_stt_model_path=config.custom_stt_model_path,
        custom_tts_model_path=config.custom_tts_model_path,
        livekit_url=config.livekit_url,
    )


# ============================================================================
# Provider Endpoints
# ============================================================================

@router.get("/voice/providers")
async def list_all_providers():
    """
    List all available voice providers (STT and TTS).
    """
    stt_providers = VoiceProviderRegistry.list_stt_providers_detailed()
    tts_providers = VoiceProviderRegistry.list_tts_providers_detailed()

    return {
        "stt_providers": stt_providers,
        "tts_providers": tts_providers,
        "default_stt": get_voice_config().stt_provider,
        "default_tts": get_voice_config().tts_provider,
    }


@router.get("/voice/providers/stt", response_model=List[ProviderInfo])
async def list_stt_providers():
    """
    List available STT (Speech-to-Text) providers with details.
    """
    providers = VoiceProviderRegistry.list_stt_providers_detailed()

    return [
        ProviderInfo(
            name=p["name"],
            description=p["description"],
            supported_models=p["supported_models"],
            supports_streaming=p["supports_streaming"],
            supports_voice_cloning=False,
            license=p["license"],
            hardware_requirements=p["hardware_requirements"],
        )
        for p in providers
    ]


@router.get("/voice/providers/tts", response_model=List[ProviderInfo])
async def list_tts_providers():
    """
    List available TTS (Text-to-Speech) providers with details.
    """
    providers = VoiceProviderRegistry.list_tts_providers_detailed()

    return [
        ProviderInfo(
            name=p["name"],
            description=p["description"],
            supported_models=p["supported_models"],
            supports_streaming=p["supports_streaming"],
            supports_voice_cloning=p.get("supports_voice_cloning", False),
            license=p["license"],
            hardware_requirements=p["hardware_requirements"],
        )
        for p in providers
    ]


@router.get("/voice/voices", response_model=List[VoiceInfo])
async def list_voices(
    provider: Optional[str] = Query(None, description="TTS provider name (uses current if not specified)")
):
    """
    List available voices for a TTS provider.

    Returns voice IDs and metadata for the specified or current TTS provider.
    """
    config = get_voice_config()
    provider_name = provider or config.tts_provider

    try:
        tts_provider = VoiceProviderRegistry.get_tts(provider_name)
        await tts_provider.initialize()

        voices = []
        for voice_id in tts_provider.available_voices:
            info = tts_provider.get_voice_info(voice_id)
            voices.append(VoiceInfo(
                id=voice_id,
                name=info.get("name", voice_id),
                gender=info.get("gender"),
                accent=info.get("accent"),
                style=info.get("style"),
            ))

        return voices

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error listing voices: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list voices: {e}")


# ============================================================================
# Test Endpoints
# ============================================================================

@router.post("/voice/test/stt", response_model=STTTestResponse)
async def test_stt(
    file: UploadFile = File(..., description="Audio file to transcribe"),
    language: Optional[str] = Query("en", description="Language code"),
    provider: Optional[str] = Query(None, description="STT provider to use"),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Test STT (Speech-to-Text) with an audio file upload.

    Accepts WAV, MP3, or other common audio formats.
    Returns transcribed text and timing information.
    """
    import time

    config = get_voice_config()
    provider_name = provider or config.stt_provider

    # Read audio file
    audio_bytes = await file.read()

    if len(audio_bytes) < 1000:
        raise HTTPException(status_code=400, detail="Audio file too small")

    try:
        # Get provider
        stt_provider = VoiceProviderRegistry.get_stt(provider_name)
        await stt_provider.initialize()

        # Transcribe
        start_time = time.perf_counter()
        result = await stt_provider.transcribe(audio_bytes, language=language)
        processing_time = time.perf_counter() - start_time

        # Handle different result types
        if hasattr(result, 'text'):
            # STTResult object
            return STTTestResponse(
                text=result.text,
                language=result.language if hasattr(result, 'language') else language,
                duration=result.duration if hasattr(result, 'duration') else 0.0,
                processing_time=processing_time,
                provider=provider_name,
                model=config.stt_model,
            )
        else:
            # String result
            return STTTestResponse(
                text=str(result),
                language=language,
                duration=0.0,
                processing_time=processing_time,
                provider=provider_name,
                model=config.stt_model,
            )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"STT test failed: {e}")
        raise HTTPException(status_code=500, detail=f"STT test failed: {e}")


@router.post("/voice/test/tts")
async def test_tts(
    request: TTSTestRequest,
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Test TTS (Text-to-Speech) with text input.

    Returns synthesized audio as WAV file.
    """
    config = get_voice_config()

    if not request.text or len(request.text.strip()) < 1:
        raise HTTPException(status_code=400, detail="Text is required")

    try:
        # Get provider
        tts_provider = VoiceProviderRegistry.get_tts(config.tts_provider)
        await tts_provider.initialize()

        # Update speed if provided
        if request.speed and request.speed != 1.0:
            tts_provider.config.speed = request.speed

        # Synthesize
        voice = request.voice or config.tts_voice
        audio_bytes = await tts_provider.synthesize(request.text, voice=voice)

        # Convert PCM to WAV
        from app.voice.providers.base import pcm_to_wav
        wav_bytes = pcm_to_wav(
            audio_bytes,
            sample_rate=tts_provider.sample_rate,
        )

        return Response(
            content=wav_bytes,
            media_type="audio/wav",
            headers={
                "Content-Disposition": f'attachment; filename="tts_test.wav"',
                "X-Voice-Provider": config.tts_provider,
                "X-Voice-ID": voice,
            }
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"TTS test failed: {e}")
        raise HTTPException(status_code=500, detail=f"TTS test failed: {e}")


# ============================================================================
# Initialization
# ============================================================================

def init_voice_settings_routes():
    """
    Initialize voice settings routes.

    Registers built-in providers on startup.
    """
    try:
        register_builtin_providers()
        logger.info("Voice settings routes initialized")
    except Exception as e:
        logger.warning(f"Failed to register some providers: {e}")
