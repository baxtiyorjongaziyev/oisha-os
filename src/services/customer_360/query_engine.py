"""
Customer 360 AI Query Engine.

Answers complex questions about any client across all five dimensions
(Voice Calls STT, AmoCRM, Airtable, Telegram, and Instagram).
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

from src.services.customer_360.collector import Customer360Collector
from src.services.customer_360.models import Customer360Profile
from src.services.customer_360.obsidian_syncer import DEFAULT_VAULT_PATHS

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_UZ = """
Siz JonBranding agentligining Customer 360 AI Tahlilchisisiz.
Sizga mijozning barcha kanallari (Telefon qo'ng'iroqlari STT, AmoCRM, Airtable, Telegram, Instagram) bo'yicha birlashtirilgan profili beriladi.
Foydalanuvchining savoliga qisqa, lo'nda, aniq va professional biznes tilda o'zbekcha javob bering.

Javobingiz quyidagi tuzilishga ega bo'lsin:
1. 👤 **Mijoz va Status:** Kim, qaysi kompaniya, asosiy aloqa kanali.
2. 📞 **Telefon & AI Tahlili (STT):** Oxirgi qo'ng'iroqda nima gaplashilgan, sotuvchining bahosi, mijozning kayfiyati, kelishilgan sana.
3. 📊 **AmoCRM & Sotuv:** Byudjet, voronka bosqichi, mas'ul menejer.
4. 🎨 **Airtable & Ijro:** Qaysi dizayn bosqichida, qancha to'lagan, qancha qarz bor, deadline.
5. 💬 **Telegram / Instagram:** Muloqotdagi muhim kelishuvlar.
6. 🎯 **Keyingi Tavsiya:** Hozir nima qilish kerak?

Agar qaysidir ma'lumot (masalan, hali qo'ng'iroq bo'lmagan bo'lsa) mavjud bo'lmasa, uni to'g'ri ko'rsating ("Ma'lumot yo'q" yoki "Hali qo'ng'iroq bo'lmagan").
"""


class Customer360QueryEngine:
    """Answers user queries about clients with full 360-degree context."""

    def __init__(
        self,
        collector: Optional[Customer360Collector] = None,
        vault_paths: Optional[List[str]] = None,
        gemini_api_key: Optional[str] = None,
    ) -> None:
        self.collector = collector or Customer360Collector()
        self.vault_paths = [p for p in (vault_paths or DEFAULT_VAULT_PATHS) if os.path.exists(p)]
        self.gemini_api_key = gemini_api_key or os.getenv("GEMINI_API_KEY")

    def _find_obsidian_card(self, client_query: str) -> Optional[str]:
        """Search for existing Obsidian customer card in 20-CLIENTS and 70-Mijozlar."""
        clean = client_query.strip().lower()
        for vault in self.vault_paths:
            # 1. Search in 20-CLIENTS
            c20 = os.path.join(vault, "20-CLIENTS")
            if os.path.exists(c20):
                for root, _, files in os.walk(c20):
                    for f in files:
                        if f.endswith(".md"):
                            f_low = f.lower()
                            folder_low = os.path.basename(root).lower()
                            if clean in f_low or clean in folder_low:
                                filepath = os.path.join(root, f)
                                try:
                                    with open(filepath, "r", encoding="utf-8", errors="ignore") as fp:
                                        return fp.read()
                                except Exception as e:
                                    logger.debug(f"[C360] Read error {filepath}: {e}")

            # 2. Fallback in 70-Mijozlar
            folder = os.path.join(vault, "70-Mijozlar")
            if os.path.exists(folder):
                for f in os.listdir(folder):
                    if f.endswith(".md"):
                        name_part = f[:-3].lower()
                        if clean in name_part or name_part in clean:
                            filepath = os.path.join(folder, f)
                            try:
                                with open(filepath, "r", encoding="utf-8", errors="ignore") as fp:
                                    return fp.read()
                            except Exception as e:
                                logger.debug(f"[C360] Read error {filepath}: {e}")
        return None

    async def answer_query(self, query: str, client_name_or_phone: Optional[str] = None) -> str:
        """Process user query and return comprehensive 360 answer."""
        target_name = client_name_or_phone or query.strip()
        obsidian_content = await asyncio.to_thread(self._find_obsidian_card, target_name)

        profile_context = ""
        if obsidian_content:
            profile_context = f"OBSIDIAN MIJOZ KARTASI:\n{obsidian_content}"
        else:
            # Live collect across channels
            profile = await self.collector.collect_profile(target_name)
            from src.services.customer_360.obsidian_syncer import Customer360ObsidianSyncer
            syncer = Customer360ObsidianSyncer(self.vault_paths)
            profile_context = syncer.format_markdown(profile)
            # Save for future
            await syncer.sync_profile(profile)

        # Call Gemini to synthesize the answer
        return await self._generate_ai_answer(query, profile_context)

    async def _generate_ai_answer(self, query: str, context: str) -> str:
        prompt = f"Foydalanuvchi savoli: {query}\n\nMijozning 360-darajali to'liq konteksti:\n{context}"
        try:
            from src.agents.ai_router import route
            result = await route(
                prompt=prompt,
                system=SYSTEM_PROMPT_UZ,
                task_type="consultation",
            )
            if result.get("success") and result.get("text"):
                return result["text"]
        except Exception as ex:
            logger.warning(f"[C360] ai_router failed: {ex}")

        # Direct Google GenAI fallback if key is present
        if self.gemini_api_key:
            try:
                from google import genai
                client = genai.Client(api_key=self.gemini_api_key)
                response = await asyncio.to_thread(
                    client.models.generate_content,
                    model="gemini-2.5-flash",
                    contents=f"{SYSTEM_PROMPT_UZ}\n\n{prompt}",
                )
                if response and response.text:
                    return response.text
            except Exception as direct_ex:
                logger.debug(f"[C360] Direct Gemini call failed: {direct_ex}")

        # Fallback to structured presentation of the card
        return (
            f"📋 **Mijoz bo'yicha 360° Ma'lumot:**\n\n{context}\n\n"
            f"*(Izoh: Savolga barcha tizimlardagi mavjud ma'lumotlar asosida hisobot taqdim etildi)*"
        )

