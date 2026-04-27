#!/usr/bin/env python3
"""
LiveKit Voice Agent Worker — Local Provider Edition

Connects to LiveKit rooms and runs the STT→LLM→TTS pipeline using
self-hosted Amanuensis (STT) and Orator (TTS) over HTTP.

Uses the raw LiveKit Python SDK (livekit.rtc) rather than the
livekit-agents framework to keep things simple and avoid cloud
provider dependencies.

Flow:
  1. Poll Brigade API for active voice rooms
  2. Join rooms via LiveKit RTC
  3. Subscribe to user audio tracks
  4. Accumulate speech frames using energy-based VAD
  5. POST audio → Amanuensis (STT) → text
  6. POST text  → Brigade API (LLM) → response
  7. POST text  → Orator (TTS) → audio
  8. Publish synthesized audio back to LiveKit room

Usage:
    python scripts/voice_agent_worker.py
"""

import os
import sys
import io
import wave
import struct
import asyncio
import logging
import signal
from typing import Optional, Dict, Any, List

import httpx
import numpy as np

# Add app to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ============================================================================
# Configuration
# ============================================================================

LIVEKIT_URL = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "unicorn")
LIVEKIT_API_SECRET = os.getenv(
    "LIVEKIT_API_SECRET", "unicorn-brigade-secret-key-change-me"
)
BRIGADE_API_URL = os.getenv("BRIGADE_API_URL", "http://localhost:8100")
BRIGADE_API_KEY = os.getenv("BRIGADE_API_KEY", "")

AMANUENSIS_URL = os.getenv("AMANUENSIS_URL", "http://unicorn-amanuensis:9000")
ORATOR_URL = os.getenv("ORATOR_URL", "http://unicorn-orator:8880")

POLL_INTERVAL = int(os.getenv("VOICE_POLL_INTERVAL", "3"))
SAMPLE_RATE = 16000  # LiveKit default for audio tracks
TTS_SAMPLE_RATE = 24000  # Orator outputs 24kHz

# VAD settings (energy-based)
VAD_ENERGY_THRESHOLD = float(os.getenv("VAD_ENERGY_THRESHOLD", "300"))
VAD_SILENCE_FRAMES = int(os.getenv("VAD_SILENCE_FRAMES", "30"))  # ~600ms at 20ms/frame
VAD_MIN_SPEECH_FRAMES = int(os.getenv("VAD_MIN_SPEECH_FRAMES", "5"))  # ~100ms

# Agent voice mapping (agent_id → Orator voice)
AGENT_VOICES = {
    "sgt-carter-knox": "jean",
    "the-general": "javert",
    "gunny": "marius",
    "detective-holmes": "alba",
}
DEFAULT_VOICE = "alba"

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("voice_agent_worker")

# Shutdown event
shutdown_event = asyncio.Event()

# Track active room tasks
active_rooms: Dict[str, asyncio.Task] = {}


# ============================================================================
# Audio Utilities
# ============================================================================


def pcm_to_wav_bytes(pcm: bytes, sample_rate: int = SAMPLE_RATE, channels: int = 1, sample_width: int = 2) -> bytes:
    """Convert raw PCM int16 bytes to a WAV byte buffer."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()


def frame_energy(data: bytes) -> float:
    """Compute RMS energy of a PCM int16 frame."""
    if len(data) < 2:
        return 0.0
    samples = np.frombuffer(data, dtype=np.int16)
    return float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))


def resample_pcm(pcm: bytes, from_rate: int, to_rate: int) -> bytes:
    """Simple linear resampling of PCM int16 data."""
    if from_rate == to_rate:
        return pcm
    samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float64)
    ratio = to_rate / from_rate
    new_len = int(len(samples) * ratio)
    indices = np.linspace(0, len(samples) - 1, new_len)
    resampled = np.interp(indices, np.arange(len(samples)), samples)
    return resampled.astype(np.int16).tobytes()


# ============================================================================
# Provider Clients (HTTP)
# ============================================================================


async def transcribe(audio_wav: bytes, client: httpx.AsyncClient) -> str:
    """Transcribe WAV audio via Amanuensis."""
    try:
        resp = await client.post(
            f"{AMANUENSIS_URL}/v1/audio/transcriptions",
            files={"file": ("audio.wav", audio_wav, "audio/wav")},
            data={"model": "base", "response_format": "json", "language": "en"},
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json().get("text", "").strip()
    except Exception as e:
        logger.error(f"STT error: {e}")
        return ""


async def synthesize(text: str, voice: str, client: httpx.AsyncClient) -> bytes:
    """Synthesize speech via Orator. Returns PCM int16 bytes at 24kHz."""
    try:
        resp = await client.post(
            f"{ORATOR_URL}/v1/audio/speech",
            json={"text": text, "voice": voice, "speed": 1.0},
            timeout=60.0,
        )
        resp.raise_for_status()
        wav_bytes = resp.content

        # Decode WAV to PCM
        buf = io.BytesIO(wav_bytes)
        with wave.open(buf, "rb") as wf:
            pcm = wf.readframes(wf.getnframes())
        return pcm
    except Exception as e:
        logger.error(f"TTS error: {e}")
        return b""


async def get_llm_response(
    agent_id: str,
    message: str,
    history: List[Dict[str, str]],
    client: httpx.AsyncClient,
) -> str:
    """Get LLM response from Brigade API."""
    headers = {}
    if BRIGADE_API_KEY:
        headers["X-API-Key"] = BRIGADE_API_KEY

    try:
        resp = await client.post(
            f"{BRIGADE_API_URL}/api/v1/agents/{agent_id}/chat",
            json={"message": message, "history": history, "stream": False},
            headers=headers,
            timeout=60.0,
        )
        resp.raise_for_status()
        return resp.json().get("content", "")
    except Exception as e:
        logger.error(f"LLM error: {e}")
        return "I'm sorry, I'm having trouble processing that right now."


# ============================================================================
# Room Polling
# ============================================================================


async def fetch_pending_rooms(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    """Fetch active voice rooms from Brigade API."""
    headers = {}
    if BRIGADE_API_KEY:
        headers["X-API-Key"] = BRIGADE_API_KEY

    try:
        resp = await client.get(
            f"{BRIGADE_API_URL}/api/v1/voice/rooms",
            headers=headers,
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
        rooms = data.get("rooms", [])
        return [r for r in rooms if r.get("status") == "active" and r["id"] not in active_rooms]
    except Exception as e:
        logger.error(f"Failed to fetch rooms: {e}")
        return []


async def get_agent_token(room_id: str, client: httpx.AsyncClient) -> Optional[str]:
    """Get a LiveKit token for the agent to join a room."""
    headers = {}
    if BRIGADE_API_KEY:
        headers["X-API-Key"] = BRIGADE_API_KEY

    try:
        resp = await client.post(
            f"{BRIGADE_API_URL}/api/v1/voice/rooms/{room_id}/agent/join",
            headers=headers,
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json().get("agent_token")
    except Exception as e:
        logger.error(f"Failed to get agent token for room {room_id}: {e}")
        return None


# ============================================================================
# Voice Agent Room Handler
# ============================================================================


async def handle_room(room_info: Dict[str, Any]):
    """
    Join a LiveKit room as a voice agent and handle the conversation.

    This function:
    1. Joins the room via LiveKit RTC
    2. Publishes an audio output track
    3. Subscribes to user audio tracks
    4. Runs VAD → STT → LLM → TTS pipeline on detected speech
    """
    from livekit import rtc

    room_id = room_info["id"]
    room_name = room_info.get("name", room_id)
    agent_id = room_info.get("agent_id", "")
    voice = AGENT_VOICES.get(agent_id, DEFAULT_VOICE)

    logger.info(f"Joining room {room_name} for agent {agent_id} (voice: {voice})")

    async with httpx.AsyncClient() as client:
        # Get token
        token = await get_agent_token(room_id, client)
        if not token:
            logger.error(f"No token for room {room_id}, skipping")
            return

        # Connect to room
        room = rtc.Room()
        try:
            await room.connect(LIVEKIT_URL, token)
        except Exception as e:
            logger.error(f"Failed to connect to room {room_name}: {e}")
            return

        logger.info(f"Connected to room {room_name}")

        # Create audio source for agent output (24kHz mono to match Orator)
        audio_source = rtc.AudioSource(TTS_SAMPLE_RATE, 1)
        track = rtc.LocalAudioTrack.create_audio_track("agent-voice", audio_source)
        await room.local_participant.publish_track(track)
        logger.info("Published agent audio track")

        # State — use a mutable container so nested closures can modify it
        state = {"is_speaking": False}
        conversation_history: List[Dict[str, str]] = []

        async def speak(text: str):
            """Synthesize and publish audio."""
            state["is_speaking"] = True
            try:
                pcm = await synthesize(text, voice, client)
                if not pcm:
                    return

                # Push audio in 20ms frames at 24kHz
                frame_samples = TTS_SAMPLE_RATE // 50  # 480 samples per 20ms
                frame_bytes = frame_samples * 2  # 16-bit = 2 bytes/sample

                for i in range(0, len(pcm), frame_bytes):
                    if not state["is_speaking"]:
                        break  # Interrupted
                    chunk = pcm[i : i + frame_bytes]
                    if len(chunk) < frame_bytes:
                        # Pad last frame
                        chunk += b"\x00" * (frame_bytes - len(chunk))

                    frame = rtc.AudioFrame(
                        data=chunk,
                        sample_rate=TTS_SAMPLE_RATE,
                        num_channels=1,
                        samples_per_channel=frame_samples,
                    )
                    await audio_source.capture_frame(frame)
                    await asyncio.sleep(0.018)  # ~20ms pacing
            except Exception as e:
                logger.error(f"Speak error: {e}")
            finally:
                state["is_speaking"] = False

        async def process_speech(audio_pcm: bytes, speaker: str):
            """Run STT → LLM → TTS pipeline."""
            nonlocal conversation_history

            # Convert PCM to WAV for Amanuensis
            wav_data = pcm_to_wav_bytes(audio_pcm, SAMPLE_RATE)

            # STT
            text = await transcribe(wav_data, client)
            if not text or len(text.strip()) < 2:
                logger.debug("No meaningful transcription, skipping")
                return

            logger.info(f"[{room_name}] {speaker}: {text}")

            # LLM
            response = await get_llm_response(agent_id, text, conversation_history, client)
            if not response:
                return

            # Update history
            conversation_history.append({"role": "user", "content": text})
            conversation_history.append({"role": "assistant", "content": response})
            if len(conversation_history) > 20:
                conversation_history = conversation_history[-20:]

            logger.info(f"[{room_name}] Agent: {response[:100]}...")

            # Clean markdown for TTS
            clean_response = clean_for_tts(response)

            # TTS + playback
            await speak(clean_response)

        async def process_audio_track(audio_track: rtc.Track, participant_identity: str):
            """Process incoming audio from a participant with VAD."""
            logger.info(f"Processing audio from {participant_identity}")

            audio_stream = rtc.AudioStream(audio_track)
            audio_buffer = bytearray()
            silence_count = 0
            speech_count = 0
            in_speech = False

            async for event in audio_stream:
                frame = event.frame
                data = bytes(frame.data)

                energy = frame_energy(data)

                if energy > VAD_ENERGY_THRESHOLD:
                    speech_count += 1
                    silence_count = 0

                    if not in_speech and speech_count >= VAD_MIN_SPEECH_FRAMES:
                        in_speech = True
                        logger.debug("Speech started")

                    if in_speech:
                        audio_buffer.extend(data)

                        # Barge-in: interrupt agent if user starts talking
                        if state["is_speaking"]:
                            state["is_speaking"] = False
                            logger.info("Barge-in detected, stopping agent speech")
                else:
                    speech_count = 0

                    if in_speech:
                        silence_count += 1
                        audio_buffer.extend(data)  # Include trailing silence

                        if silence_count >= VAD_SILENCE_FRAMES:
                            # End of speech — process
                            in_speech = False
                            if len(audio_buffer) > SAMPLE_RATE * 2 * 0.3:  # >300ms
                                pcm_data = bytes(audio_buffer)
                                audio_buffer = bytearray()
                                await process_speech(pcm_data, participant_identity)
                            else:
                                audio_buffer = bytearray()
                                logger.debug("Speech too short, discarding")

        # Handle track subscriptions
        @room.on("track_subscribed")
        def on_track_subscribed(
            track: rtc.Track,
            publication: rtc.RemoteTrackPublication,
            participant: rtc.RemoteParticipant,
        ):
            if track.kind == rtc.TrackKind.KIND_AUDIO:
                logger.info(f"Subscribed to audio from {participant.identity}")
                asyncio.create_task(process_audio_track(track, participant.identity))

        @room.on("participant_disconnected")
        def on_participant_disconnected(participant: rtc.RemoteParticipant):
            logger.info(f"Participant left: {participant.identity}")
            # Check if room is empty (no remote participants)
            if len(room.remote_participants) == 0:
                logger.info(f"Room {room_name} is empty, disconnecting")
                asyncio.create_task(room.disconnect())

        @room.on("disconnected")
        def on_disconnected():
            logger.info(f"Disconnected from room {room_name}")

        # Send greeting
        greeting = f"Hello, I'm here. How can I help?"
        logger.info(f"Sending greeting for {agent_id}")
        await speak(greeting)

        # Wait until disconnected or shutdown
        try:
            while room.connection_state == rtc.ConnectionState.CONN_CONNECTED:
                if shutdown_event.is_set():
                    break
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            if room.connection_state == rtc.ConnectionState.CONN_CONNECTED:
                await room.disconnect()
            logger.info(f"Room handler for {room_name} finished")


# ============================================================================
# Text Cleaning
# ============================================================================


def clean_for_tts(text: str) -> str:
    """Strip markdown formatting for cleaner TTS output."""
    import re

    # Remove code blocks
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)

    # Remove headers
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)

    # Remove bold/italic
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"_(.+?)_", r"\1", text)

    # Remove links [text](url) → text
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)

    # Remove bullet points
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)

    # Collapse whitespace
    text = re.sub(r"\n{2,}", ". ", text)
    text = re.sub(r"\n", " ", text)
    text = re.sub(r"\s{2,}", " ", text)

    return text.strip()


# ============================================================================
# Main Loop
# ============================================================================


async def poll_loop():
    """Main polling loop: discover rooms and join them."""
    logger.info("=" * 60)
    logger.info("LiveKit Voice Agent Worker (Local Providers)")
    logger.info("=" * 60)
    logger.info(f"  LiveKit:     {LIVEKIT_URL}")
    logger.info(f"  Brigade API: {BRIGADE_API_URL}")
    logger.info(f"  STT:         {AMANUENSIS_URL}")
    logger.info(f"  TTS:         {ORATOR_URL}")
    logger.info(f"  Poll:        every {POLL_INTERVAL}s")
    logger.info("=" * 60)

    # Verify services
    async with httpx.AsyncClient() as client:
        for name, url, path in [
            ("Brigade API", BRIGADE_API_URL, "/api/v1/health"),
            ("Amanuensis STT", AMANUENSIS_URL, "/health"),
            ("Orator TTS", ORATOR_URL, "/health"),
        ]:
            try:
                resp = await client.get(f"{url}{path}", timeout=5.0)
                if resp.status_code == 200:
                    logger.info(f"  {name}: OK")
                else:
                    logger.warning(f"  {name}: HTTP {resp.status_code}")
            except Exception as e:
                logger.warning(f"  {name}: unreachable ({e})")

    async with httpx.AsyncClient() as client:
        while not shutdown_event.is_set():
            try:
                rooms = await fetch_pending_rooms(client)
                for room in rooms:
                    room_id = room["id"]
                    if room_id not in active_rooms:
                        task = asyncio.create_task(handle_room(room))
                        active_rooms[room_id] = task

                        # Cleanup completed tasks
                        def cleanup(t, rid=room_id):
                            active_rooms.pop(rid, None)
                            if t.exception():
                                logger.error(f"Room {rid} error: {t.exception()}")

                        task.add_done_callback(cleanup)

            except Exception as e:
                logger.error(f"Poll error: {e}")

            try:
                await asyncio.wait_for(shutdown_event.wait(), timeout=POLL_INTERVAL)
            except asyncio.TimeoutError:
                pass


async def main():
    """Entry point."""
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: shutdown_event.set())

    try:
        await poll_loop()
    finally:
        # Cancel active room handlers
        for rid, task in list(active_rooms.items()):
            task.cancel()
        if active_rooms:
            await asyncio.gather(*active_rooms.values(), return_exceptions=True)
        logger.info("Voice agent worker shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
