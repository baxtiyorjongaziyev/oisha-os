"""
OishaMemory — ChatGPT/Claude kabi persistent xotira qatlami.

Har bir o'zaro aloqadan muhim faktlarni avtomatik ajratib saqlaydi va
keyingi AI javoblari uchun kontekst sifatida inject qiladi.

Xotira turlari:
  client   — mijoz: afzalliklari, byudjeti, loyihalari
  lead     — potentsial mijoz: manba, ehtiyoj, muloqot tarixi
  team     — jamoa a'zosi: samaradorligi, uslubi
  business — biznes bilim: narxlar, muvaffaqiyatli strategiyalar
  general  — umumiy kuzatuvlar
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Optional

from src.time_utils import get_local_now

if TYPE_CHECKING:
    from src.database import Database

logger = logging.getLogger(__name__)

_FACT_EXTRACT_PROMPT = """Quyidagi suhbatdan muhim, amaliy faktlarni chiqar.

SUHBAT:
{conversation}

KONTEKST:
- Suhbat turi: {entity_type}
- Shaxs/Kompaniya: {entity_name}

Har bir fakt uchun JSON obekt:
- "entity_type": "client"|"lead"|"team"|"business"|"general"
- "entity_id": shaxs/kompaniyaning identifikatori (username, ID, yoki nom)
- "entity_name": o'qilishi oson ism
- "fact_key": fakt kaliti (masalan: "prefers_whatsapp", "budget_5000", "works_evenings")
- "fact_value": faktning to'liq mazmuni (1-2 jumla)
- "confidence": 0.0—1.0 ishonch darajasi

Faqat aniq, tasdiqlangan faktlarni yazing. Taxminlarni qo'shmang.
JSON array qaytaring. Agar fakt yo'q bo'lsa: []"""


class OishaMemory:
    """Oisha'ning persistent xotirasi — har o'zaro aloqadan o'rganadi."""

    def __init__(self, db: "Database", gemini_api_key: str):
        self.db = db
        self._api_key = gemini_api_key
        self._client = None

    @property
    def _gemini(self):
        if self._client is None:
            from google import genai
            self._client = genai.Client(api_key=self._api_key)
        return self._client

    async def ensure_tables(self):
        async with await self.db.get_connection() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS oisha_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT,
                    entity_name TEXT,
                    fact_key TEXT NOT NULL,
                    fact_value TEXT NOT NULL,
                    confidence REAL DEFAULT 0.8,
                    source TEXT DEFAULT 'conversation',
                    times_confirmed INTEGER DEFAULT 1,
                    last_seen_at TEXT,
                    created_at TEXT
                )
            """)
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memory_entity ON oisha_memory(entity_id)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memory_type ON oisha_memory(entity_type)"
            )
            await conn.commit()

    async def learn_from_conversation(
        self,
        conversation: str,
        entity_type: str = "general",
        entity_name: str = "",
        source: str = "conversation",
    ) -> int:
        """Suhbatdan faktlarni ajratib, xotirada saqlaydi. Saqlangan faktlar sonini qaytaradi."""
        if not conversation or len(conversation) < 30:
            return 0

        try:
            from src.utils.ai_utils import safe_ai_call
            import os
            from src.settings import settings

            model = os.getenv("GEMINI_SELF_LEARNING_MODEL", settings.GEMINI_CALL_MODEL)
            prompt = _FACT_EXTRACT_PROMPT.format(
                conversation=conversation[:3000],
                entity_type=entity_type,
                entity_name=entity_name or "Noma'lum",
            )
            response = await safe_ai_call(
                client=self._gemini,
                prompt=[prompt],
                system_instruction="Faqat valid JSON array qaytaring.",
                model=model,
            )
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            facts = json.loads(text)
            if not isinstance(facts, list):
                return 0

            return await self._save_facts(facts, source)

        except Exception as exc:
            logger.debug("[MEMORY] Fakt ajratishda xato: %s", exc)
            return 0

    async def _save_facts(self, facts: list, source: str) -> int:
        now = get_local_now().isoformat()
        saved = 0
        async with await self.db.get_connection() as conn:
            for fact in facts:
                if not fact.get("fact_key") or not fact.get("fact_value"):
                    continue
                entity_id = str(fact.get("entity_id", "")) or None
                fact_key = str(fact.get("fact_key", ""))[:100]

                existing = await (await conn.execute(
                    "SELECT id, times_confirmed FROM oisha_memory WHERE entity_id=? AND fact_key=?",
                    (entity_id, fact_key),
                )).fetchone()

                if existing:
                    await conn.execute(
                        """UPDATE oisha_memory SET
                           fact_value=?, confidence=?, times_confirmed=times_confirmed+1,
                           last_seen_at=?
                           WHERE id=?""",
                        (
                            str(fact.get("fact_value", ""))[:500],
                            min(max(float(fact.get("confidence", 0.8)), 0.0), 1.0),
                            now,
                            existing[0],
                        ),
                    )
                else:
                    await conn.execute(
                        """INSERT INTO oisha_memory
                           (entity_type, entity_id, entity_name, fact_key, fact_value,
                            confidence, source, last_seen_at, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            str(fact.get("entity_type", "general"))[:50],
                            entity_id,
                            str(fact.get("entity_name", ""))[:100],
                            fact_key,
                            str(fact.get("fact_value", ""))[:500],
                            min(max(float(fact.get("confidence", 0.8)), 0.0), 1.0),
                            source,
                            now,
                            now,
                        ),
                    )
                saved += 1
            await conn.commit()

        if saved:
            logger.info("[MEMORY] %d fakt saqlandi (source=%s)", saved, source)
        return saved

    async def get_context_for_entity(self, entity_id: str, limit: int = 10) -> str:
        """Bitta shaxs/kompaniya haqidagi xotiralarni qaytaradi."""
        async with await self.db.get_connection() as conn:
            rows = await (await conn.execute(
                """SELECT fact_key, fact_value, times_confirmed FROM oisha_memory
                   WHERE entity_id=?
                   ORDER BY times_confirmed DESC, confidence DESC LIMIT ?""",
                (entity_id, limit),
            )).fetchall()

        if not rows:
            return ""

        lines = [f"• {r[0]}: {r[1]}" for r in rows]
        return "📋 Shaxs haqida:\n" + "\n".join(lines)

    async def get_global_context(
        self,
        entity_type: Optional[str] = None,
        limit: int = 15,
    ) -> str:
        """Umumiy biznes xotiralarni (strategiya, narxlar, muhim faktlar) qaytaradi."""
        async with await self.db.get_connection() as conn:
            if entity_type:
                rows = await (await conn.execute(
                    """SELECT entity_name, fact_key, fact_value, times_confirmed
                       FROM oisha_memory WHERE entity_type=? AND confidence >= 0.7
                       ORDER BY times_confirmed DESC, confidence DESC LIMIT ?""",
                    (entity_type, limit),
                )).fetchall()
            else:
                rows = await (await conn.execute(
                    """SELECT entity_name, fact_key, fact_value, times_confirmed
                       FROM oisha_memory WHERE confidence >= 0.7
                       ORDER BY times_confirmed DESC, confidence DESC LIMIT ?""",
                    (limit,),
                )).fetchall()

        if not rows:
            return ""

        lines = []
        for name, key, value, confirmed in rows:
            prefix = f"[{name}] " if name else ""
            stars = "⭐" * min(confirmed, 3)
            lines.append(f"• {prefix}{value} {stars}")

        return "🧠 Oisha xotirasi:\n" + "\n".join(lines)

    async def remember_crm_lead(self, lead: dict):
        """AmoCRM lead ma'lumotlarini xotirada saqlaydi."""
        name = lead.get("name", "")
        lead_id = str(lead.get("id", ""))
        if not name or not lead_id:
            return

        facts = []
        if lead.get("price"):
            facts.append({
                "entity_type": "lead",
                "entity_id": lead_id,
                "entity_name": name,
                "fact_key": "budget",
                "fact_value": f"Byudjeti: {lead['price']:,} so'm",
                "confidence": 0.9,
            })
        if lead.get("pipeline_name"):
            facts.append({
                "entity_type": "lead",
                "entity_id": lead_id,
                "entity_name": name,
                "fact_key": "pipeline_stage",
                "fact_value": f"Pipeline: {lead['pipeline_name']} → {lead.get('status_name', '?')}",
                "confidence": 1.0,
            })
        if lead.get("responsible_user_name"):
            facts.append({
                "entity_type": "lead",
                "entity_id": lead_id,
                "entity_name": name,
                "fact_key": "responsible_manager",
                "fact_value": f"Mas'ul menejer: {lead['responsible_user_name']}",
                "confidence": 1.0,
            })

        if facts:
            await self._save_facts(facts, source="crm")
