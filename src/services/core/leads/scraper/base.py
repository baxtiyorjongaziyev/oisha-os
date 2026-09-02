"""
Base helpers, contact name formatting, and AI intro parsing for lead scraper.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("LeadScraper")


class BaseScraperMixin:
    """State tracking and name normalization utilities."""

    def _is_processed(self, user_id: int) -> bool:
        return user_id in self.processed_users

    def _mark_processed(self, user_id: int) -> None:
        self.processed_users.add(user_id)

    def format_contact_name(
        self,
        first_name: str,
        last_name: str = "",
        lead_data: Dict[str, Any] = None,
        is_tn5: bool = False,
    ) -> str:
        """
        Guruh a'zosi yoki DM-murojaati uchun chiroyli ism formatini yaratish.
        Agar TN5 guruhidab bo'lsa: 'Ism Familiya TN5 Gr'
        Aks holda: 'Ism Familiya Shahar Sohasi Brand' (mavjudligiga qarab)
        """
        # 1. TN5 logic (Primary override)
        if is_tn5:
            full = f"{first_name} {last_name}".strip()
            return f"{full} TN5 Gr".strip()

        # 2. Detailed logic (Enterprise standard)
        parts = [first_name, last_name]

        if lead_data:
            # We check for keys from AutoLeadAgent extraction
            for key in ["city", "activity", "brand_name"]:
                val = lead_data.get(key)
                if val and str(val).lower() not in [
                    "noma'lum",
                    "unknown",
                    "none",
                    "",
                    "null",
                    "no'malum",
                ]:
                    # Clean up common AI filler
                    val_clean = str(val).strip()
                    if val_clean.lower() != "nomsiz":
                        parts.append(val_clean)

        # Join and remove redundant spaces
        final_name = " ".join([p for p in parts if p]).strip()

        # Limit length if necessary for contact sync (Optional, but good for stability)
        return final_name[:64]

    async def parse_intro_with_ai(self, text: str) -> Optional[Dict[str, Any]]:
        """Introductsiyani Gemini orqali tahlil qilish."""
        prompt = (
            "Quyidagi xabar Telegram guruhidagi 'Intro' xabari. "
            "Undan foydalanuvchining ismi, telefon raqami va faoliyat sohasini ajratib oling. "
            "Faqat JSON formatida javob bering.\n\n"
            f"Xabar: {text}\n\n"
            'Format: {"name": "...", "phone": "...", "work": "..."}'
        )

        system_instruction = "Siz tajribali ma'lumot tahlilchisisiz. Telegram xabarlaridan lidlar ma'lumotlarini ajratib olishga ixtisoslashgansiz."

        try:
            from src.utils.ai_utils import safe_ai_call

            response = await safe_ai_call(
                client=self.genai_client,
                prompt=prompt,
                system_instruction=system_instruction,
                model=self.model_name,
                mime_type="application/json",
            )

            if response and response.text:
                return json.loads(response.text)
        except Exception as e:
            logger.error(f"[LEAD_SCRAPER] AI Parsing Error: {e}")
            return None
