"""
Voice API Routes for LiveKit integration.

Provides endpoints for:
- Creating voice rooms for agents
- Getting participant tokens
- Listing active voice rooms
- Managing room lifecycle

Usage:
    POST /api/v1/voice/rooms - Create a voice room for an agent
    GET /api/v1/voice/rooms/{room_id}/token - Get participant token to join
    GET /api/v1/voice/rooms - List active voice rooms
    GET /api/v1/voice/rooms/{room_id} - Get room details
    DELETE /api/v1/voice/rooms/{room_id} - End/close a room
    GET /api/v1/voice/config - Get voice configuration options
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Annotated, Dict, List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import logging
import os

from app.db.database import get_session
from app.db.repositories import AgentRepository
# S1 (HIGH) fix — every voice route is now authenticated. Token minting, room
# creation, deletion and the agent-join trigger require OPERATOR; read-only
# listing/detail/config require any valid API key or bearer (VIEWER+). Binding
# the caller also gives us their org context (BR-1.4) so an org-scoped agent
# resolves. NOTE (residual): ``VoiceRoom`` (app/voice/livekit_agent.py) carries
# no owner/org field, so we cannot scope per-room *visibility* to the caller's
# org here — that would require adding an org column to the room manager, which
# is out of scope for this change. We therefore enforce the task's minimum:
# verify an authenticated (operator) caller BEFORE any token is minted or a room
# is mutated, closing the unauthenticated-access hole.
from app.auth.middleware import require_api_key, require_operator, AuthUser
from app.voice import VoiceRoomManager, VoiceConfig, STTProvider, TTSProvider

logger = logging.getLogger(__name__)
router = APIRouter()

# Global room manager (initialized during startup)
room_manager: Optional[VoiceRoomManager] = None
# Sticky flag: voice could not initialize (e.g. the S6 guard refused unsafe LiveKit
# creds). Set once so get_room_manager() short-circuits to 503 without re-running the
# guard — and re-logging its loud ERROR — on every subsequent voice request.
_voice_init_failed: bool = False


def init_voice_routes(manager: Optional[VoiceRoomManager] = None):
    """Initialize voice routes with room manager.

    Voice is an OPTIONAL feature. If LiveKit is misconfigured (e.g. the S6 guard
    refuses insecure dev creds in a production env), we DISABLE voice and let the
    rest of the app boot rather than crashing the entire service — a missing
    optional integration must degrade gracefully. The voice endpoints then return
    503 via get_room_manager() until real creds are configured.
    """
    global room_manager, _voice_init_failed
    if manager:
        room_manager = manager
        _voice_init_failed = False
        logger.info("Voice routes initialized")
        return
    try:
        room_manager = VoiceRoomManager()
        _voice_init_failed = False
        logger.info("Voice routes initialized")
    except Exception as e:  # incl. InsecureConfigurationError from the S6 creds guard
        room_manager = None
        _voice_init_failed = True
        logger.warning(
            "Voice DISABLED — could not initialize the LiveKit room manager: %s. "
            "The app is running normally; /api/v1/voice/* will return 503 until "
            "LIVEKIT_API_KEY/SECRET are configured with real (non-dev) values.", e
        )


def get_room_manager() -> VoiceRoomManager:
    """Get the room manager, or 503 if voice is unavailable in this environment."""
    global room_manager, _voice_init_failed
    if room_manager is None:
        # Voice already known-unavailable this process: 503 immediately, do NOT
        # re-construct (which would re-fire the S6 guard's loud ERROR every request).
        if _voice_init_failed:
            raise HTTPException(
                status_code=503,
                detail="Voice service unavailable: LiveKit is not configured for "
                       "this environment.",
            )
        try:
            room_manager = VoiceRoomManager()
        except Exception as e:  # incl. InsecureConfigurationError
            _voice_init_failed = True
            raise HTTPException(
                status_code=503,
                detail="Voice service unavailable: LiveKit is not configured for "
                       "this environment.",
            ) from e
    return room_manager


# ---- Request/Response Models ----

class CreateRoomRequest(BaseModel):
    """Request to create a voice room."""
    agent_id: str = Field(..., description="ID of the agent to host the room")
    room_name: Optional[str] = Field(None, description="Optional custom room name")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Room metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "agent_id": "col-finance",
                "room_name": "finance-consultation-001",
                "metadata": {"purpose": "quarterly review"}
            }
        }


class VoiceRoomResponse(BaseModel):
    """Voice room details."""
    id: str
    name: str
    agent_id: str
    agent_name: str
    created_at: datetime
    participants: List[str]
    status: str
    metadata: Dict[str, Any]
    livekit_url: str
    agent_token: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "voice-col-finance-550e8400",
                "agent_id": "col-finance",
                "agent_name": "Colonel Finance",
                "created_at": "2026-01-29T12:00:00Z",
                "participants": [],
                "status": "active",
                "metadata": {},
                "livekit_url": "ws://localhost:7880"
            }
        }


class ParticipantTokenResponse(BaseModel):
    """Participant token for joining a room."""
    token: str
    room_name: str
    participant_identity: str
    expires_at: datetime
    livekit_url: str

    class Config:
        json_schema_extra = {
            "example": {
                "token": "eyJ...",
                "room_name": "voice-col-finance-550e8400",
                "participant_identity": "user-john-a1b2c3",
                "expires_at": "2026-01-29T13:00:00Z",
                "livekit_url": "ws://localhost:7880"
            }
        }


class VoiceConfigResponse(BaseModel):
    """Voice configuration options."""
    stt_providers: List[str]
    tts_providers: List[str]
    default_stt: str
    default_tts: str
    livekit_url: str
    available_voices: Dict[str, List[str]]


class GetTokenRequest(BaseModel):
    """Request to get a participant token."""
    participant_name: str = Field(..., description="Display name for the participant")
    ttl_seconds: int = Field(3600, description="Token time-to-live in seconds")

    class Config:
        json_schema_extra = {
            "example": {
                "participant_name": "John",
                "ttl_seconds": 3600
            }
        }


# ---- Endpoints ----

@router.post("/voice/rooms", response_model=VoiceRoomResponse, status_code=201)
async def create_voice_room(
    request: CreateRoomRequest,
    session: AsyncSession = Depends(get_session),
    _user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Create a new voice room for an agent.

    The voice agent worker will automatically join the room and be ready
    to handle voice conversations.

    Returns room details including the LiveKit URL and agent token needed
    to connect the voice agent.
    """
    manager = get_room_manager()

    # Verify agent exists
    repo = AgentRepository(session)
    agent = await repo.get(request.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {request.agent_id}")

    if agent.get("status") != "active":
        raise HTTPException(status_code=400, detail=f"Agent is not active: {request.agent_id}")

    try:
        # Create the room
        room = await manager.create_room(
            agent_id=request.agent_id,
            agent_name=agent.get("displayName") or agent.get("name"),
            room_name=request.room_name,
            metadata=request.metadata,
        )

        # Get agent token for the voice worker
        agent_token = manager.get_agent_token(room.id, request.agent_id)

        livekit_url = os.getenv("LIVEKIT_URL", "ws://localhost:7880")

        logger.info(f"Created voice room {room.name} for agent {request.agent_id}")

        return VoiceRoomResponse(
            id=room.id,
            name=room.name,
            agent_id=room.agent_id,
            agent_name=room.agent_name,
            created_at=room.created_at,
            participants=room.participants,
            status=room.status,
            metadata=room.metadata,
            livekit_url=livekit_url,
            agent_token=agent_token.token,
        )

    except Exception as e:
        logger.error(f"Failed to create voice room: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/voice/rooms/{room_id}/token", response_model=ParticipantTokenResponse)
async def get_participant_token(
    room_id: str,
    participant_name: str = Query(..., description="Display name for the participant"),
    ttl_seconds: int = Query(3600, description="Token TTL in seconds"),
    _user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Get a participant token to join a voice room.

    The token includes permissions to publish/subscribe audio and data.
    Use this token with the LiveKit client SDK to join the room.
    """
    manager = get_room_manager()

    room = manager.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail=f"Room not found: {room_id}")

    if room.status != "active":
        raise HTTPException(status_code=400, detail=f"Room is not active: {room_id}")

    try:
        token_data = manager.get_participant_token(
            room_id=room_id,
            participant_name=participant_name,
            ttl_seconds=ttl_seconds,
        )

        livekit_url = os.getenv("LIVEKIT_URL", "ws://localhost:7880")

        return ParticipantTokenResponse(
            token=token_data.token,
            room_name=token_data.room_name,
            participant_identity=token_data.participant_identity,
            expires_at=token_data.expires_at,
            livekit_url=livekit_url,
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to generate token: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/voice/rooms/{room_id}/token", response_model=ParticipantTokenResponse)
async def get_participant_token_post(
    room_id: str,
    request: GetTokenRequest,
    _user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Get a participant token to join a voice room (POST variant).

    Same as GET but accepts parameters in request body.
    """
    # This handler carries its OWN auth dependency: the inner call below invokes
    # get_participant_token as a plain function, which does NOT re-trigger that
    # route's Depends(...), so the guard must live here too.
    return await get_participant_token(
        room_id=room_id,
        participant_name=request.participant_name,
        ttl_seconds=request.ttl_seconds,
    )


@router.get("/voice/rooms", response_model=Dict[str, Any])
async def list_voice_rooms(
    agent_id: Optional[str] = Query(None, description="Filter by agent ID"),
    _user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """
    List active voice rooms.

    Optionally filter by agent ID to see rooms for a specific agent.
    """
    manager = get_room_manager()

    rooms = manager.list_rooms(agent_id=agent_id)

    livekit_url = os.getenv("LIVEKIT_URL", "ws://localhost:7880")

    return {
        "rooms": [
            {
                "id": room.id,
                "name": room.name,
                "agent_id": room.agent_id,
                "agent_name": room.agent_name,
                "created_at": room.created_at.isoformat(),
                "participants": room.participants,
                "status": room.status,
                "metadata": room.metadata,
            }
            for room in rooms
        ],
        "count": len(rooms),
        "livekit_url": livekit_url,
    }


@router.get("/voice/rooms/{room_id}", response_model=VoiceRoomResponse)
async def get_voice_room(
    room_id: str,
    _user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """
    Get details for a specific voice room.
    """
    manager = get_room_manager()

    room = manager.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail=f"Room not found: {room_id}")

    livekit_url = os.getenv("LIVEKIT_URL", "ws://localhost:7880")

    return VoiceRoomResponse(
        id=room.id,
        name=room.name,
        agent_id=room.agent_id,
        agent_name=room.agent_name,
        created_at=room.created_at,
        participants=room.participants,
        status=room.status,
        metadata=room.metadata,
        livekit_url=livekit_url,
    )


@router.delete("/voice/rooms/{room_id}")
async def close_voice_room(
    room_id: str,
    _user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Close/end a voice room.

    This disconnects all participants and frees resources.
    """
    manager = get_room_manager()

    success = await manager.close_room(room_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Room not found: {room_id}")

    logger.info(f"Closed voice room: {room_id}")

    return {"message": "Room closed", "room_id": room_id}


@router.get("/voice/config", response_model=VoiceConfigResponse)
async def get_voice_config_endpoint(
    _user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """
    Get voice configuration options.

    Returns available STT/TTS providers and default settings.
    Includes both cloud-based and self-hosted providers.
    """
    from app.voice.config import get_voice_config as get_config
    from app.voice.providers import VoiceProviderRegistry

    config = get_config()

    # Get self-hosted providers from registry
    registry_stt = VoiceProviderRegistry.list_stt_providers()
    registry_tts = VoiceProviderRegistry.list_tts_providers()

    # Combine cloud and self-hosted providers
    all_stt = [p.value for p in STTProvider] + registry_stt
    all_tts = [p.value for p in TTSProvider] + registry_tts

    # Build available voices including Kokoro
    available_voices = {
        "openai": ["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
        "elevenlabs": ["Rachel", "Drew", "Clyde", "Paul", "Domi", "Dave", "Fin", "Sarah", "Antoni", "Thomas", "Charlie", "George", "Emily", "Elli", "Callum", "Patrick", "Harry", "Liam", "Dorothy", "Josh", "Arnold", "Charlotte", "Matilda", "Matthew", "James", "Joseph", "Jeremy", "Michael", "Ethan", "Gigi", "Freya", "Grace", "Daniel", "Serena", "Adam", "Nicole", "Bill", "Jessie", "Sam", "Glinda", "Giovanni", "Mimi"],
        "kokoro": [
            "af_bella", "af_heart", "af_nicole", "af_sarah", "af_sky",
            "am_adam", "am_michael",
            "bf_emma", "bf_isabella",
            "bm_george", "bm_lewis",
        ],
    }

    return VoiceConfigResponse(
        stt_providers=list(set(all_stt)),
        tts_providers=list(set(all_tts)),
        default_stt=config.stt_provider,
        default_tts=config.tts_provider,
        livekit_url=config.livekit_url,
        available_voices=available_voices,
    )


@router.get("/voice/health")
async def voice_health():
    """
    Health check for voice services.

    Checks LiveKit connectivity and voice provider availability.
    Includes both cloud-based and self-hosted providers.

    NOTE: ``/api/v1/voice/health`` is intentionally listed in
    ``app.auth.roles.PUBLIC_PATHS`` (monitoring/liveness), so no auth dependency
    is added here — ``get_current_user`` short-circuits public paths, which would
    make ``require_api_key`` a no-op and ``require_operator`` a 403 for probes.
    Changing that policy belongs in roles.py, which is out of scope for S1.
    """
    from app.voice.config import get_voice_config as get_config
    from app.voice.providers import VoiceProviderRegistry, list_available_providers

    config = get_config()

    livekit_api_key = os.getenv("LIVEKIT_API_KEY")
    deepgram_key = os.getenv("DEEPGRAM_API_KEY")
    elevenlabs_key = os.getenv("ELEVENLABS_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    # Get available self-hosted providers
    available_stt = list_available_providers()
    registry_stt = VoiceProviderRegistry.list_stt_providers()
    registry_tts = VoiceProviderRegistry.list_tts_providers()

    return {
        "status": "healthy",
        "livekit": {
            "url": config.livekit_url,
            "configured": bool(livekit_api_key),
        },
        "current_config": {
            "stt_provider": config.stt_provider,
            "stt_model": config.stt_model,
            "tts_provider": config.tts_provider,
            "tts_voice": config.tts_voice,
        },
        "cloud_providers": {
            "stt": {
                "deepgram": {"configured": bool(deepgram_key)},
                "whisper": {"configured": bool(openai_key)},
            },
            "tts": {
                "openai": {"configured": bool(openai_key)},
                "elevenlabs": {"configured": bool(elevenlabs_key)},
            },
        },
        "self_hosted_providers": {
            "stt": {
                "registered": registry_stt,
                "available": available_stt,
            },
            "tts": {
                "registered": registry_tts,
            },
        },
        "room_count": (len(room_manager.list_rooms()) if room_manager is not None else 0),
        "voice_enabled": room_manager is not None,
    }


@router.post("/voice/rooms/{room_id}/agent/join")
async def trigger_agent_join(
    room_id: str,
    session: AsyncSession = Depends(get_session),
    _user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Trigger the voice agent to join a room.

    This is typically called automatically when a room is created,
    but can be used to reconnect an agent if needed.
    """
    manager = get_room_manager()

    room = manager.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail=f"Room not found: {room_id}")

    # Verify agent exists
    repo = AgentRepository(session)
    agent = await repo.get(room.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {room.agent_id}")

    # Get token for agent
    agent_token = manager.get_agent_token(room_id, room.agent_id)

    # In production, this would dispatch to the agent worker
    # For now, return the token so the caller can handle it

    livekit_url = os.getenv("LIVEKIT_URL", "ws://localhost:7880")

    return {
        "message": "Agent join triggered",
        "room_id": room_id,
        "room_name": room.name,
        "agent_id": room.agent_id,
        "agent_token": agent_token.token,
        "livekit_url": livekit_url,
    }
