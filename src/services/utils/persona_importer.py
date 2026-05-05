import json
import logging
import os
from database import Database  # type: ignore

logger = logging.getLogger(__name__)
db = Database()


class PersonaImporter:
    """Telegram JSON export fayllarini tahlil qilib, 'Miya'ga o'tkazish."""

    @staticmethod
    def import_from_json(file_path):
        """Telegram Desktop dan olingan result.json faylini o'qish."""
        if not os.path.exists(file_path):
            logger.error(f"[IMPORT] Fayl topilmadi: {file_path}")
            return False

        logger.info(f"[IMPORT] 10 yillik tarixni yuklash boshlandi: {file_path}")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Agar bu guruhlar/shaxsiy suhbatlar ro'yxati bo'lsa
            chats_data = data.get("chats", {})
            chats_list = []
            if isinstance(chats_data, dict):
                chats_list = chats_data.get("list", [])

            total_learned = 0

            for chat in chats_list:
                chat_name = str(chat.get("name", "Nomalum"))
                messages = chat.get("messages", [])

                # Muhim biznes suhbatlarini qidirish
                for msg in messages:
                    text_raw = msg.get("text", "")
                    text = ""
                    if isinstance(text_raw, list):
                        for part in text_raw:
                            if isinstance(part, dict):
                                text += str(part.get("text", ""))
                            else:
                                text += str(part)
                    else:
                        text = str(text_raw)

                    # Faqat uzun va mazmunli xabarlarni saqlash
                    if len(text) > 50 and any(
                        kw in text.lower()
                        for kw in [
                            "branding",
                            "agentlik",
                            "shartnoma",
                            "narx",
                            "loyiha",
                        ]
                    ):
                        fact = f"OTMISH BILIMI ({chat_name}, {msg.get('date')}): {text[:500]}"
                        db.add_learned_fact(0, fact)
                        total_learned += 1

            logger.info(
                f"[IMPORT] Yakunlandi. {total_learned} ta muhim fakt Miya ga qoshildi."
            )
            return True
        except Exception as e:
            logger.error(f"[IMPORT ERROR] {e}")
            return False


if __name__ == "__main__":
    PersonaImporter.import_from_json("result.json")
