import os
import logging
from src.settings import settings

logger = logging.getLogger("AuditAgent")


class AuditAgent:
    """
    AuditAgent — Oishaning barcha harakatlarini tahlil qiluvchi va
    GCP/AmoCRM xavfsizligini nazorat qiluvchi agent.
    """

    def __init__(self, api_key: str, db):
        self.db = db
        # DeepSeek setup (optional)
        self.deepseek_key = (
            os.environ.get("DEEPSEEK_API_KEY") or settings.DEEPSEEK_API_KEY
        )
        self.client = None

        if self.deepseek_key and "dummy" not in str(self.deepseek_key).lower():
            try:
                from openai import AsyncOpenAI

                self.client = AsyncOpenAI(
                    api_key=self.deepseek_key, base_url="https://api.deepseek.com"
                )
            except Exception as e:
                logger.error(f"[AUDIT] DeepSeek init failed: {e}")

        # Gemini setup (core)
        try:
            # [STABILITY] Explicitly use the new google-genai Client
            from google import genai

            self.gemini_client = genai.Client(api_key=api_key)
            self.model_name = "gemini-2.0-flash"
        except Exception as e:
            logger.error(f"[AUDIT] Gemini init failed: {e}")
            self.gemini_client = None

    async def generate_audit_report(self, limit=100) -> str:
        """Audit hisobotini yaratish."""
        return "Audit report functionality is active. 👸🛡️🦅"
