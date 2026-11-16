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
import os
from typing import Any, Dict, List, Optional

from google import genai

from src.database import Database
from src.settings import settings
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


def _row_val(row: Any, key: str, index: int) -> Any:
    if isinstance(row, dict) or hasattr(row, "keys"):
        try:
            return row[key]
        except (KeyError, IndexError, TypeError):
            pass
    return row[index]


def _extract_json_array(raw: str) -> List[Dict[str, Any]]:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, list) else []
    except ValueError:
        pass
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end <= start:
        return []
    try:
        parsed = json.loads(text[start : end + 1])
        return parsed if isinstance(parsed, list) else []
    except ValueError:
        return []


class SelfLearningEngine:
    """Conversation feedback → lesson extraction → prompt evolution."""

    def __init__(self, db: Database, gemini_api_key: str = "", router: Any = None):
        self.db = db
        self.client = genai.Client(api_key=gemini_api_key) if gemini_api_key else None
        self.model = os.getenv("GEMINI_SELF_LEARNING_MODEL", settings.GEMINI_CALL_MODEL)
        self._router = router

    async def _generate_json_array(
        self, prompt: str, *, system_instruction: str = "Faqat valid JSON array qaytaring."
    ) -> List[Dict[str, Any]]:
        raw_text = ""
        if self._router is None and self.client is not None:
            try:
                from src.utils.ai_utils import safe_ai_call

                response = await safe_ai_call(
                    client=self.client,
                    prompt=[prompt],
                    system_instruction=system_instruction,
                    model=self.model,
                )
                raw_text = getattr(response, "text", "") or ""
            except Exception as exc:
                logger.debug("[LEARN] safe_ai_call fallback to free router: %s", exc)
        if not raw_text.strip():
            from src.services.utils.free_ai_router import get_free_ai_router

            router = self._router or get_free_ai_router()
            res = await router.generate_text(
                prompt, system=system_instruction, max_tokens=900, temperature=0.2
            )
            raw_text = getattr(res, "text", "") or ""
        return _extract_json_array(raw_text)

    async def ensure_tables(self):
        ddl = (
            "CREATE TABLE IF NOT EXISTS learning_journal (id INTEGER PRIMARY KEY AUTOINCREMENT, pattern TEXT NOT NULL, lesson TEXT NOT NULL, strategy TEXT, confidence REAL DEFAULT 0.5, category TEXT DEFAULT 'general', times_applied INTEGER DEFAULT 0, times_successful INTEGER DEFAULT 0, source_chat_id INTEGER, source_user_id INTEGER, created_at TEXT, last_applied_at TEXT)",
            "CREATE TABLE IF NOT EXISTS strategy_rules (id INTEGER PRIMARY KEY AUTOINCREMENT, rule TEXT NOT NULL, trigger_condition TEXT, weight REAL DEFAULT 0.5, active BOOLEAN DEFAULT 1, applied_count INTEGER DEFAULT 0, success_count INTEGER DEFAULT 0, created_at TEXT, updated_at TEXT)",
            "CREATE TABLE IF NOT EXISTS learning_metrics (id INTEGER PRIMARY KEY AUTOINCREMENT, metric_type TEXT NOT NULL, metric_value REAL, context_json TEXT, recorded_at TEXT)",
            "CREATE INDEX IF NOT EXISTS idx_journal_category ON learning_journal(category)",
            "CREATE INDEX IF NOT EXISTS idx_journal_confidence ON learning_journal(confidence)",
        )
        async with await self.db.get_connection() as conn:
            for stmt in ddl:
                await conn.execute(stmt)
            await conn.commit()

    async def _upsert_lesson(
        self, conn: Any, lesson: Dict[str, Any], *, chat_id: Optional[int], user_id: Optional[int], now: str
    ) -> bool:
        lesson_text = str(lesson.get("lesson") or "").strip()
        if not lesson_text:
            return False
        pattern = str(lesson.get("pattern") or lesson_text[:80]).strip()
        category = str(lesson.get("category") or "general").strip() or "general"
        strategy = str(lesson.get("strategy") or "").strip()
        conf = min(max(float(lesson.get("confidence", 0.5)), 0.0), 1.0)
        cur = await conn.execute(
            "SELECT id, confidence FROM learning_journal WHERE pattern = ? AND category = ? LIMIT 1",
            (pattern, category),
        )
        existing = await cur.fetchone()
        if existing is not None:
            row_id = _row_val(existing, "id", 0)
            prev_conf = float(_row_val(existing, "confidence", 1) or 0.5)
            await conn.execute(
                "UPDATE learning_journal SET lesson = ?, strategy = ?, confidence = ? WHERE id = ?",
                (lesson_text, strategy, min(max(prev_conf, conf), 1.0), row_id),
            )
            return True
        await conn.execute(
            "INSERT INTO learning_journal (pattern, lesson, strategy, confidence, category, source_chat_id, source_user_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (pattern, lesson_text, strategy, conf, category, chat_id, user_id, now),
        )
        return True

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
            lessons = await self._generate_json_array(prompt)
            if not lessons:
                return []
            now = get_local_now().isoformat()
            saved = []
            async with await self.db.get_connection() as conn:
                for lesson in lessons:
                    if isinstance(lesson, dict) and await self._upsert_lesson(
                        conn, lesson, chat_id=chat_id, user_id=user_id, now=now
                    ):
                        saved.append(lesson)
                await conn.commit()
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
        async with await self.db.get_connection() as conn:
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
                    "pattern": _row_val(row, "pattern", 0),
                    "lesson": _row_val(row, "lesson", 1),
                    "strategy": _row_val(row, "strategy", 2),
                    "confidence": _row_val(row, "confidence", 3),
                    "applied": _row_val(row, "times_applied", 4),
                    "successful": _row_val(row, "times_successful", 5),
                })
            return results[:limit]

    async def get_active_strategies(self) -> List[Dict[str, Any]]:
        """Faol strategiyalarni olish (prompt'ga qo'shish uchun)."""
        async with await self.db.get_connection() as conn:
            rows = await conn.execute(
                """SELECT rule, trigger_condition, weight
                   FROM strategy_rules
                   WHERE active = 1
                   ORDER BY weight DESC
                   LIMIT 10"""
            )
            return [
                {
                    "rule": _row_val(r, "rule", 0),
                    "when": _row_val(r, "trigger_condition", 1),
                    "weight": _row_val(r, "weight", 2),
                }
                for r in await rows.fetchall()
            ]

    async def mark_lesson_applied(self, pattern: str, success: bool):
        """Dars ishlatilganini belgilash (feedback loop)."""
        async with await self.db.get_connection() as conn:
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
            await conn.commit()

    async def _save_synthesized_strategies(
        self, strategies: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        now = get_local_now().isoformat()
        saved = []
        async with await self.db.get_connection() as conn:
            for strat in strategies:
                if not isinstance(strat, dict) or not strat.get("rule"):
                    continue
                rule_text = str(strat["rule"]).strip()
                cur = await conn.execute(
                    "SELECT id FROM strategy_rules WHERE rule = ? AND active = 1 LIMIT 1",
                    (rule_text,),
                )
                if await cur.fetchone() is not None:
                    continue
                await conn.execute(
                    "INSERT INTO strategy_rules (rule, trigger_condition, weight, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (
                        rule_text,
                        str(strat.get("when", "") or "").strip(),
                        min(max(float(strat.get("weight", 0.5)), 0.0), 1.0),
                        now,
                        now,
                    ),
                )
                saved.append(strat)
            await conn.commit()
        return saved

    async def synthesize_strategies(self) -> List[Dict[str, Any]]:
        """Yigʻilgan darslardan umumiy strategiyalar chiqarish (haftalik)."""
        async with await self.db.get_connection() as conn:
            rows = await conn.execute(
                "SELECT pattern, lesson, strategy, confidence, category FROM learning_journal WHERE confidence > 0.5 ORDER BY confidence DESC LIMIT 30"
            )
            lessons = [
                {
                    "pattern": _row_val(r, "pattern", 0),
                    "lesson": _row_val(r, "lesson", 1),
                    "strategy": _row_val(r, "strategy", 2),
                    "confidence": _row_val(r, "confidence", 3),
                    "category": _row_val(r, "category", 4),
                }
                for r in await rows.fetchall()
            ]
        if len(lessons) < 5:
            return []
        prompt = STRATEGY_SYNTHESIS_PROMPT.format(lessons_json=json.dumps(lessons, ensure_ascii=False))
        try:
            strategies = await self._generate_json_array(prompt)
            if not strategies:
                return []
            saved = await self._save_synthesized_strategies(strategies)
            logger.info(f"[LEARN] Synthesized {len(saved)} new strategies")
            return saved
        except Exception as exc:
            logger.warning(f"[LEARN] Strategy synthesis failed: {exc}")
            return []

    async def record_metric(self, metric_type: str, value: float, context: Optional[Dict] = None):
        """O'lchov yozish (response_quality, lead_conversion, etc)."""
        async with await self.db.get_connection() as conn:
            await conn.execute(
                """INSERT INTO learning_metrics (metric_type, metric_value, context_json, recorded_at)
                   VALUES (?, ?, ?, ?)""",
                (metric_type, value, json.dumps(context or {}), get_local_now().isoformat()),
            )
            await conn.commit()

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
