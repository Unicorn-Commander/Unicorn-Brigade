"""
LiveKit Voice Agent Implementation.

Provides voice conversation capabilities for Brigade agents using LiveKit.
Integrates with existing agent personas, tools, and the LLM client.

Key components:
- LiveKitVoiceAgent: Main agent worker that handles voice interactions
- VoiceRoomManager: Manages room creation, tokens, and lifecycle
- STT/TTS integration: Supports multiple providers (Deepgram, Whisper, ElevenLabs, OpenAI)
"""

import os
import logging
import asyncio
import json
import time
import uuid
from typing import Optional, Dict, Any, List, Callable
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import httpx

logger = logging.getLogger(__name__)


class STTProvider(str, Enum):
    """Speech-to-Text provider options."""
    DEEPGRAM = "deepgram"
    WHISPER = "whisper"
    ASSEMBLYAI = "assemblyai"


class TTSProvider(str, Enum):
    """Text-to-Speech provider options."""
    ELEVENLABS = "elevenlabs"
    OPENAI = "openai"
    CARTESIA = "cartesia"


@dataclass
class VoiceConfig:
    """Configuration for voice agent."""
    stt_provider: STTProvider = STTProvider.DEEPGRAM
    tts_provider: TTSProvider = TTSProvider.OPENAI

    # Voice settings
    voice_id: Optional[str] = None  # Provider-specific voice ID
    language: str = "en"

    # VAD settings
    vad_enabled: bool = True
    vad_threshold: float = 0.5
    vad_min_speech_duration: float = 0.25
    vad_min_silence_duration: float = 0.5

    # Interruption handling
    allow_interruptions: bool = True
    interruption_threshold: float = 0.3

    # Audio settings
    sample_rate: int = 16000
    channels: int = 1


@dataclass
class VoiceRoom:
    """Represents a voice room."""
    id: str
    name: str
    agent_id: str
    agent_name: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    participants: List[str] = field(default_factory=list)
    status: str = "active"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParticipantToken:
    """Token for participant to join a room."""
    token: str
    room_name: str
    participant_identity: str
    expires_at: datetime


class VoiceRoomManager:
    """
    Manages LiveKit voice rooms for Brigade agents.

    Handles:
    - Room creation and lifecycle
    - Participant token generation
    - Room listing and cleanup
    """

    def __init__(
        self,
        livekit_url: Optional[str] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
    ):
        self.livekit_url = livekit_url or os.getenv("LIVEKIT_URL", "ws://localhost:7880")
        self.api_key = api_key or os.getenv("LIVEKIT_API_KEY", "unicorn")
        self.api_secret = api_secret or os.getenv("LIVEKIT_API_SECRET", "unicorn-brigade-secret-key-change-me")

        # In-memory room tracking (for now)
        self._rooms: Dict[str, VoiceRoom] = {}

        logger.info(f"VoiceRoomManager initialized with LiveKit URL: {self.livekit_url}")

    def _generate_jwt(
        self,
        room_name: str,
        participant_identity: str,
        is_agent: bool = False,
        ttl_seconds: int = 3600,
    ) -> str:
        """
        Generate a LiveKit JWT access token.

        For production, use livekit-api package. This is a simplified implementation.
        """
        try:
            # Try to use the official livekit-api package
            from livekit.api import AccessToken, VideoGrants

            token = AccessToken(self.api_key, self.api_secret)

            # Set permissions
            grants = VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
                can_publish_data=True,
            )

            # Agents get additional permissions
            if is_agent:
                grants.room_admin = True
                grants.room_record = True

            # livekit-api v1.x uses chaining methods
            token = (
                token.with_identity(participant_identity)
                .with_name(participant_identity)
                .with_ttl(timedelta(seconds=ttl_seconds))
                .with_grants(grants)
            )

            return token.to_jwt()

        except ImportError:
            # Fallback: generate a simple token structure
            # NOTE: This won't work with a real LiveKit server
            logger.warning("livekit-api not installed, using mock token")
            import base64

            payload = {
                "iss": self.api_key,
                "sub": participant_identity,
                "name": participant_identity,
                "video": {
                    "room": room_name,
                    "roomJoin": True,
                    "canPublish": True,
                    "canSubscribe": True,
                },
                "exp": int(time.time()) + ttl_seconds,
            }

            # This is a mock - real implementation needs proper JWT signing
            return base64.b64encode(json.dumps(payload).encode()).decode()

    async def create_room(
        self,
        agent_id: str,
        agent_name: str,
        room_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> VoiceRoom:
        """
        Create a new voice room for an agent.

        The agent worker will automatically join when the room is created.
        """
        room_id = str(uuid.uuid4())
        room_name = room_name or f"voice-{agent_id}-{room_id[:8]}"

        room = VoiceRoom(
            id=room_id,
            name=room_name,
            agent_id=agent_id,
            agent_name=agent_name,
            metadata=metadata or {},
        )

        self._rooms[room_id] = room

        logger.info(f"Created voice room: {room_name} for agent {agent_id}")

        # Notify the agent worker to join (if using LiveKit API)
        try:
            await self._notify_agent_worker(room)
        except Exception as e:
            logger.warning(f"Failed to notify agent worker: {e}")

        return room

    async def _notify_agent_worker(self, room: VoiceRoom):
        """
        Notify the voice agent worker to join a room.

        In production, this would use LiveKit's agent dispatch API.
        For now, we rely on the agent worker polling for rooms or
        using a webhook/event system.
        """
        # The agent worker will discover rooms via the API
        # This is a placeholder for more sophisticated dispatch
        pass

    def get_participant_token(
        self,
        room_id: str,
        participant_name: str,
        ttl_seconds: int = 3600,
    ) -> ParticipantToken:
        """
        Generate a token for a participant to join a room.
        """
        room = self._rooms.get(room_id)
        if not room:
            raise ValueError(f"Room not found: {room_id}")

        participant_identity = f"user-{participant_name}-{uuid.uuid4().hex[:6]}"

        token = self._generate_jwt(
            room_name=room.name,
            participant_identity=participant_identity,
            is_agent=False,
            ttl_seconds=ttl_seconds,
        )

        expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)

        # Track participant
        room.participants.append(participant_identity)

        return ParticipantToken(
            token=token,
            room_name=room.name,
            participant_identity=participant_identity,
            expires_at=expires_at,
        )

    def get_agent_token(self, room_id: str, agent_id: str) -> ParticipantToken:
        """Generate a token for the agent to join a room."""
        room = self._rooms.get(room_id)
        if not room:
            raise ValueError(f"Room not found: {room_id}")

        agent_identity = f"agent-{agent_id}"

        token = self._generate_jwt(
            room_name=room.name,
            participant_identity=agent_identity,
            is_agent=True,
            ttl_seconds=7200,  # Agents get longer tokens
        )

        return ParticipantToken(
            token=token,
            room_name=room.name,
            participant_identity=agent_identity,
            expires_at=datetime.utcnow() + timedelta(seconds=7200),
        )

    def list_rooms(self, agent_id: Optional[str] = None) -> List[VoiceRoom]:
        """List active voice rooms, optionally filtered by agent."""
        rooms = list(self._rooms.values())

        if agent_id:
            rooms = [r for r in rooms if r.agent_id == agent_id]

        # Filter to active rooms only
        rooms = [r for r in rooms if r.status == "active"]

        return rooms

    def get_room(self, room_id: str) -> Optional[VoiceRoom]:
        """Get a specific room by ID."""
        return self._rooms.get(room_id)

    async def close_room(self, room_id: str) -> bool:
        """Close a voice room."""
        room = self._rooms.get(room_id)
        if not room:
            return False

        room.status = "closed"

        # Notify LiveKit to close the room (if using LiveKit API)
        try:
            # In production, use LiveKit API to delete the room
            pass
        except Exception as e:
            logger.warning(f"Failed to close LiveKit room: {e}")

        logger.info(f"Closed voice room: {room.name}")
        return True

    def cleanup_inactive_rooms(self, max_age_hours: int = 24):
        """Remove old inactive rooms."""
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)

        to_remove = [
            room_id
            for room_id, room in self._rooms.items()
            if room.created_at < cutoff or room.status == "closed"
        ]

        for room_id in to_remove:
            del self._rooms[room_id]

        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} inactive voice rooms")


class LiveKitVoiceAgent:
    """
    Voice agent that connects to LiveKit rooms and handles voice conversations.

    This agent:
    - Joins LiveKit rooms as a participant
    - Uses VAD (Voice Activity Detection) to detect speech
    - Transcribes speech using STT (Deepgram, Whisper, etc.)
    - Processes text through the Brigade agent's LLM
    - Synthesizes responses using TTS (ElevenLabs, OpenAI, etc.)
    - Handles interruptions gracefully

    The agent integrates with existing Brigade agents, using their:
    - Persona and system prompts
    - Tools and function calling
    - Memory context
    """

    def __init__(
        self,
        agent_id: str,
        agent_config: Dict[str, Any],
        voice_config: Optional[VoiceConfig] = None,
        brigade_api_url: Optional[str] = None,
    ):
        self.agent_id = agent_id
        self.agent_config = agent_config
        self.voice_config = voice_config or VoiceConfig()
        self.brigade_api_url = brigade_api_url or os.getenv(
            "BRIGADE_API_URL", "http://localhost:8100"
        )

        # State
        self._room = None
        self._is_speaking = False
        self._is_listening = True
        self._conversation_history: List[Dict[str, str]] = []
        self._current_task: Optional[asyncio.Task] = None

        # Callbacks
        self._on_transcription: Optional[Callable] = None
        self._on_response: Optional[Callable] = None
        self._on_state_change: Optional[Callable] = None

        logger.info(f"LiveKitVoiceAgent initialized for agent: {agent_id}")

    @property
    def agent_name(self) -> str:
        return self.agent_config.get("displayName") or self.agent_config.get("name", self.agent_id)

    @property
    def system_prompt(self) -> str:
        """Build system prompt from agent config."""
        parts = []

        if self.agent_config.get("persona"):
            parts.append(self.agent_config["persona"])

        if self.agent_config.get("systemPrompt"):
            parts.append(self.agent_config["systemPrompt"])

        # Add voice-specific instructions
        parts.append(
            "You are now speaking via voice. Keep your responses concise and natural. "
            "Avoid using markdown, bullet points, or other text formatting. "
            "Speak conversationally as if talking to a person."
        )

        return "\n\n".join(parts) if parts else f"You are {self.agent_name}, a helpful AI assistant."

    async def join_room(self, room_token: str, room_url: Optional[str] = None):
        """
        Join a LiveKit room as a voice agent.

        This method:
        1. Connects to the LiveKit room
        2. Sets up audio tracks for input/output
        3. Initializes VAD, STT, and TTS
        4. Starts the voice conversation loop
        """
        try:
            from livekit import rtc
            from livekit.agents import AgentSession, JobContext
            from livekit.plugins import silero

            # Create room connection
            room = rtc.Room()

            # Set up event handlers
            @room.on("participant_connected")
            def on_participant_connected(participant: rtc.RemoteParticipant):
                logger.info(f"Participant connected: {participant.identity}")
                if self._on_state_change:
                    asyncio.create_task(self._on_state_change("participant_joined", {
                        "identity": participant.identity,
                    }))

            @room.on("participant_disconnected")
            def on_participant_disconnected(participant: rtc.RemoteParticipant):
                logger.info(f"Participant disconnected: {participant.identity}")
                if self._on_state_change:
                    asyncio.create_task(self._on_state_change("participant_left", {
                        "identity": participant.identity,
                    }))

            @room.on("track_subscribed")
            def on_track_subscribed(
                track: rtc.Track,
                publication: rtc.RemoteTrackPublication,
                participant: rtc.RemoteParticipant,
            ):
                if track.kind == rtc.TrackKind.KIND_AUDIO:
                    logger.info(f"Subscribed to audio from: {participant.identity}")
                    # Start processing audio
                    asyncio.create_task(self._process_audio_track(track, participant))

            # Connect to room
            livekit_url = room_url or os.getenv("LIVEKIT_URL", "ws://localhost:7880")
            await room.connect(livekit_url, room_token)

            self._room = room
            logger.info(f"Voice agent joined room: {room.name}")

            # Publish agent's audio track
            await self._setup_audio_output(room)

            # Send greeting
            await self._speak_greeting()

        except ImportError as e:
            logger.error(f"LiveKit SDK not installed: {e}")
            raise RuntimeError(
                "LiveKit SDK required. Install with: pip install livekit livekit-agents"
            )
        except Exception as e:
            logger.error(f"Failed to join room: {e}")
            raise

    async def _setup_audio_output(self, room):
        """Set up audio output track for TTS."""
        try:
            from livekit import rtc

            # Create audio source for TTS output
            self._audio_source = rtc.AudioSource(
                sample_rate=self.voice_config.sample_rate,
                num_channels=self.voice_config.channels,
            )

            # Create and publish audio track
            track = rtc.LocalAudioTrack.create_audio_track(
                "agent-voice",
                self._audio_source,
            )

            await room.local_participant.publish_track(track)
            logger.info("Published agent audio track")

        except Exception as e:
            logger.error(f"Failed to set up audio output: {e}")

    async def _process_audio_track(self, track, participant):
        """
        Process incoming audio from a participant.

        This runs the VAD -> STT -> LLM -> TTS pipeline.
        """
        try:
            from livekit import rtc

            # Create audio stream from track
            audio_stream = rtc.AudioStream(track)

            # Buffer for audio frames
            audio_buffer = []

            async for frame in audio_stream:
                if not self._is_listening:
                    continue

                # Run VAD
                is_speech = await self._detect_speech(frame)

                if is_speech:
                    audio_buffer.append(frame)

                    # Handle interruption
                    if self._is_speaking and self.voice_config.allow_interruptions:
                        await self._handle_interruption()

                elif audio_buffer:
                    # End of speech - process the buffer
                    await self._process_speech(audio_buffer, participant.identity)
                    audio_buffer = []

        except Exception as e:
            logger.error(f"Error processing audio: {e}")

    async def _detect_speech(self, audio_frame) -> bool:
        """
        Detect if audio frame contains speech using VAD.

        Uses Silero VAD for accurate voice activity detection.
        """
        if not self.voice_config.vad_enabled:
            return True  # Assume all audio is speech

        try:
            from livekit.plugins import silero

            # Use Silero VAD (would be initialized once in production)
            # This is a simplified example
            vad = silero.VAD.load()

            # Check for speech
            events = vad.stream()
            # ... process frame through VAD

            return True  # Placeholder

        except Exception as e:
            logger.warning(f"VAD error: {e}")
            return True

    async def _process_speech(self, audio_frames: List, speaker_identity: str):
        """
        Process accumulated speech frames through STT -> LLM -> TTS.
        """
        try:
            # 1. Transcribe audio to text
            text = await self._transcribe(audio_frames)

            if not text or len(text.strip()) < 2:
                return

            logger.info(f"Transcribed: {text[:100]}...")

            if self._on_transcription:
                await self._on_transcription(text, speaker_identity)

            # 2. Get response from Brigade agent
            response = await self._get_agent_response(text)

            if not response:
                return

            logger.info(f"Agent response: {response[:100]}...")

            if self._on_response:
                await self._on_response(response)

            # 3. Synthesize and speak response
            await self._speak(response)

        except Exception as e:
            logger.error(f"Error processing speech: {e}")

    async def _transcribe(self, audio_frames: List) -> str:
        """
        Transcribe audio frames to text using configured STT provider.
        """
        provider = self.voice_config.stt_provider

        try:
            if provider == STTProvider.DEEPGRAM:
                return await self._transcribe_deepgram(audio_frames)
            elif provider == STTProvider.WHISPER:
                return await self._transcribe_whisper(audio_frames)
            else:
                logger.warning(f"Unknown STT provider: {provider}, using Whisper")
                return await self._transcribe_whisper(audio_frames)

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return ""

    async def _transcribe_deepgram(self, audio_frames: List) -> str:
        """Transcribe using Deepgram."""
        try:
            from livekit.plugins import deepgram

            # Deepgram streaming transcription
            stt = deepgram.STT()

            # Combine audio frames
            audio_data = b"".join(f.data for f in audio_frames)

            # Transcribe
            result = await stt.recognize(audio_data)

            return result.text if result else ""

        except ImportError:
            logger.error("Deepgram plugin not installed: pip install livekit-plugins-deepgram")
            return ""

    async def _transcribe_whisper(self, audio_frames: List) -> str:
        """Transcribe using OpenAI Whisper."""
        try:
            import openai

            client = openai.AsyncOpenAI()

            # Combine audio frames and convert to format Whisper expects
            audio_data = b"".join(f.data for f in audio_frames)

            # Write to temporary file (Whisper API needs a file)
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                # Would need proper WAV header in production
                f.write(audio_data)
                temp_path = f.name

            with open(temp_path, "rb") as audio_file:
                result = await client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language=self.voice_config.language,
                )

            return result.text

        except Exception as e:
            logger.error(f"Whisper transcription error: {e}")
            return ""

    async def _get_agent_response(self, user_message: str) -> str:
        """
        Get a response from the Brigade agent.

        Uses the existing chat endpoint which supports function calling.
        """
        # Add to conversation history
        self._conversation_history.append({"role": "user", "content": user_message})

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.brigade_api_url}/api/v1/agents/{self.agent_id}/chat",
                    json={
                        "message": user_message,
                        "history": self._conversation_history[:-1],  # Exclude current message
                        "stream": False,
                    },
                    timeout=60.0,
                )
                response.raise_for_status()
                data = response.json()

                content = data.get("content", "")

                # Add to history
                self._conversation_history.append({"role": "assistant", "content": content})

                # Keep history manageable
                if len(self._conversation_history) > 20:
                    self._conversation_history = self._conversation_history[-20:]

                return content

        except Exception as e:
            logger.error(f"Failed to get agent response: {e}")
            return "I'm sorry, I'm having trouble processing that right now."

    async def _speak(self, text: str):
        """
        Synthesize and speak text using configured TTS provider.
        """
        provider = self.voice_config.tts_provider

        self._is_speaking = True

        try:
            if provider == TTSProvider.ELEVENLABS:
                await self._speak_elevenlabs(text)
            elif provider == TTSProvider.OPENAI:
                await self._speak_openai(text)
            else:
                await self._speak_openai(text)

        except Exception as e:
            logger.error(f"TTS error: {e}")
        finally:
            self._is_speaking = False

    async def _speak_elevenlabs(self, text: str):
        """Synthesize speech using ElevenLabs."""
        try:
            from livekit.plugins import elevenlabs

            tts = elevenlabs.TTS(
                voice=self.voice_config.voice_id or "Rachel",  # Default voice
            )

            # Generate audio
            audio_stream = await tts.synthesize(text)

            # Stream to room
            async for frame in audio_stream:
                if not self._is_speaking:  # Interrupted
                    break
                await self._audio_source.capture_frame(frame)

        except ImportError:
            logger.error("ElevenLabs plugin not installed: pip install livekit-plugins-elevenlabs")
            await self._speak_openai(text)  # Fallback

    async def _speak_openai(self, text: str):
        """Synthesize speech using OpenAI TTS."""
        try:
            import openai

            client = openai.AsyncOpenAI()

            # Use streaming TTS
            response = await client.audio.speech.create(
                model="tts-1",
                voice=self.voice_config.voice_id or "nova",
                input=text,
                response_format="pcm",
            )

            # Stream audio to room
            audio_data = response.content

            # Convert to frames and publish
            # Would need proper frame chunking in production
            frame_size = self.voice_config.sample_rate // 50  # 20ms frames

            for i in range(0, len(audio_data), frame_size * 2):  # 16-bit audio
                if not self._is_speaking:  # Interrupted
                    break

                frame_data = audio_data[i:i + frame_size * 2]
                # await self._audio_source.capture_frame(frame_data)
                await asyncio.sleep(0.02)  # ~20ms per frame

        except Exception as e:
            logger.error(f"OpenAI TTS error: {e}")

    async def _speak_greeting(self):
        """Speak initial greeting when agent joins."""
        greeting = self.agent_config.get("greeting") or (
            f"Hello! I'm {self.agent_name}. How can I help you today?"
        )

        await self._speak(greeting)

    async def _handle_interruption(self):
        """Handle user interrupting the agent's speech."""
        logger.info("Handling interruption")

        self._is_speaking = False

        # Cancel any ongoing TTS
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()

        if self._on_state_change:
            await self._on_state_change("interrupted", {})

    async def leave_room(self):
        """Leave the LiveKit room and clean up."""
        if self._room:
            await self._room.disconnect()
            self._room = None

        logger.info(f"Voice agent left room")

    def on_transcription(self, callback: Callable):
        """Register callback for transcription events."""
        self._on_transcription = callback

    def on_response(self, callback: Callable):
        """Register callback for response events."""
        self._on_response = callback

    def on_state_change(self, callback: Callable):
        """Register callback for state change events."""
        self._on_state_change = callback


# Factory function for creating voice agents
async def create_voice_agent(
    agent_id: str,
    voice_config: Optional[VoiceConfig] = None,
    brigade_api_url: Optional[str] = None,
) -> LiveKitVoiceAgent:
    """
    Create a voice agent for a Brigade agent.

    Fetches agent configuration from the Brigade API.
    """
    api_url = brigade_api_url or os.getenv("BRIGADE_API_URL", "http://localhost:8100")

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{api_url}/api/v1/agents/{agent_id}")
        response.raise_for_status()
        agent_config = response.json()

    return LiveKitVoiceAgent(
        agent_id=agent_id,
        agent_config=agent_config,
        voice_config=voice_config,
        brigade_api_url=api_url,
    )


# ============================================================================
# Registry-based Voice Agent Factory
# ============================================================================

async def create_voice_agent_with_registry(
    agent_id: str,
    stt_provider_name: Optional[str] = None,
    tts_provider_name: Optional[str] = None,
    brigade_api_url: Optional[str] = None,
) -> "LiveKitVoiceAgentWithRegistry":
    """
    Create a voice agent using the provider registry.

    This version uses self-hosted STT/TTS providers from the registry
    instead of cloud-based providers.

    Args:
        agent_id: ID of the Brigade agent
        stt_provider_name: STT provider name (uses config default if not specified)
        tts_provider_name: TTS provider name (uses config default if not specified)
        brigade_api_url: Brigade API URL

    Returns:
        LiveKitVoiceAgentWithRegistry instance
    """
    from app.voice.config import get_voice_config
    from app.voice.providers import VoiceProviderRegistry

    api_url = brigade_api_url or os.getenv("BRIGADE_API_URL", "http://localhost:8100")
    config = get_voice_config()

    # Get provider names from config if not specified
    stt_name = stt_provider_name or config.stt_provider
    tts_name = tts_provider_name or config.tts_provider

    # Get agent configuration
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{api_url}/api/v1/agents/{agent_id}")
        response.raise_for_status()
        agent_config = response.json()

    # Get providers from registry
    stt_provider = VoiceProviderRegistry.get_stt(stt_name, reuse_instance=True)
    tts_provider = VoiceProviderRegistry.get_tts(tts_name, reuse_instance=True)

    # Initialize providers
    await stt_provider.initialize()
    await tts_provider.initialize()

    return LiveKitVoiceAgentWithRegistry(
        agent_id=agent_id,
        agent_config=agent_config,
        stt_provider=stt_provider,
        tts_provider=tts_provider,
        brigade_api_url=api_url,
    )


class LiveKitVoiceAgentWithRegistry:
    """
    Voice agent that uses the provider registry for STT/TTS.

    This agent uses self-hosted providers (faster-whisper, kokoro, etc.)
    instead of cloud-based services.
    """

    def __init__(
        self,
        agent_id: str,
        agent_config: Dict[str, Any],
        stt_provider,  # STTProvider from registry
        tts_provider,  # TTSProvider from registry
        brigade_api_url: Optional[str] = None,
    ):
        from app.voice.config import get_voice_config

        self.agent_id = agent_id
        self.agent_config = agent_config
        self.stt_provider = stt_provider
        self.tts_provider = tts_provider
        self.brigade_api_url = brigade_api_url or os.getenv(
            "BRIGADE_API_URL", "http://localhost:8100"
        )
        self.voice_config = get_voice_config()

        # State
        self._room = None
        self._is_speaking = False
        self._is_listening = True
        self._conversation_history: List[Dict[str, str]] = []
        self._current_task: Optional[asyncio.Task] = None

        # Callbacks
        self._on_transcription: Optional[Callable] = None
        self._on_response: Optional[Callable] = None
        self._on_state_change: Optional[Callable] = None

        logger.info(
            f"LiveKitVoiceAgentWithRegistry initialized for agent: {agent_id}, "
            f"STT: {stt_provider.name}, TTS: {tts_provider.name}"
        )

    @property
    def agent_name(self) -> str:
        return self.agent_config.get("displayName") or self.agent_config.get("name", self.agent_id)

    @property
    def system_prompt(self) -> str:
        """Build system prompt from agent config."""
        parts = []

        if self.agent_config.get("persona"):
            parts.append(self.agent_config["persona"])

        if self.agent_config.get("systemPrompt"):
            parts.append(self.agent_config["systemPrompt"])

        parts.append(
            "You are now speaking via voice. Keep your responses concise and natural. "
            "Avoid using markdown, bullet points, or other text formatting. "
            "Speak conversationally as if talking to a person."
        )

        return "\n\n".join(parts) if parts else f"You are {self.agent_name}, a helpful AI assistant."

    async def transcribe(self, audio_bytes: bytes) -> str:
        """
        Transcribe audio using the registered STT provider.

        Args:
            audio_bytes: Audio data

        Returns:
            Transcribed text
        """
        result = await self.stt_provider.transcribe(
            audio_bytes,
            language=self.voice_config.stt_language,
        )

        # Handle different result types
        if hasattr(result, 'text'):
            return result.text
        return str(result)

    async def synthesize(self, text: str) -> bytes:
        """
        Synthesize speech using the registered TTS provider.

        Args:
            text: Text to synthesize

        Returns:
            Audio bytes
        """
        return await self.tts_provider.synthesize(
            text,
            voice=self.voice_config.tts_voice,
        )

    async def get_agent_response(self, user_message: str) -> str:
        """
        Get a response from the Brigade agent.

        Uses the existing chat endpoint which supports function calling.
        """
        self._conversation_history.append({"role": "user", "content": user_message})

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.brigade_api_url}/api/v1/agents/{self.agent_id}/chat",
                    json={
                        "message": user_message,
                        "history": self._conversation_history[:-1],
                        "stream": False,
                    },
                    timeout=60.0,
                )
                response.raise_for_status()
                data = response.json()

                content = data.get("content", "")

                self._conversation_history.append({"role": "assistant", "content": content})

                # Keep history manageable
                if len(self._conversation_history) > 20:
                    self._conversation_history = self._conversation_history[-20:]

                return content

        except Exception as e:
            logger.error(f"Failed to get agent response: {e}")
            return "I'm sorry, I'm having trouble processing that right now."

    async def process_voice_turn(self, audio_bytes: bytes) -> bytes:
        """
        Process a complete voice turn: transcribe -> respond -> synthesize.

        Args:
            audio_bytes: User's audio input

        Returns:
            Synthesized audio response
        """
        # Transcribe
        text = await self.transcribe(audio_bytes)
        if not text or len(text.strip()) < 2:
            return b""

        logger.info(f"Transcribed: {text[:100]}...")

        if self._on_transcription:
            await self._on_transcription(text)

        # Get response
        response = await self.get_agent_response(text)
        if not response:
            return b""

        logger.info(f"Agent response: {response[:100]}...")

        if self._on_response:
            await self._on_response(response)

        # Synthesize
        self._is_speaking = True
        try:
            audio = await self.synthesize(response)
            return audio
        finally:
            self._is_speaking = False

    def on_transcription(self, callback: Callable):
        """Register callback for transcription events."""
        self._on_transcription = callback

    def on_response(self, callback: Callable):
        """Register callback for response events."""
        self._on_response = callback

    def on_state_change(self, callback: Callable):
        """Register callback for state change events."""
        self._on_state_change = callback
