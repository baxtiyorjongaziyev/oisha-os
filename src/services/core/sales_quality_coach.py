"""Sales Quality Coach — kunlik sifat hisoboti, ideal skript, playbook takliflari.

Rahbariyat talabi (2026-07-21):
  1. Har bir qo'ng'iroq baholansin (buni `call_analyzer`/`quality_analyzer`
     qiladi, natijalar `call_analyses` jadvaliga tushadi).
  2. Kun yakunida: eng yaxshi sotuvchi + eng yomon sotuvchiga nimani
     yaxshilash kerakligi.
  3. AI tarixdan ideal skript shakllantirsin va yangilab borsin.
  4. AI playbook'ni rivojlantirish bo'yicha taklif bersin.

Guardrail: AI playbook'ni O'ZGARTIRMAYDI — faqat taklif beradi. Rasmiy
mezon (`sales_playbook.py`) faqat odam qo'li bilan o'zgaradi.

Eslatma: `sales_coach.py` (SalesCoach) — boshqa, eskiroq modul; u bilan
adashtirmang.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional

from src.services.utils.db_rows import fetch_rows
from src.services.core.sales_playbook import SCORE_RED, rubric_prompt_uz

logger = logging.getLogger(__name__)

# Kunlik reyting adolatli bo'lishi uchun menejerda kamida shuncha
# baholangan qo'ng'iroq bo'lishi kerak.
MIN_CALLS_FOR_RANKING = 2


def _json_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(v) for v in parsed]
        except (json.JSONDecodeError, TypeError):
            pass
    return []


def _row_get(row: Any, key: str, default: Any = None) -> Any:
    """Row dict ham, SmartRow ham bo'lishi mumkin — ikkalasini ham o'qiymiz."""
    if isinstance(row, dict):
        return row.get(key, default)
    getter = getattr(row, "get", None)
    if callable(getter):
        try:
            value = getter(key, default)
            return default if value is None else value
        except Exception:
            return default
    return getattr(row, key, default)


class SalesQualityCoach:
    """`call_analyses` jadvalidagi baholar ustidan murabbiylik qatlami."""

    def __init__(self, db: Any, gemini_client: Any = None):
        self.db = db
        self._gemini_client = gemini_client

    # ------------------------------------------------------------------
    # Ma'lumot o'qish
    # ------------------------------------------------------------------

    async def _fetch_rows(self, sql: str, params: List[Any]) -> List[Any]:
        if self.db is None:
            return []
        try:
            # `Database` fasadida `execute()` yo'q, `DatabasePool` da bor —
            # ikkalasini ham qo'llab-quvvatlaydigan yordamchi orqali o'qiymiz.
            return await fetch_rows(self.db, sql, params)
        except Exception as exc:
            logger.error("[COACH] DB read failed: %s", exc)
            return []

    async def fetch_day_analyses(self, day_iso: str) -> List[Any]:
        """`day_iso` (YYYY-MM-DD) kunidagi barcha baholangan qo'ng'iroqlar."""
        return await self._fetch_rows(
            "SELECT manager_name, overall_score, category, weaknesses, "
            "strengths, outcome, call_id, duration_seconds "
            "FROM call_analyses WHERE created_at LIKE ? ORDER BY overall_score DESC",
            [f"{day_iso}%"],
        )

    async def fetch_top_transcripts(self, limit: int = 10, min_score: int = 75) -> List[Any]:
        """Ideal skript uchun eng yuqori baholi, transkripsiyali qo'ng'iroqlar."""
        return await self._fetch_rows(
            "SELECT transcript, overall_score, outcome FROM call_analyses "
            "WHERE overall_score >= ? AND transcript IS NOT NULL "
            "AND LENGTH(transcript) > 200 "
            "ORDER BY overall_score DESC LIMIT ?",
            [min_score, limit],
        )

    async def fetch_recent_weaknesses(self, days: int = 7, limit: int = 200) -> List[str]:
        rows = await self._fetch_rows(
            "SELECT weaknesses FROM call_analyses "
            "WHERE created_at >= datetime('now', ?) "
            "ORDER BY created_at DESC LIMIT ?",
            [f"-{int(days)} days", limit],
        )
        weaknesses: List[str] = []
        for row in rows:
            weaknesses.extend(_json_list(_row_get(row, "weaknesses")))
        return weaknesses

    # ------------------------------------------------------------------
    # 1) Kunlik hisobot — deterministik, LLM'siz (har doim ishlaydi)
    # ------------------------------------------------------------------

    def build_daily_report(self, rows: List[Any], day_iso: str) -> Optional[str]:
        """Kunlik sifat hisoboti matni. Ma'lumot bo'lmasa None."""
        if not rows:
            return None

        by_manager: Dict[str, List[Any]] = defaultdict(list)
        for row in rows:
            name = str(_row_get(row, "manager_name") or "Noma'lum").strip() or "Noma'lum"
            by_manager[name].append(row)

        def avg_score(items: List[Any]) -> float:
            scores = [int(_row_get(r, "overall_score") or 0) for r in items]
            return sum(scores) / max(len(scores), 1)

        ranked = sorted(
            (
                (name, avg_score(items), len(items))
                for name, items in by_manager.items()
                if len(items) >= MIN_CALLS_FOR_RANKING
            ),
            key=lambda item: item[1],
            reverse=True,
        )

        total = len(rows)
        overall_avg = avg_score(rows)
        red_calls = [r for r in rows if int(_row_get(r, "overall_score") or 0) < SCORE_RED]

        lines = [
            f"📞 KUNLIK SAVDO SIFATI — {day_iso}",
            "",
            f"Baholangan qo'ng'iroqlar: {total}",
            f"O'rtacha ball: {overall_avg:.0f}/100",
            f"Qizil qo'ng'iroqlar (<{SCORE_RED}): {len(red_calls)}",
        ]

        if ranked:
            best_name, best_avg, best_count = ranked[0]
            lines += [
                "",
                f"🏆 Kunning eng yaxshi sotuvchisi: {best_name} "
                f"({best_avg:.0f}/100, {best_count} ta qo'ng'iroq)",
            ]
            best_strengths = self._top_items(by_manager[best_name], "strengths")
            if best_strengths:
                lines.append("   Nimasi kuchli: " + "; ".join(best_strengths[:3]))

            if len(ranked) > 1:
                worst_name, worst_avg, worst_count = ranked[-1]
                lines += [
                    "",
                    f"📉 Eng past natija: {worst_name} "
                    f"({worst_avg:.0f}/100, {worst_count} ta qo'ng'iroq)",
                ]
                worst_weak = self._top_items(by_manager[worst_name], "weaknesses")
                if worst_weak:
                    lines.append("   Nimani yaxshilash kerak:")
                    lines += [f"   • {item}" for item in worst_weak[:3]]
        else:
            lines += [
                "",
                f"ℹ️ Reyting uchun har bir menejerda kamida "
                f"{MIN_CALLS_FOR_RANKING} ta baholangan qo'ng'iroq kerak.",
            ]

        return "\n".join(lines)

    @staticmethod
    def _top_items(rows: List[Any], column: str, top: int = 5) -> List[str]:
        """Eng ko'p takrorlangan strengths/weaknesses."""
        counts: Dict[str, int] = defaultdict(int)
        for row in rows:
            for item in _json_list(_row_get(row, column)):
                cleaned = item.strip()
                if cleaned:
                    counts[cleaned] += 1
        return [item for item, _ in sorted(counts.items(), key=lambda kv: -kv[1])[:top]]

    async def generate_daily_report(self, day_iso: str) -> Optional[str]:
        rows = await self.fetch_day_analyses(day_iso)
        return self.build_daily_report(rows, day_iso)

    # ------------------------------------------------------------------
    # 2) Ideal skript — eng yaxshi qo'ng'iroqlardan
    # ------------------------------------------------------------------

    async def generate_ideal_script(self) -> Optional[str]:
        """Yuqori baholi qo'ng'iroqlar tarixidan yozma ideal skript tuzadi.

        Yozma skript yo'q — shuning uchun uni eng zo'r haqiqiy suhbatlardan
        sintez qilamiz. Natija — TAKLIF, rahbariyat tasdiqlashi kerak.
        """
        rows = await self.fetch_top_transcripts()
        if len(rows) < 3:
            logger.info(
                "[COACH] Ideal skript uchun namuna yetarli emas (%d ta, kerak: 3+)",
                len(rows),
            )
            return None

        samples = "\n\n---\n\n".join(
            f"[Ball: {_row_get(r, 'overall_score')}, natija: {_row_get(r, 'outcome')}]\n"
            + str(_row_get(r, "transcript") or "")[:3000]
            for r in rows
        )
        prompt = (
            "Sen Jon Branding savdo murabbiyisan. Quyida kompaniyaning ENG YUQORI "
            "baholangan haqiqiy qo'ng'iroq transkripsiyalari berilgan.\n\n"
            f"{rubric_prompt_uz()}\n"
            "VAZIFA: shu namunalar va playbook asosida YOZMA IDEAL SKRIPT tuz:\n"
            "1. Har bosqich uchun 2-3 ta tayyor ibora (o'zbekcha, tabiiy)\n"
            "2. 'Qimmat' va 'o'ylab ko'raman' e'tirozlariga tayyor javoblar\n"
            "3. Yakunlash uchun uchrashuv taklif qilish iboralari\n"
            "Faqat namunalarda ISHLAGAN yondashuvlarni ol. To'qima.\n"
            "Format: oddiy matn, Telegram uchun qisqa va aniq.\n\n"
            f"NAMUNALAR:\n{samples}"
        )
        return await self._llm_text(prompt, "ideal_script")

    # ------------------------------------------------------------------
    # 3) Playbook takliflari — haftalik, faqat taklif
    # ------------------------------------------------------------------

    async def suggest_playbook_improvements(self) -> Optional[str]:
        """Oxirgi hafta zaifliklari asosida playbook'ga tuzatish TAKLIF qiladi.

        Hech narsani avtomatik o'zgartirmaydi — matn rahbariyatga yuboriladi.
        """
        weaknesses = await self.fetch_recent_weaknesses()
        if len(weaknesses) < 5:
            return None

        counts: Dict[str, int] = defaultdict(int)
        for item in weaknesses:
            counts[item.strip()] += 1
        top = sorted(counts.items(), key=lambda kv: -kv[1])[:15]
        summary = "\n".join(f"- {item} ({n} marta)" for item, n in top)

        prompt = (
            "Sen Jon Branding savdo bo'limi maslahatchisisan.\n\n"
            "JORIY PLAYBOOK:\n"
            f"{rubric_prompt_uz()}\n"
            "OXIRGI HAFTADA ENG KO'P TAKRORLANGAN ZAIFLIKLAR:\n"
            f"{summary}\n\n"
            "VAZIFA: 3-5 ta aniq taklif ber:\n"
            "- qaysi playbook bandini kuchaytirish yoki qo'shish kerak\n"
            "- menejerlar uchun qaysi trening mavzusi eng zarur\n"
            "Har taklif 1-2 gap. Umumiy gap yozma, faqat ma'lumotga tayanib.\n"
            "Oxirida eslat: bu TAKLIF, playbook faqat rahbariyat qarori bilan o'zgaradi."
        )
        return await self._llm_text(prompt, "playbook_suggestions")

    # ------------------------------------------------------------------
    # LLM helper
    # ------------------------------------------------------------------

    def _get_gemini_client(self) -> Optional[Any]:
        if self._gemini_client is not None:
            return self._gemini_client
        try:
            from src.settings import settings

            key = settings.GEMINI_API_KEY
            api_key = key.get_secret_value() if hasattr(key, "get_secret_value") else str(key or "")
            if not api_key:
                return None

            from google import genai

            self._gemini_client = genai.Client(api_key=api_key)
        except Exception as exc:
            logger.warning("[COACH] Gemini klient yaratilmadi: %s", exc)
            return None
        return self._gemini_client

    async def _llm_text(self, prompt: str, tag: str) -> Optional[str]:
        client = self._get_gemini_client()
        if client is None:
            logger.info("[COACH] Gemini yo'q — %s o'tkazib yuborildi", tag)
            return None
        try:
            from src.services.utils.gemini_fallback import generate_content_with_fallback

            response, _model = await generate_content_with_fallback(
                client,
                primary_model="gemini-1.5-pro",  # sintez — murakkab fikrlash
                contents=prompt,
                log_prefix=f"[COACH:{tag}]",
            )
            text = (getattr(response, "text", "") or "").strip()
            return text or None
        except Exception as exc:
            logger.warning("[COACH] %s LLM xatosi: %s", tag, exc)
            return None
