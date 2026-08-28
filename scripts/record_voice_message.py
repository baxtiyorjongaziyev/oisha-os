"""Voice message recording script for Uzbek Entrepreneurs system.

Usage:
    python scripts/record_voice_message.py --text "Assalomu alaykum..." --output voice_message.mp3
"""
import argparse
import logging
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.settings import settings

logger = logging.getLogger(__name__)


def record_with_gemini(text: str, output_path: str) -> bool:
    """Record voice message using Google Gemini TTS."""
    try:
        gemini_key = settings.GEMINI_API_KEY.get_secret_value() if settings.GEMINI_API_KEY else None
        if not gemini_key:
            logger.error("GEMINI_API_KEY not set")
            return False

        # For now, placeholder - Gemini doesn't have direct TTS
        # We'll use a different service
        logger.warning("Gemini TTS not directly available, using placeholder")
        return False

    except Exception as e:
        logger.error(f"Gemini TTS failed: {e}")
        return False


def record_with_openai(text: str, output_path: str) -> bool:
    """Record voice message using OpenAI TTS."""
    try:
        from openai import OpenAI

        openai_key = settings.OPENAI_API_KEY.get_secret_value() if settings.OPENAI_API_KEY else None
        if not openai_key:
            logger.error("OPENAI_API_KEY not set")
            return False

        client = OpenAI(api_key=openai_key)

        response = client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=text,
        )

        response.stream_to_file(output_path)
        logger.info(f"Voice message saved to: {output_path}")
        return True

    except Exception as e:
        logger.error(f"OpenAI TTS failed: {e}")
        return False


def record_with_elevenlabs(text: str, output_path: str) -> bool:
    """Record voice message using ElevenLabs TTS."""
    try:
        import requests

        elevenlabs_key = os.getenv("ELEVENLABS_API_KEY")
        if not elevenlabs_key:
            logger.error("ELEVENLABS_API_KEY not set")
            return False

        url = "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": elevenlabs_key,
        }
        data = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.5},
        }

        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200:
            with open(output_path, "wb") as f:
                f.write(response.content)
            logger.info(f"Voice message saved to: {output_path}")
            return True
        else:
            logger.error(f"ElevenLabs API error: {response.status_code}")
            return False

    except Exception as e:
        logger.error(f"ElevenLabs TTS failed: {e}")
        return False


def get_default_uzbek_script() -> str:
    """Get default Uzbek voice script."""
    return """Assalomu alaykum! Men Jon Branding agentligidan qo'ng'iroq qilyapman.

Biz global O'zbek tadbirkorlari uchun maxsus brending va marketing xizmatlarini taklif qilamiz.

Agar siz brending, dizayn yoki marketing bo'yicha professional yordam kerak bo'lsa, 1 ni bosing.

Agar hozir vaqtingiz yo'q bo'lsa, keyin qo'ng'iroq qilishimiz uchun 2 ni bosing.

Rahmat!"""


def main():
    parser = argparse.ArgumentParser(description="Record voice message for auto-calling")
    parser.add_argument(
        "--text",
        type=str,
        default=get_default_uzbek_script(),
        help="Text to convert to speech",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/voice_message.mp3",
        help="Output MP3 file path",
    )
    parser.add_argument(
        "--provider",
        type=str,
        choices=["openai", "elevenlabs", "gemini"],
        default="openai",
        help="TTS provider to use",
    )

    args = parser.parse_args()

    # Create output directory if needed
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    logger.info(f"Recording voice message using {args.provider}...")
    logger.info(f"Text: {args.text[:100]}...")

    success = False
    if args.provider == "openai":
        success = record_with_openai(args.text, args.output)
    elif args.provider == "elevenlabs":
        success = record_with_elevenlabs(args.text, args.output)
    elif args.provider == "gemini":
        success = record_with_gemini(args.text, args.output)

    if success:
        logger.info(f"✅ Voice message saved successfully: {args.output}")
        print(f"\n📞 Voice message ready!")
        print(f"📁 File: {args.output}")
        print(f"🔗 Upload this to your cloud storage and set VAPI_VOICE_URL in .env")
        return 0
    else:
        logger.error("❌ Failed to record voice message")
        return 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.exit(main())
