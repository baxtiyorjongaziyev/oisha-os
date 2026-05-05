import edge_tts  # type: ignore
import os
import re
import logging
import config  # type: ignore

logger = logging.getLogger(__name__)


class TTSEngine:
    def __init__(self, voice="uz-UZ-MadinaNeural"):
        self.voice = voice
        self.output_dir = "temp_audio"
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    async def generate_audio(self, text, filename="response.mp3"):
        """Matnni audio faylga aylantirish."""
        path = os.path.join(self.output_dir, filename)

        # HTML taglarni tozalash (TTS uchun)
        text_str = str(text or "")
        clean_text = re.sub(r"<[^>]+>", "", text_str)

        # Maxsus o'qilishlarni sozlash (O'zbek tili uchun)
        # 1. "00" ni to'g'ri o'qish ("oh oh" demasligi uchun)
        clean_text = re.sub(r"\b00\b", "no'l no'l", clean_text)

        # 2. Soat formatlarini to'g'rilash (masalan: 15:00 -> 15 no'l no'l)
        clean_text = re.sub(r"(\d{1,2}):00", r"\1 no'l no'l", clean_text)
        clean_text = re.sub(r"(\d{1,2}):(\d{2})", r"\1 dan \2 daqiqa o'tdi", clean_text)

        # 3. Katta raqamlardagi nuqtalarni yoki probellarni tozalash (1 000 000 -> 1000000)
        # edge-tts odatda yaxshi o'qiydi, shunday qolsa ham arziydi

        try:
            # Mohir.ai integratsiyasi
            if (
                config.TTS_PROVIDER == "mohir"
                and hasattr(config, "MOHIR_API_KEY")
                and config.MOHIR_API_KEY
            ):
                try:
                    import requests

                    logger.info(
                        f"[TTS] Mohir.ai orqali audio generatsiya qilinmoqda: {clean_text[:50]}..."
                    )
                    headers = {"Authorization": config.MOHIR_API_KEY}
                    json_data = {"text": clean_text, "model": "uz-lat", "format": "mp3"}
                    response = requests.post(
                        "https://api.mohir.ai/api/v1/tts",
                        headers=headers,
                        json=json_data,
                        timeout=15,
                    )
                    if response.status_code == 200:
                        with open(path, "wb") as f:
                            f.write(response.content)
                        return path
                    else:
                        logger.error(
                            f"[TTS ERROR] Mohir.ai status: {response.status_code}, Response: {response.text}"
                        )
                except Exception as e:
                    logger.error(f"[TTS ERROR] Mohir.ai xatosi: {e}")

            # ElevenLabs integratsiyasi (Ultra-Agent Voice Cloning)
            if config.TTS_PROVIDER == "elevenlabs" and config.ELEVENLABS_API_KEY:
                from elevenlabs.client import ElevenLabs  # type: ignore

                client = ElevenLabs(api_key=config.ELEVENLABS_API_KEY)

                logger.info("[TTS] ElevenLabs orqali audio yaratilmoqda...")
                audio_gen = client.generate(
                    text=clean_text,
                    voice=(
                        config.ELEVENLABS_VOICE_ID
                        if config.ELEVENLABS_VOICE_ID
                        else "Bella"
                    ),
                    model="eleven_multilingual_v2",
                )
                # Iterator natijasini faylga yozish
                with open(path, "wb") as f:
                    for chunk in audio_gen:
                        if chunk:
                            f.write(chunk)
                return path

            # Standart / Fallback: edge-tts
            logger.info("[TTS] edge-tts orqali audio yaratilmoqda...")
            communicate = edge_tts.Communicate(
                clean_text, self.voice, rate="-10%", pitch="+15Hz"
            )
            await communicate.save(path)
            return path
        except Exception as e:
            logger.error(f"[TTS ERROR] Audio yaratishda xato: {e}")
            # Agar ElevenLabs xato bersa, edge-tts ga o'tamiz
            if config.TTS_PROVIDER == "elevenlabs":
                try:
                    logger.warning("[TTS] ElevenLabs xatosi, edge-tts ga qaytildi.")
                    communicate = edge_tts.Communicate(
                        clean_text, self.voice, rate="-10%", pitch="+15Hz"
                    )
                    await communicate.save(path)
                    return path
                except Exception:
                    pass
            return None

    def cleanup(self, path):
        """Vaqtinchalik faylni o'chirish."""
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except Exception as e:
            logger.error(f"[TTS ERROR] Faylni o'chirishda xato: {e}")
