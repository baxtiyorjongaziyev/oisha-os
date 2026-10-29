"""
Winning Script Evolver — Avtomatik Rivojlanuvchi Sotuv Skripti Dvigateli.

Qo'ng'iroq tahlili jarayonida yuqori baholangan (score >= 75) va muvaffaqiyatli
yakunlangan (outcome converted: to'lov, uchrashuv, material yuborish, KP) qo'ng'iroqlardan
eng yaxshi ishlayotgan iboralar, e'tiroz yechimlari va yondashuvlarni avtomatik ajratib oladi,
ularni doimiy bilimlar bazasiga saqlaydi va barcha sotuvchilarga avtomat tarqatadi.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

WINNING_SCRIPTS_FILE = Path("data/winning_sales_scripts.json")

CONVERTING_OUTCOMES = frozenset(
    {
        "tolov_kelishildi",
        "uchrashuv_kelishildi",
        "material_yuborish",
        "kp_yuborish",
        "uchrashuv sanasi belgilandi (offline yoki online)",
        "portfolio/keys yuborish kelishildi",
        "KP (tijorat taklifi) yuborish kelishildi",
        "to'lov kelishildi",
    }
)


class WinningScriptEvolver:
    """
    Qo'ng'iroqlar ichidan g'olib usullarni aniqlab, skriptni avtomatik boyituvchi xizmat.
    """

    def __init__(self, db: Any = None, tg_client: Any = None):
        self.db = db
        self.tg_client = tg_client
        self._ensure_storage()

    def _ensure_storage(self) -> None:
        try:
            WINNING_SCRIPTS_FILE.parent.mkdir(parents=True, exist_ok=True)
            if not WINNING_SCRIPTS_FILE.exists():
                WINNING_SCRIPTS_FILE.write_text("[]", encoding="utf-8")
        except Exception as exc:
            logger.warning("[WINNING-SCRIPT] Storage init warning: %s", exc)

    def is_winning_call(self, analysis: Dict[str, Any]) -> bool:
        """Qo'ng'iroq konversiyali va yuqori sifatli ekanini aniqlaydi."""
        score = analysis.get("sifat_bahosi") or analysis.get("overall_score") or 0
        if isinstance(score, str):
            try:
                score = int(score)
            except ValueError:
                score = 0

        outcome = str(analysis.get("natija") or analysis.get("outcome") or "").lower()
        converted = bool(analysis.get("converted")) or (outcome in CONVERTING_OUTCOMES)

        return score >= 75 and (converted or outcome in CONVERTING_OUTCOMES)

    async def evolve_from_call(
        self,
        lead_id: int,
        caller_phone: str,
        manager_name: str,
        duration_seconds: int,
        transcript: str,
        analysis: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Agar qo'ng'iroq muvaffaqiyatli bo'lsa, undan g'olib yondashuvni ajratib oladi va saqlaydi.
        """
        if not self.is_winning_call(analysis):
            return None

        score = analysis.get("sifat_bahosi") or analysis.get("overall_score") or 80
        outcome = analysis.get("natija") or analysis.get("outcome") or "kelishildi"
        summary = analysis.get("suhbat_xulosasi") or analysis.get("summary") or ""
        strengths = analysis.get("strengths") or analysis.get("kuchli_tomonlari") or []
        if isinstance(strengths, str):
            strengths = [strengths]

        advice = analysis.get("konversiya_tavsiyalari") or ""

        # G'olib namuna tuzilmasi
        winning_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "lead_id": lead_id,
            "manager_name": manager_name or "Menejer",
            "caller_phone": caller_phone,
            "score": score,
            "outcome": outcome,
            "duration_seconds": duration_seconds,
            "summary": summary,
            "key_strengths": strengths,
            "winning_technique": self._extract_winning_technique(summary, strengths, transcript),
        }

        self._save_winning_record(winning_record)
        logger.info(
            "[WINNING-SCRIPT] New winning technique captured for lead=%s score=%s manager=%s",
            lead_id, score, manager_name
        )
        return winning_record

    def _extract_winning_technique(
        self, summary: str, strengths: List[str], transcript: str
    ) -> str:
        """Suhbatdan eng ta'sirchan usulni formula qiladi."""
        techniques = []
        if strengths:
            techniques.append(" / ".join(strengths[:2]))

        low = (summary + " " + transcript).lower()
        if "notarius" in low or "ishonchnoma" in low:
            techniques.append("Notarius/ishonchnoma tartibi online ekani aniq tushuntirilib, byurokratiya xavfi bartaraf etildi.")
        if "bosqich" in low or "bolib" in low or "bo'lib" in low:
            techniques.append("To'lov 2 bosqichga (boshlang'ich ariza va guvohnoma) bo'lib berilishi taklif qilindi.")
        if "tekshir" in low or "audit" in low or "ekspert" in low:
            techniques.append("Katta xarajatdan oldin 1 kunda rasmiy Ekspert tekshiruvi (kichik qadam) taklif etildi.")
        if "telegram" in low:
            techniques.append("Materiallar/nomlarni darhol Telegram orqali yuborishga kelishib, mijoz bilan yozma kanal ochildi.")

        return "; ".join(techniques) if techniques else summary[:200]

    def _save_winning_record(self, record: Dict[str, Any]) -> None:
        try:
            records: List[Dict[str, Any]] = []
            if WINNING_SCRIPTS_FILE.exists():
                try:
                    records = json.loads(WINNING_SCRIPTS_FILE.read_text(encoding="utf-8"))
                except Exception:
                    records = []

            # Dublikat bo'lmasligi uchun lead_id bo'yicha tekshirish
            records = [r for r in records if r.get("lead_id") != record.get("lead_id")]
            records.append(record)

            # Oxirgi 100 ta g'olib qo'ng'iroqni saqlash
            records = records[-100:]
            WINNING_SCRIPTS_FILE.write_text(
                json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception as exc:
            logger.warning("[WINNING-SCRIPT] Save error: %s", exc)

    def get_top_winning_techniques(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Eng yuqori baholangan g'olib usullarni qaytaradi."""
        try:
            if not WINNING_SCRIPTS_FILE.exists():
                return []
            records = json.loads(WINNING_SCRIPTS_FILE.read_text(encoding="utf-8"))
            records.sort(key=lambda x: x.get("score", 0), reverse=True)
            return records[:limit]
        except Exception:
            return []

    def format_telegram_broadcast(self, record: Dict[str, Any]) -> str:
        """Sotuvchilar guruhiga yuboriladigan g'olib usul xabari."""
        manager = record.get("manager_name", "Menejer")
        score = record.get("score", 80)
        outcome = record.get("outcome", "kelishildi")
        technique = record.get("winning_technique", "")
        summary = record.get("summary", "")

        return (
            f"🏆 **YANGI G'OLIB YONDASHUV ANIQLANDI!**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🧑‍💼 **Menejer:** {manager}\n"
            f"⭐️ **Sifat bahosi:** {score}/100\n"
            f"🎯 **Natija:** {outcome}\n"
            f"💡 **Ishlagan g'olib usul:**\n{technique}\n"
            f"📝 **Xulosa:** {summary}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 *Barcha sotuvchilar ushbu usulni o'z qo'ng'iroqlarida amalda qo'llasin!*"
        )
