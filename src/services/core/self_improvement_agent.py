"""
Self-Improvement Agent — Oisha o'zini o'zi tahlil qilib, rivojlanish takliflari bilan chiqadi.

Farqi self_evolution'dan:
  - self_evolution: mavjud promptlarni yaxshilaydi (kod ichida)
  - self_improvement: TIZIMGA nima YETISHMAYOTGANINI aniqlaydi va
    "menga shu qobiliyat kerak, shu AI agent bilan yordam beringlar"
    degan taklif bilan owner'ga chiqadi.

Loop:
  1. collect_signals() — DB'dan operatsion signallarni yig'adi:
     muvaffaqiyatsiz harakatlar, retry navbati, past sifat metrikalari,
     o'rganish jurnalidagi bo'shliqlar
  2. analyze_gaps() — Gemini orqali kamchiliklarni tahlil qiladi
  3. save_proposals() — takliflarni agent_improvement_proposals jadvaliga yozadi
  4. Owner'ga Telegram orqali hisobot yuboriladi (EvolutionScheduler orqali)

Xavfsizlik:
  - Faqat o'qiydi va taklif yozadi — hech qanday avtomatik harakat qilmaydi
  - Barcha takliflar owner approve qilmaguncha "proposed" statusida qoladi
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

import structlog
from google import genai

from src.database import Database
from src.settings import settings
from src.time_utils import get_local_now

logger = structlog.get_logger()

VALID_PRIORITIES = {"high", "medium", "low"}

GAP_ANALYSIS_PROMPT = """Siz Oisha-OS (Jon Branding agentligining avtonom COO tizimi) ning
o'z-o'zini rivojlantirish modulisiz. Vazifangiz — tizimning operatsion signallarini
tahlil qilib, unga NIMA YETISHMAYOTGANINI aniqlash va aniq takliflar berish.

OPERATSION SIGNALLAR (oxirgi 7 kun):
{signals}

MAVJUD QOBILIYATLAR:
- Telegram xabarlarini boshqarish (userbot + admin bot)
- AmoCRM lead sync va pipeline audit
- Sales coaching (AdvisorAgent), avtonom lead ishlovi (AutoLeadAgent)
- Kunlik hisobotlar (EnterpriseReporter), jamoa auditi (AuditAgent)
- Prompt self-evolution (haftalik PR)

VAZIFA:
Signallar asosida 1-5 ta rivojlanish taklifini chiqaring. Har bir taklif uchun:
1. "area" — qaysi soha (masalan: "lead followup", "error handling", "reporting")
2. "gap" — aniq nima yetishmayapti (1-2 jumla, signallarga tayangan holda)
3. "proposal" — nima qilish kerak (1-2 jumla, amaliy)
4. "ai_agent_help" — qanday AI agent yoki avtomatlashtirish yordam beradi
   (masalan: "yangi FollowupAgent: 48 soat javobsiz leadlarga eslatma yuboradi")
5. "priority" — high | medium | low
6. "impact" — kutilayotgan natija (1 jumla)

QOIDALAR:
- Faqat signallarda ASOSI bor takliflar bering. Taxmin qilmang.
- Agar signallar yetarli bo'lmasa yoki muammo ko'rinmasa, bo'sh array qaytaring: []
- Faqat valid JSON array qaytaring, boshqa hech narsa yo'q.
"""


class SelfImprovementAgent:
    """Operatsion signallar asosida rivojlanish takliflarini generatsiya qiladi."""

    def __init__(self, db: Database, gemini_api_key: str):
        self.db = db
        self.client = genai.Client(api_key=gemini_api_key)
        self.model = os.getenv(
            "GEMINI_SELF_IMPROVEMENT_MODEL", settings.GEMINI_CALL_MODEL
        )

    async def ensure_tables(self):
        async with await self.db.get_connection() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_improvement_proposals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    area TEXT NOT NULL,
                    gap TEXT NOT NULL,
                    proposal TEXT NOT NULL,
                    ai_agent_help TEXT,
                    priority TEXT DEFAULT 'medium',
                    impact TEXT,
                    status TEXT DEFAULT 'proposed',
                    signals_json TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_agent_proposals_status "
                "ON agent_improvement_proposals(status)"
            )
            await conn.commit()

    # ------------------------------------------------------------------
    # 1. Signal yig'ish
    # ------------------------------------------------------------------

    async def collect_signals(self) -> Dict[str, Any]:
        """Operatsion signallarni DB'dan yig'ish. Har bir manba mustaqil —
        bittasi ishlamasa qolganlari baribir yig'iladi."""
        signals: Dict[str, Any] = {"collected_at": get_local_now().isoformat()}

        signals["failed_actions"] = await self._safe_query(
            """SELECT action_type, COUNT(*) FROM agent_actions
               WHERE success = 0 AND created_at > datetime('now', '-7 days')
               GROUP BY action_type ORDER BY COUNT(*) DESC LIMIT 10""",
            lambda rows: [{"action": r[0], "failures": r[1]} for r in rows],
        )

        signals["retry_queue_depth"] = await self._safe_query(
            "SELECT COUNT(*) FROM retry_queue",
            lambda rows: rows[0][0] if rows else 0,
        )

        signals["avg_response_quality"] = await self._safe_query(
            """SELECT AVG(metric_value) FROM learning_metrics
               WHERE metric_type = 'response_quality'
               AND recorded_at > datetime('now', '-7 days')""",
            lambda rows: round(rows[0][0], 2) if rows and rows[0][0] else None,
        )

        signals["low_confidence_categories"] = await self._safe_query(
            """SELECT category, COUNT(*), AVG(confidence) FROM learning_journal
               WHERE confidence < 0.5
               AND created_at > datetime('now', '-7 days')
               GROUP BY category ORDER BY COUNT(*) DESC LIMIT 5""",
            lambda rows: [
                {"category": r[0], "count": r[1], "avg_confidence": round(r[2] or 0, 2)}
                for r in rows
            ],
        )

        signals["unanswered_leads"] = await self._safe_query(
            """SELECT COUNT(*) FROM leads
               WHERE status NOT IN ('won', 'lost', 'closed')
               AND updated_at < datetime('now', '-2 days')""",
            lambda rows: rows[0][0] if rows else 0,
        )

        signals["stale_tasks"] = await self._safe_query(
            """SELECT COUNT(*) FROM tasks
               WHERE status = 'pending'
               AND created_at < datetime('now', '-3 days')""",
            lambda rows: rows[0][0] if rows else 0,
        )

        return signals

    async def _safe_query(self, sql: str, mapper) -> Any:
        try:
            async with await self.db.get_connection() as conn:
                cursor = await conn.execute(sql)
                rows = await cursor.fetchall()
                return mapper(rows)
        except Exception as exc:
            logger.debug(f"[IMPROVE] Signal query skipped: {exc}")
            return None

    # ------------------------------------------------------------------
    # 2. Gap tahlili
    # ------------------------------------------------------------------

    async def analyze_gaps(self, signals: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Signallar asosida LLM orqali rivojlanish takliflarini chiqarish."""
        if not self._has_meaningful_signals(signals):
            logger.info("[IMPROVE] Not enough signals for gap analysis")
            return []

        prompt = GAP_ANALYSIS_PROMPT.format(
            signals=json.dumps(signals, ensure_ascii=False, indent=2, default=str)
        )

        try:
            from src.utils.ai_utils import safe_ai_call

            response = await safe_ai_call(
                client=self.client,
                prompt=[prompt],
                system_instruction="Faqat valid JSON array qaytaring.",
                model=self.model,
            )
            proposals = self._parse_proposals(response.text)
            logger.info(f"[IMPROVE] {len(proposals)} proposals generated")
            return proposals
        except Exception as exc:
            logger.warning(f"[IMPROVE] Gap analysis failed: {exc}")
            return []

    @staticmethod
    def _has_meaningful_signals(signals: Dict[str, Any]) -> bool:
        """Kamida bitta manba real ma'lumot berganligini tekshirish."""
        for key, value in signals.items():
            if key == "collected_at":
                continue
            if isinstance(value, list) and value:
                return True
            if isinstance(value, (int, float)) and value:
                return True
        return False

    @staticmethod
    def _parse_proposals(text: str) -> List[Dict[str, Any]]:
        """LLM javobidan takliflar ro'yxatini xavfsiz ajratib olish."""
        if not text:
            return []
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("[IMPROVE] LLM returned invalid JSON")
            return []

        if not isinstance(data, list):
            return []

        proposals = []
        for item in data:
            if not isinstance(item, dict):
                continue
            if not item.get("area") or not item.get("gap") or not item.get("proposal"):
                continue
            priority = str(item.get("priority", "medium")).lower()
            if priority not in VALID_PRIORITIES:
                priority = "medium"
            proposals.append({
                "area": str(item["area"])[:100],
                "gap": str(item["gap"])[:500],
                "proposal": str(item["proposal"])[:500],
                "ai_agent_help": str(item.get("ai_agent_help", ""))[:500],
                "priority": priority,
                "impact": str(item.get("impact", ""))[:300],
            })
        return proposals[:5]

    # ------------------------------------------------------------------
    # 3. Saqlash va hisobot
    # ------------------------------------------------------------------

    async def save_proposals(
        self, proposals: List[Dict[str, Any]], signals: Dict[str, Any]
    ) -> int:
        """Yangi takliflarni saqlash. Ochiq (proposed) dublikatlar o'tkazib yuboriladi."""
        if not proposals:
            return 0

        saved = 0
        now = get_local_now().isoformat()
        signals_json = json.dumps(signals, ensure_ascii=False, default=str)

        async with await self.db.get_connection() as conn:
            for p in proposals:
                cursor = await conn.execute(
                    """SELECT COUNT(*) FROM agent_improvement_proposals
                       WHERE area = ? AND status = 'proposed'""",
                    (p["area"],),
                )
                row = await cursor.fetchone()
                if row and row[0] > 0:
                    continue

                await conn.execute(
                    """INSERT INTO agent_improvement_proposals
                       (area, gap, proposal, ai_agent_help, priority, impact,
                        status, signals_json, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, 'proposed', ?, ?, ?)""",
                    (
                        p["area"], p["gap"], p["proposal"], p["ai_agent_help"],
                        p["priority"], p["impact"], signals_json, now, now,
                    ),
                )
                saved += 1
            await conn.commit()

        logger.info(f"[IMPROVE] Saved {saved} new proposals")
        return saved

    async def get_open_proposals(self, limit: int = 10) -> List[Dict[str, Any]]:
        async with await self.db.get_connection() as conn:
            cursor = await conn.execute(
                """SELECT id, area, gap, proposal, ai_agent_help, priority, impact, created_at
                   FROM agent_improvement_proposals WHERE status = 'proposed'
                   ORDER BY CASE priority
                       WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
                       created_at DESC
                   LIMIT ?""",
                (limit,),
            )
            rows = await cursor.fetchall()
            return [
                {
                    "id": r[0], "area": r[1], "gap": r[2], "proposal": r[3],
                    "ai_agent_help": r[4], "priority": r[5], "impact": r[6],
                    "created_at": r[7],
                }
                for r in rows
            ]

    async def update_proposal_status(self, proposal_id: int, status: str) -> bool:
        """Owner qarori: approved | rejected | done."""
        if status not in {"approved", "rejected", "done", "proposed"}:
            return False
        async with await self.db.get_connection() as conn:
            await conn.execute(
                """UPDATE agent_improvement_proposals
                   SET status = ?, updated_at = ? WHERE id = ?""",
                (status, get_local_now().isoformat(), proposal_id),
            )
            await conn.commit()
        return True

    @staticmethod
    def format_report(proposals: List[Dict[str, Any]]) -> str:
        """Owner uchun Telegram hisoboti."""
        if not proposals:
            return ""

        priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}
        lines = [
            "🧠 Oisha Self-Improvement hisoboti",
            "",
            "Men o'z ishimni tahlil qildim. Quyidagilar menga yetishmayapti:",
            "",
        ]
        for i, p in enumerate(proposals, 1):
            emoji = priority_emoji.get(p.get("priority", "medium"), "🟡")
            lines.append(f"{emoji} {i}. {p['area'].upper()}")
            lines.append(f"   Muammo: {p['gap']}")
            lines.append(f"   Taklif: {p['proposal']}")
            if p.get("ai_agent_help"):
                lines.append(f"   AI yordam: {p['ai_agent_help']}")
            if p.get("impact"):
                lines.append(f"   Natija: {p['impact']}")
            lines.append("")

        lines.append(
            "Tasdiqlash uchun: /improve_approve <id> | Rad etish: /improve_reject <id>"
        )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 4. To'liq tsikl
    # ------------------------------------------------------------------

    async def run_cycle(self) -> Optional[str]:
        """To'liq tsikl: signal → tahlil → saqlash → hisobot matni.

        Yangi taklif bo'lmasa None qaytaradi (owner bezovta qilinmaydi).
        """
        await self.ensure_tables()
        signals = await self.collect_signals()
        proposals = await self.analyze_gaps(signals)
        saved = await self.save_proposals(proposals, signals)
        if saved == 0:
            return None
        open_proposals = await self.get_open_proposals()
        return self.format_report(open_proposals)
