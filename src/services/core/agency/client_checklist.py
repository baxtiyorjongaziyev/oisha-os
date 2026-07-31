"""
ClientChecklist — Mijoz hayot sikli bo'yicha jamoa cheklisti.

7 bosqich, 29 element. Har bir lead uchun alohida checklist yaratiladi.
Oisha bu checklist asosida jamoani nazorat qiladi va baholaydi.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# CHECKLIST TEMPLATE — Jon Branding Client Lifecycle
# ─────────────────────────────────────────────
CHECKLIST_TEMPLATE: List[Dict[str, Any]] = [
    # BOSQICH 1: KIRISH
    {"stage": "intake",    "key": "intake_crm",      "label": "CRM ga kiritildi",                    "due_hours": 2},
    {"stage": "intake",    "key": "intake_reply",     "label": "24 soat ichida javob berildi",         "due_hours": 24},
    {"stage": "intake",    "key": "intake_channel",   "label": "Muloqot kanali aniqlandi",             "due_hours": 4},
    {"stage": "intake",    "key": "intake_manager",   "label": "Mas'ul menejer tayinlandi",            "due_hours": 4},

    # BOSQICH 2: BRIEF
    {"stage": "brief",     "key": "brief_filled",     "label": "Brief to'ldirildi",                   "due_hours": 48},
    {"stage": "brief",     "key": "brief_budget",     "label": "Byudjet diapazoni aniqlandi",          "due_hours": 48},
    {"stage": "brief",     "key": "brief_deadline",   "label": "Muddat kelishildi",                    "due_hours": 48},
    {"stage": "brief",     "key": "brief_decision",   "label": "Qaror qabul qiluvchi aniqlandi",       "due_hours": 72},

    # BOSQICH 3: TAKLIF (KP)
    {"stage": "proposal",  "key": "kp_prepared",      "label": "Tijorat taklif (KP) tayyorlandi",     "due_hours": 24},
    {"stage": "proposal",  "key": "kp_sent",          "label": "KP mijozga yuborildi",                "due_hours": 48},
    {"stage": "proposal",  "key": "kp_response",      "label": "Mijozdan javob olindi",               "due_hours": 72},
    {"stage": "proposal",  "key": "kp_agreed",        "label": "Narx/shartlar kelishildi",            "due_hours": 96},

    # BOSQICH 4: SHARTNOMA
    {"stage": "contract",  "key": "contract_ready",   "label": "Shartnoma tayyorlandi",               "due_hours": 24},
    {"stage": "contract",  "key": "contract_signed",  "label": "Shartnoma imzolandi",                 "due_hours": 72},
    {"stage": "contract",  "key": "contract_advance", "label": "Avans to'lovi qabul qilindi (≥50%)",  "due_hours": 72},
    {"stage": "contract",  "key": "contract_airtable","label": "Loyiha Airtable ga kiritildi",        "due_hours": 4},

    # BOSQICH 5: IJRO
    {"stage": "execution", "key": "exec_assigned",    "label": "Mas'ul dizayner/xodim tayinlandi",    "due_hours": 8},
    {"stage": "execution", "key": "exec_concept",     "label": "Dastlabki konsepsiya tayyorlandi",    "due_hours": 72},
    {"stage": "execution", "key": "exec_present1",    "label": "1-taqdimot o'tkazildi",              "due_hours": 96},
    {"stage": "execution", "key": "exec_revisions",   "label": "Tuzatishlar qabul qilindi",           "due_hours": 48},
    {"stage": "execution", "key": "exec_final",       "label": "Final variant tayyorlandi",           "due_hours": 48},
    {"stage": "execution", "key": "exec_approved",    "label": "Mijoz final variantni tasdiqladi",    "due_hours": 72},

    # BOSQICH 6: TOPSHIRISH
    {"stage": "delivery",  "key": "del_files",        "label": "Barcha source fayllar topshirildi",   "due_hours": 24},
    {"stage": "delivery",  "key": "del_payment",      "label": "To'lov to'liq qabul qilindi (100%)",  "due_hours": 72},
    {"stage": "delivery",  "key": "del_handover",     "label": "Qabul dalolatnomasi / tasdiq xati",   "due_hours": 48},

    # BOSQICH 7: RETENTION
    {"stage": "retention", "key": "ret_nps",          "label": "NPS/feedback so'raldi",              "due_hours": 24},
    {"stage": "retention", "key": "ret_testimonial",  "label": "Testimonial/sharh olindi",            "due_hours": 168},
    {"stage": "retention", "key": "ret_referral",     "label": "Referral dasturi taqdim etildi",      "due_hours": 72},
    {"stage": "retention", "key": "ret_followup",     "label": "1 oylik follow-up rejalashtirildi",   "due_hours": 48},
]

STAGE_NAMES = {
    "intake":    "📥 Kirish",
    "brief":     "📋 Brief",
    "proposal":  "📄 Taklif (KP)",
    "contract":  "✍️ Shartnoma",
    "execution": "🎨 Ijro",
    "delivery":  "📦 Topshirish",
    "retention": "🤝 Retention",
}

STATUS_EMOJI = {
    "done":    "✅",
    "pending": "⏳",
    "overdue": "🔴",
    "skipped": "⏭️",
}


class ClientChecklist:
    """Mijoz cheklisti — DB operatsiyalari va ball hisoblash."""

    def __init__(self, db):
        self.db = db

    async def create_for_lead(
        self,
        lead_id: int,
        lead_name: str,
        manager_id: Optional[int] = None,
    ) -> int:
        """Yangi lead uchun to'liq checklist yaratish."""
        now = datetime.now().isoformat()
        conn = await self.db.get_connection()
        inserted = 0
        for item in CHECKLIST_TEMPLATE:
            try:
                await conn.execute(
                    """
                    INSERT OR IGNORE INTO client_checklists
                        (lead_id, lead_name, manager_id, item_key, stage, label, due_hours, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (lead_id, lead_name, manager_id, item["key"],
                     item["stage"], item["label"], item["due_hours"], now),
                )
                inserted += 1
            except Exception as e:
                logger.error(f"[CHECKLIST] insert error {item['key']}: {e}")
        await conn.commit()
        return inserted

    async def mark_done(
        self,
        lead_id: int,
        item_key: str,
        completed_by: Optional[int] = None,
        notes: str = "",
    ) -> bool:
        """Checklist elementini bajarilgan deb belgilash."""
        now = datetime.now().isoformat()
        conn = await self.db.get_connection()
        await conn.execute(
            """
            UPDATE client_checklists
            SET status='done', completed_by=?, completed_at=?, notes=?
            WHERE lead_id=? AND item_key=? AND status != 'done'
            """,
            (completed_by, now, notes, lead_id, item_key),
        )
        await conn.commit()
        return True

    async def get_lead_checklist(self, lead_id: int) -> List[Dict[str, Any]]:
        """Lead uchun checklist elementlarini olish."""
        conn = await self.db.get_connection()
        rows = await conn.execute_fetchall(
            "SELECT * FROM client_checklists WHERE lead_id=? ORDER BY id",
            (lead_id,),
        )
        return [dict(r) for r in rows]

    async def get_overdue_items(self) -> List[Dict[str, Any]]:
        """Muddati o'tgan (overdue) elementlarni topish."""
        conn = await self.db.get_connection()
        rows = await conn.execute_fetchall(
            """
            SELECT * FROM client_checklists
            WHERE status = 'pending'
              AND datetime(created_at, '+' || due_hours || ' hours') < datetime('now')
            ORDER BY lead_id, id
            """,
        )
        return [dict(r) for r in rows]

    async def get_stage_completion(self, lead_id: int) -> Dict[str, Dict[str, Any]]:
        """Har bir bosqich uchun bajarilish foizini hisoblash."""
        items = await self.get_lead_checklist(lead_id)
        stages: Dict[str, Dict[str, Any]] = {}
        for item in items:
            stage = item["stage"]
            if stage not in stages:
                stages[stage] = {"total": 0, "done": 0, "overdue": 0}
            stages[stage]["total"] += 1
            if item["status"] == "done":
                stages[stage]["done"] += 1
            elif item["status"] == "pending":
                due_at = datetime.fromisoformat(item["created_at"]) + timedelta(hours=item["due_hours"] or 24)
                if datetime.now() > due_at:
                    stages[stage]["overdue"] += 1
        return stages

    async def score_manager(
        self, manager_id: int, since_days: int = 7
    ) -> Dict[str, Any]:
        """Menejer uchun sifat balli hisoblash (0-100)."""
        cutoff = (datetime.now() - timedelta(days=since_days)).isoformat()
        conn = await self.db.get_connection()
        rows = await conn.execute_fetchall(
            """
            SELECT status, due_hours, created_at, completed_at
            FROM client_checklists
            WHERE manager_id=? AND created_at >= ?
            """,
            (manager_id, cutoff),
        )
        items = [dict(r) for r in rows]
        if not items:
            return {"score": 0, "total": 0, "done": 0, "overdue": 0, "on_time": 0}

        total = len(items)
        done = sum(1 for i in items if i["status"] == "done")
        on_time = 0
        for i in items:
            if i["status"] == "done" and i["completed_at"] and i["created_at"]:
                due_at = datetime.fromisoformat(i["created_at"]) + timedelta(hours=i["due_hours"] or 24)
                completed_at = datetime.fromisoformat(i["completed_at"])
                if completed_at <= due_at:
                    on_time += 1
        overdue = sum(
            1 for i in items
            if i["status"] == "pending"
            and datetime.now() > datetime.fromisoformat(i["created_at"]) + timedelta(hours=i["due_hours"] or 24)
        )

        completion_rate = done / total if total else 0
        on_time_rate = on_time / done if done else 0
        overdue_penalty = overdue / total if total else 0

        score = int((completion_rate * 60 + on_time_rate * 40 - overdue_penalty * 20) * 100)
        score = max(0, min(100, score))

        return {
            "score": score,
            "total": total,
            "done": done,
            "on_time": on_time,
            "overdue": overdue,
            "completion_pct": round(completion_rate * 100),
            "on_time_pct": round(on_time_rate * 100) if done else 0,
        }

    def format_checklist_text(
        self,
        items: List[Dict[str, Any]],
        lead_name: str,
    ) -> str:
        """Checklist'ni Telegram-friendly matn sifatida formatlash."""
        now = datetime.now()
        by_stage: Dict[str, List[Dict]] = {}
        for item in items:
            by_stage.setdefault(item["stage"], []).append(item)

        lines = [f"📋 <b>{lead_name}</b> — Mijoz cheklisti\n"]
        for stage_key, stage_items in by_stage.items():
            done_count = sum(1 for i in stage_items if i["status"] == "done")
            total_count = len(stage_items)
            pct = round(done_count / total_count * 100) if total_count else 0
            stage_label = STAGE_NAMES.get(stage_key, stage_key)
            lines.append(f"\n{stage_label} — {done_count}/{total_count} ({pct}%)")
            for item in stage_items:
                status = item["status"]
                if status == "pending":
                    due_at = datetime.fromisoformat(item["created_at"]) + timedelta(hours=item["due_hours"] or 24)
                    if now > due_at:
                        status = "overdue"
                emoji = STATUS_EMOJI.get(status, "⏳")
                lines.append(f"  {emoji} {item['label']}")

        return "\n".join(lines)

    def format_score_text(self, score_data: Dict[str, Any], manager_name: str) -> str:
        """Menejer ball xulosasini formatlash."""
        score = score_data["score"]
        if score >= 85:
            verdict = "🏆 A'lo"
        elif score >= 70:
            verdict = "✅ Yaxshi"
        elif score >= 50:
            verdict = "⚠️ O'rtacha"
        else:
            verdict = "🔴 Yaxshilash kerak"

        return (
            f"📊 <b>{manager_name}</b> — Haftalik ball\n\n"
            f"🎯 Umumiy ball: <b>{score}/100</b> — {verdict}\n"
            f"📋 Jami element: {score_data['total']}\n"
            f"✅ Bajarildi: {score_data['done']} ({score_data['completion_pct']}%)\n"
            f"⏰ O'z vaqtida: {score_data['on_time']} ({score_data['on_time_pct']}%)\n"
            f"🔴 Kechikmoqda: {score_data['overdue']}\n"
        )
