#!/usr/bin/env python3
"""
LiveKit Voice Agent Worker

This worker runs as a separate process/container and handles voice
conversations with Brigade agents. It:

1. Polls for new voice rooms via the Brigade API
2. Connects to LiveKit rooms as a voice agent
3. Handles STT -> LLM -> TTS pipeline
4. Gracefully handles interruptions and room lifecycle

Usage:
    # Run directly
    python scripts/voice_agent_worker.py

    # Or via Docker
    docker-compose -f docker-compose.yml -f docker-compose.livekit.yml up -d livekit-agent
"""

import os
import sys
import asyncio
import logging
import signal
from typing import Optional, Dict, Any

import httpx

# Add app to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.voice import LiveKitVoiceAgent, VoiceConfig, STTProvider, TTSProvider

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("voice_agent_worker")

# Configuration
LIVEKIT_URL = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "devkey")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "REMOVED")
BRIGADE_API_URL = os.getenv("BRIGADE_API_URL", "http://localhost:8100")

# Voice provider configuration
STT_PROVIDER = os.getenv("VOICE_STT_PROVIDER", "deepgram")
TTS_PROVIDER = os.getenv("VOICE_TTS_PROVIDER", "openai")

# Polling interval for new rooms
POLL_INTERVAL = int(os.getenv("VOICE_POLL_INTERVAL", "5"))

# Active agents
active_agents: Dict[str, LiveKitVoiceAgent] = {}

# Shutdown flag
shutdown_event = asyncio.Event()


def get_voice_config() -> VoiceConfig:
    """Get voice configuration from environment."""
    return VoiceConfig(
        stt_provider=STTProvider(STT_PROVIDER),
        tts_provider=TTSProvider(TTS_PROVIDER),
        voice_id=os.getenv("OPENAI_TTS_VOICE") or os.getenv("ELEVENLABS_VOICE_ID"),
        language=os.getenv("VOICE_LANGUAGE", "en"),
        vad_enabled=os.getenv("VOICE_VAD_ENABLED", "true").lower() == "true",
        allow_interruptions=os.getenv("VOICE_ALLOW_INTERRUPTIONS", "true").lower() == "true",
    )


async def fetch_pending_rooms() -> list:
    """Fetch rooms waiting for an agent from the Brigade API."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BRIGADE_API_URL}/api/v1/voice/rooms",
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()

            # Filter to rooms we haven't joined yet
            rooms = data.get("rooms", [])
            pending = [
                room for room in rooms
                if room["id"] not in active_agents and room["status"] == "active"
            ]

            return pending

    except Exception as e:
        logger.error(f"Failed to fetch rooms: {e}")
        return []


async def fetch_agent_config(agent_id: str) -> Optional[Dict[str, Any]]:
    """Fetch agent configuration from Brigade API."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BRIGADE_API_URL}/api/v1/agents/{agent_id}",
                timeout=10.0,
            )
            response.raise_for_status()
            return response.json()

    except Exception as e:
        logger.error(f"Failed to fetch agent {agent_id}: {e}")
        return None


async def get_agent_token(room_id: str) -> Optional[str]:
    """Get token for agent to join room."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BRIGADE_API_URL}/api/v1/voice/rooms/{room_id}/agent/join",
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("agent_token")

    except Exception as e:
        logger.error(f"Failed to get agent token for room {room_id}: {e}")
        return None


async def join_room(room: Dict[str, Any]):
    """Create and connect a voice agent to a room."""
    room_id = room["id"]
    room_name = room["name"]
    agent_id = room["agent_id"]

    logger.info(f"Joining room {room_name} for agent {agent_id}")

    # Fetch agent configuration
    agent_config = await fetch_agent_config(agent_id)
    if not agent_config:
        logger.error(f"Could not fetch agent config for {agent_id}")
        return

    # Get agent token
    token = await get_agent_token(room_id)
    if not token:
        logger.error(f"Could not get token for room {room_id}")
        return

    # Create voice agent
    voice_config = get_voice_config()
    agent = LiveKitVoiceAgent(
        agent_id=agent_id,
        agent_config=agent_config,
        voice_config=voice_config,
        brigade_api_url=BRIGADE_API_URL,
    )

    # Set up event handlers
    @agent.on_transcription
    async def on_transcription(text: str, speaker: str):
        logger.info(f"[{room_name}] {speaker}: {text}")

    @agent.on_response
    async def on_response(response: str):
        logger.info(f"[{room_name}] Agent: {response[:100]}...")

    @agent.on_state_change
    async def on_state_change(event: str, data: Dict):
        logger.info(f"[{room_name}] State: {event} - {data}")

        if event == "participant_left" and len(room.get("participants", [])) <= 1:
            # Last participant left, close room
            logger.info(f"[{room_name}] Room empty, cleaning up...")
            await cleanup_room(room_id)

    try:
        # Connect to room
        await agent.join_room(token, LIVEKIT_URL)

        # Track active agent
        active_agents[room_id] = agent

        logger.info(f"Successfully joined room {room_name}")

    except Exception as e:
        logger.error(f"Failed to join room {room_name}: {e}")


async def cleanup_room(room_id: str):
    """Clean up a room and disconnect agent."""
    if room_id in active_agents:
        agent = active_agents[room_id]
        try:
            await agent.leave_room()
        except Exception as e:
            logger.warning(f"Error leaving room: {e}")
        del active_agents[room_id]
        logger.info(f"Cleaned up room {room_id}")


async def poll_rooms():
    """Main loop to poll for new rooms."""
    logger.info(f"Starting room polling (interval: {POLL_INTERVAL}s)")
    logger.info(f"Brigade API: {BRIGADE_API_URL}")
    logger.info(f"LiveKit URL: {LIVEKIT_URL}")

    while not shutdown_event.is_set():
        try:
            # Fetch pending rooms
            rooms = await fetch_pending_rooms()

            for room in rooms:
                # Join each pending room
                asyncio.create_task(join_room(room))

        except Exception as e:
            logger.error(f"Error in poll loop: {e}")

        # Wait for next poll or shutdown
        try:
            await asyncio.wait_for(
                shutdown_event.wait(),
                timeout=POLL_INTERVAL,
            )
        except asyncio.TimeoutError:
            pass  # Normal timeout, continue polling


async def cleanup_all():
    """Clean up all active agents on shutdown."""
    logger.info(f"Cleaning up {len(active_agents)} active agents...")

    tasks = [cleanup_room(room_id) for room_id in list(active_agents.keys())]
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

    logger.info("All agents cleaned up")


def handle_signal(sig):
    """Handle shutdown signals."""
    logger.info(f"Received signal {sig}, initiating shutdown...")
    shutdown_event.set()


async def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("LiveKit Voice Agent Worker Starting")
    logger.info("=" * 60)

    # Set up signal handlers
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda s=sig: handle_signal(s))

    try:
        # Verify Brigade API is accessible
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BRIGADE_API_URL}/api/v1/health",
                timeout=10.0,
            )
            response.raise_for_status()
            logger.info("Brigade API connection verified")

    except Exception as e:
        logger.warning(f"Could not verify Brigade API: {e}")
        logger.info("Will retry on first poll...")

    # Start polling
    try:
        await poll_rooms()
    finally:
        await cleanup_all()

    logger.info("Voice agent worker shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
