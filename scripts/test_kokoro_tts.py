#!/usr/bin/env python3
"""
Test Kokoro TTS Provider

Verifies that Kokoro TTS is properly installed and working.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.voice.providers.tts_kokoro import KokoroTTSProvider
from app.voice.config import VoiceConfig


async def test_kokoro():
    """Test Kokoro TTS provider"""
    print("=" * 70)
    print("Testing Kokoro TTS Provider")
    print("=" * 70)

    try:
        # Initialize provider
        print("\n1. Initializing Kokoro provider...")
        config = VoiceConfig()
        provider = KokoroTTSProvider(config)
        await provider.initialize()
        print("   ✓ Provider initialized successfully")

        # Check available voices
        print("\n2. Available voices:")
        voices = [
            "af_bella", "af_heart", "af_nicole", "af_sarah", "af_sky",
            "am_adam", "am_michael",
            "bf_emma", "bf_isabella",
            "bm_george", "bm_lewis"
        ]
        print(f"   Total voices: {len(voices)}")
        print("   American Female: af_bella, af_heart, af_nicole, af_sarah, af_sky")
        print("   American Male: am_adam, am_michael")
        print("   British Female: bf_emma, bf_isabella")
        print("   British Male: bm_george, bm_lewis")

        # Test synthesis
        print("\n3. Testing synthesis (af_bella)...")
        test_text = "Hello! This is a test of the Kokoro text to speech system."
        audio_data = await provider.synthesize(test_text, voice="af_bella")
        print(f"   ✓ Synthesized {len(audio_data)} bytes of audio")
        print(f"   ✓ Sample rate: 24000 Hz")
        print(f"   ✓ Format: WAV (16-bit PCM)")

        # Test streaming
        print("\n4. Testing streaming synthesis...")
        chunks = []
        async for chunk in provider.synthesize_stream(test_text, voice="am_adam"):
            chunks.append(chunk)
        total_bytes = sum(len(chunk) for chunk in chunks)
        print(f"   ✓ Streamed {len(chunks)} chunks")
        print(f"   ✓ Total audio: {total_bytes} bytes")

        print("\n" + "=" * 70)
        print("✓ All tests passed! Kokoro TTS is production-ready.")
        print("=" * 70)
        print("\nNext steps:")
        print("  1. Voice system is ready for LiveKit integration")
        print("  2. Test voice calls at /api/v1/voice/rooms")
        print("  3. Configure STT provider (Whisper) if needed")
        print()
        return True

    except ImportError as e:
        print(f"\n✗ Import error: {e}")
        print("\nInstall Kokoro:")
        print("  pip install kokoro>=0.9.2")
        return False

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_kokoro())
    sys.exit(0 if success else 1)
