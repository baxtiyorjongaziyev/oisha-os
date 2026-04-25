import os
import logging
from google import genai
from typing import List, Dict, Any


logger = logging.getLogger(__name__)


class AuditAgent:
    """
    Foydalanuvchi harakatlarini tahlil qilib, unumdorlikni oshirish bo'yicha audit o'tkazuvchi agent.
    """


    def __init__(self, api_key: str, db):
        self.db = db
        self.deepseek_key = os.environ.get("DEEPSEEK_API_KEY") or getattr(self, 'settings_DEEPSEEK_API_KEY', None)
        self.client = None
        if self.deepseek_key and "dummy" not in self.deepseek_key.lower():
            try:
                from openai import AsyncOpenAI
                self.client = AsyncOpenAI(api_key=self.deepseek_key, base_url="https://api.deepseek.com")
            except Exception as e:
                logger.error(f"[AUDIT] DeepSeek init failed: {e}")
        else:
            logger.warning("[AUDIT] DeepSeek API key missing or dummy. Audit features will be limited.")
        self.gemini_client = genai.Client(api_key=api_key)
        self.model_name = 'gemini-2.0-flash'


    async def generate_audit_report(self, limit=100) -> str:
        """Oxirgi harakatlar asosida audit xulosasini tayyorlash."""
        try:
            # 1. Loglarni olish
            logs = self.db.get_recent_user_activity(limit=limit)
            if not logs:
                return "👸 Oisha-OS Audit: Hozircha tahlil qilish uchun yetarli ma'lumot yig'ilmadi. Biroz ko'proq muloqot qiling."


            # 2. Loglarni matn ko'rinishiga keltirish
            log_entries = []
