"""
Self-Learning Engine — Oisha o'zini o'zi rivojlantirish moduli.

Har bir suhbat natijasidan lesson learned chiqarib, keyingi suhbatlarda
yaxshiroq ishlash uchun prompt/strategiyani auto-tune qiladi.

Loop:
  1. Conversation ends → extract_lessons()
  2. Lessons → DB (learning_journal)
  3. Before next response → get_relevant_lessons() → inject into prompt
  4. Periodically → synthesize_strategies() → evolve prompts
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from google import genai

from src.database import Database
from src.time_utils import get_local_now

logger = logging.getLogger(__name__)

LESSON_EXTRACTION_PROMPT = """Siz AI agentning o'z-o'zini o'rgatish moduli siz.

Quyidagi suhbat tarixini tahlil qiling va aniq DARS(lesson) chiqaring:

SUHBAT:
{conversation}

KONTEKST:
- Mijoz turi: {client_type}
- Natija: {outcome}
- Menejer nomi: {manager_name}

Har bir dars uchun:
1. **pattern** — qanday vaziyatda bu dars kerak (2-3 so'z)
2. **lesson** — nima o'rgandik (1 jumla)
3. **strategy** — keyingi safar nima qilish kerak (1 jumla)
4. **confidence** — ishonch darajasi (0.0—1.0)
5. **category** — kategoriya: sales|objection|timing|tone|followup|pricing

JSON array qaytaring. Faqat JSON, boshqa narsa yo'q.
Agar hech narsa o'rganilmagan bo'lsa, bo'sh array qaytaring: []
"""

STRATEGY_SYNTHESIS_PROMPT = """Siz strategik AI. Quyidagi individual darslardan UMUMIY strategiya chiqaring.

DARSLAR:
{lessons_json}

Vazifa: Shu darslarni umumlashtiring va 3-5 ta strategik qoida yozing.
Har bir qoida:
1. **rule** — qoida (1 jumla)
2. **when** — qachon ishlatish (trigger condition)
3. **weight** — muhimligi (0.0—1.0)

JSON array qaytaring. Faqat JSON."""


class SelfLearningEngine:
    """Conversation feedback → lesson extraction → prompt evolution."""

    def __init__(self, db: Database, gemini_api_key: str):
        self.db = db
        self.client = genai.Client(api_key=gemini_api_key)
        self.model = "gemini-2.0-flash"

    async def ensure_tables(self):
        async with self.db.get_connection() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS learning_journal (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern TEXT NOT NULL,
                    lesson TEXT NOT NULL,
                    strategy TEXT,
                    confidence REAL DEFAULT 0.5,
                    category TEXT DEFAULT 'general',
                    times_applied INTEGER DEFAULT 0,
                    times_successful INTEGER DEFAULT 0,
                    source_chat_id INTEGER,
                    source_user_id INTEGER,
                    created_at TEXT,
                    last_applied_at TEXT
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS strategy_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rule TEXT NOT NULL,
                    trigger_condition TEXT,
                    weight REAL DEFAULT 0.5,
                    active BOOLEAN DEFAULT 1,
                    applied_count INTEGER DEFAULT 0,
                    success_count INTEGER DEFAULT 0,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS learning_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_type TEXT NOT NULL,
                    metric_value REAL,
                    context_json TEXT,
                    recorded_at TEXT
                )
            """)
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_journal_category ON learning_journal(category)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_journal_confidence ON learning_journal(confidence)"
            )

    async def extract_lessons(
        self,
        conversation: str,
        client_type: str = "unknown",
        outcome: str = "unknown",
        manager_name: str = "",
        chat_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Suhbatdan darslar chiqarish."""
        if not conversation or len(conversation) < 50:
            return []

        prompt = LESSON_EXTRACTION_PROMPT.format(
            conversation=conversation[:3000],
            client_type=client_type,
            outcome=outcome,
            manager_name=manager_name,
        )

        try:
            from src.utils.ai_utils import safe_ai_call
            response = await safe_ai_call(
                client=self.client,
                prompt=[prompt],
                system_instruction="Faqat valid JSON array qaytaring.",
                model=self.model,
            )
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            lessons = json.loads(text)
            if not isinstance(lessons, list):
                return []

            now = get_local_now().isoformat()
            saved = []
            async with self.db.get_connection() as conn:
                for lesson in lessons:
                    if not lesson.get("lesson"):
                        continue
                    await conn.execute(
                        """INSERT INTO learning_journal
                           (pattern, lesson, strategy, confidence, category,
                            source_chat_id, source_user_id, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            lesson.get("pattern", ""),
                            lesson["lesson"],
                            lesson.get("strategy", ""),
                            min(max(float(lesson.get("confidence", 0.5)), 0.0), 1.0),
                            lesson.get("category", "general"),
                            chat_id,
                            user_id,
                            now,
                        ),
                    )
                    saved.append(lesson)

            logger.info(f"[LEARN] Extracted {len(saved)} lessons from conversation")
            return saved

        except Exception as exc:
            logger.warning(f"[LEARN] Lesson extraction failed: {exc}")
            return []

    async def get_relevant_lessons(
        self,
        context: str,
        category: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Kontekstga mos darslarni olish (keyingi prompt'ga inject qilish uchun)."""
        async with self.db.get_connection() as conn:
            if category:
                rows = await conn.execute(
                    """SELECT pattern, lesson, strategy, confidence, times_applied, times_successful
                       FROM learning_journal
                       WHERE category = ? AND confidence > 0.3
                       ORDER BY confidence DESC, times_successful DESC
                       LIMIT ?""",
                    (category, limit),
                )
            else:
                rows = await conn.execute(
                    """SELECT pattern, lesson, strategy, confidence, times_applied, times_successful
                       FROM learning_journal
                       WHERE confidence > 0.3
                       ORDER BY confidence DESC, times_successful DESC
                       LIMIT ?""",
                    (limit * 2,),
                )

            results = []
            for row in await rows.fetchall():
                results.append({
                    "pattern": row[0],
                    "lesson": row[1],
                    "strategy": row[2],
                    "confidence": row[3],
                    "applied": row[4],
                    "successful": row[5],
                })
            return results[:limit]

    async def get_active_strategies(self) -> List[Dict[str, Any]]:
        """Faol strategiyalarni olish (prompt'ga qo'shish uchun)."""
        async with self.db.get_connection() as conn:
            rows = await conn.execute(
                """SELECT rule, trigger_condition, weight
                   FROM strategy_rules
                   WHERE active = 1
                   ORDER BY weight DESC
                   LIMIT 10"""
            )
            return [
                {"rule": r[0], "when": r[1], "weight": r[2]}
                for r in await rows.fetchall()
            ]

    async def mark_lesson_applied(self, pattern: str, success: bool):
        """Dars ishlatilganini belgilash (feedback loop)."""
        async with self.db.get_connection() as conn:
            now = get_local_now().isoformat()
            if success:
                await conn.execute(
                    """UPDATE learning_journal
                       SET times_applied = times_applied + 1,
                           times_successful = times_successful + 1,
                           confidence = MIN(confidence + 0.05, 1.0),
                           last_applied_at = ?
                       WHERE pattern = ?""",
                    (now, pattern),
                )
            else:
                await conn.execute(
                    """UPDATE learning_journal
                       SET times_applied = times_applied + 1,
                           confidence = MAX(confidence - 0.1, 0.0),
                           last_applied_at = ?
                       WHERE pattern = ?""",
                    (now, pattern),
                )

    async def synthesize_strategies(self) -> List[Dict[str, Any]]:
        """Yig'ilgan darslardan umumiy strategiyalar chiqarish (haftalik)."""
        async with self.db.get_connection() as conn:
            rows = await conn.execute(
                """SELECT pattern, lesson, strategy, confidence, category
                   FROM learning_journal
                   WHERE confidence > 0.5
                   ORDER BY confidence DESC
                   LIMIT 30"""
            )
            lessons = [
                {
                    "pattern": r[0],
                    "lesson": r[1],
                    "strategy": r[2],
                    "confidence": r[3],
                    "category": r[4],
                }
                for r in await rows.fetchall()
            ]

        if len(lessons) < 5:
            return []

        prompt = STRATEGY_SYNTHESIS_PROMPT.format(lessons_json=json.dumps(lessons, ensure_ascii=False))

        try:
            from src.utils.ai_utils import safe_ai_call
            response = await safe_ai_call(
                client=self.client,
                prompt=[prompt],
                system_instruction="Faqat valid JSON array qaytaring.",
                model=self.model,
            )
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            strategies = json.loads(text)
            if not isinstance(strategies, list):
                return []

            now = get_local_now().isoformat()
            saved = []
            async with self.db.get_connection() as conn:
                for strat in strategies:
                    if not strat.get("rule"):
                        continue
                    await conn.execute(
                        """INSERT INTO strategy_rules (rule, trigger_condition, weight, created_at, updated_at)
                           VALUES (?, ?, ?, ?, ?)""",
                        (
                            strat["rule"],
                            strat.get("when", ""),
                            min(max(float(strat.get("weight", 0.5)), 0.0), 1.0),
                            now,
                            now,
                        ),
                    )
                    saved.append(strat)

            logger.info(f"[LEARN] Synthesized {len(saved)} new strategies")
            return saved

        except Exception as exc:
            logger.warning(f"[LEARN] Strategy synthesis failed: {exc}")
            return []

    async def record_metric(self, metric_type: str, value: float, context: Optional[Dict] = None):
        """O'lchov yozish (response_quality, lead_conversion, etc)."""
        async with self.db.get_connection() as conn:
            await conn.execute(
                """INSERT INTO learning_metrics (metric_type, metric_value, context_json, recorded_at)
                   VALUES (?, ?, ?, ?)""",
                (metric_type, value, json.dumps(context or {}), get_local_now().isoformat()),
            )

    def build_learning_context(self, lessons: List[Dict], strategies: List[Dict]) -> str:
        """Prompt'ga inject qilinadigan learning context string."""
        if not lessons and not strategies:
            return ""

        parts = []
        if strategies:
            parts.append("📋 STRATEGIK QOIDALAR:")
            for s in strategies[:5]:
                parts.append(f"  • {s['rule']} (qachon: {s.get('when', 'doim')})")

        if lessons:
            parts.append("\n💡 O'RGANILGAN DARSLAR:")
            for l in lessons[:5]:
                success_rate = ""
                if l.get("applied", 0) > 0:
                    rate = l.get("successful", 0) / l["applied"] * 100
                    success_rate = f" [{rate:.0f}% samarali]"
                parts.append(f"  • {l['lesson']}{success_rate}")
                if l.get("strategy"):
                    parts.append(f"    → {l['strategy']}")

        return "\n".join(parts)
