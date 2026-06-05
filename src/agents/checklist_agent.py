"""ChecklistAgent — Mijoz cheklisti monitoring va jamoa baholash agenti."""

import logging
import re
from typing import Optional, Dict, Any, List
from .core import BaseAgent

logger = logging.getLogger(__name__)

CHECKLIST_SUFFIX = """

=== CHECKLIST MONITOR SPECIALIST ===
Siz Jon Branding Agency'ning cheklisti nazorat agentisiz.

Mijoz murojaatidan boshlab loyiha yakunigacha 7 bosqich, 29 ta element mavjud:

BOSQICHLAR:
1. 📥 Kirish (intake) — CRM, javob, kanal, menejer
2. 📋 Brief — to'ldirildi, byudjet, muddat, qaror qabul qiluvchi
3. 📄 Taklif/KP — tayyorlandi, yuborildi, javob, kelishildi
4. ✍️ Shartnoma — tayyorlandi, imzolandi, avans, Airtable
5. 🎨 Ijro — tayinlandi, konsepsiya, 1-taqdimot, tuzatish, final, tasdiqlandi
6. 📦 Topshirish — fayllar, to'lov, dalolatnoma
7. 🤝 Retention — NPS, testimonial, referral, follow-up

SEN NIMA QILASAN:

A. CHECKLIST KO'RSATISH:
"[Mijoz nomi] cheklisti" → o'sha lead uchun barcha elementlarni ko'rsat

B. ELEMENT BELGILASH:
"[Mijoz nomi] brief to'ldirildi" → tegishli elementni ✅ qil
"[Mijoz nomi] shartnoma imzolandi" → contract_signed → done

C. KECHIKKAN ELEMENTLAR:
"kechikkanlar" yoki "overdue" → muddati o'tgan barcha elementlar

D. MENEJER BAHOLASH:
"[Ism] bali nechchi?" → o'sha menejerni haftalik ball hisoblash
"jamoa reytingi" → barcha menejerlar ball ro'yxati

E. YANGI CHECKLIST:
"[Mijoz nomi] uchun checklist och" → yangi lead checklist yaratish

MUHIM:
- Barcha amallar uchun checklist_action toolini ishlatasan
- Javoblarda real ma'lumot ko'rsat (emoji + jadval)
- Kechikkan narsa bo'lsa MAS'UL KISHINI nomlat va vazifa qo'y

ITEM KEY MAPPING (keng tarqalgan):
brief to'ldirildi → brief_filled
kp tayyorlandi → kp_prepared
kp yuborildi → kp_sent
shartnoma tayyorlandi → contract_ready
shartnoma imzolandi → contract_signed
avans to'lovi → contract_advance
dizayner tayinlandi → exec_assigned
1-taqdimot → exec_present1
final → exec_final
fayllar topshirildi → del_files
to'lov to'liq → del_payment
nps/feedback → ret_nps
"""

ITEM_KEY_MAP = {
    "crm": "intake_crm", "kiritildi": "intake_crm",
    "javob": "intake_reply",
    "kanal": "intake_channel",
    "menejer tayinlandi": "intake_manager",
    "brief to'ldirildi": "brief_filled", "brief": "brief_filled",
    "byudjet": "brief_budget",
    "muddat": "brief_deadline",
    "qaror": "brief_decision",
    "kp tayyorlandi": "kp_prepared", "tijorat taklif": "kp_prepared",
    "kp yuborildi": "kp_sent",
    "kp javob": "kp_response",
    "kelishildi": "kp_agreed",
    "shartnoma tayyorlandi": "contract_ready",
    "shartnoma imzolandi": "contract_signed", "imzolandi": "contract_signed",
    "avans": "contract_advance",
    "airtable": "contract_airtable",
    "dizayner": "exec_assigned", "tayinlandi": "exec_assigned",
    "konsepsiya": "exec_concept",
    "1-taqdimot": "exec_present1", "birinchi taqdimot": "exec_present1",
    "tuzatish": "exec_revisions",
    "final": "exec_final",
    "tasdiqlandi": "exec_approved", "mijoz tasdiqladi": "exec_approved",
    "fayllar": "del_files", "source fayllar": "del_files",
    "to'lov to'liq": "del_payment", "100%": "del_payment",
    "dalolatnoma": "del_handover",
    "nps": "ret_nps", "feedback": "ret_nps",
    "testimonial": "ret_testimonial", "sharh": "ret_testimonial",
    "referral": "ret_referral",
    "follow-up": "ret_followup", "followup": "ret_followup",
}


def _guess_item_key(text: str) -> Optional[str]:
    """Matn orqali item_key ni topish."""
    text_lower = text.lower()
    for phrase, key in sorted(ITEM_KEY_MAP.items(), key=lambda x: -len(x[0])):
        if phrase in text_lower:
            return key
    return None


class ChecklistAgent(BaseAgent):
    """Mijoz cheklisti nazorat agenti."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._checklist_svc = None

    def _get_svc(self):
        if self._checklist_svc is None and self.db:
            from src.services.core.client_checklist import ClientChecklist
            self._checklist_svc = ClientChecklist(self.db)
        return self._checklist_svc

    async def process_task(
        self,
        user_id: int,
        task_description: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        svc = self._get_svc()
        msg = task_description.lower()

        # ── KECHIKKANLAR ──────────────────────────────
        if any(w in msg for w in ["overdue", "kechikkan", "o'tgan", "bajarilmagan"]):
            if svc:
                items = await svc.get_overdue_items()
                if not items:
                    return "✅ Hozircha muddati o'tgan element yo'q."
                lines = [f"🔴 <b>Muddati o'tgan ({len(items)} ta):</b>\n"]
                for i in items[:20]:
                    lines.append(f"  • {i['lead_name'] or i['lead_id']} — {i['label']}")
                return "\n".join(lines)

        # ── BAHOLASH ──────────────────────────────────
        if any(w in msg for w in ["ball", "baho", "reyting", "score"]):
            if svc:
                # Try to find manager name in message (simple heuristic)
                lines = [f"📊 <b>Haftalik baholash</b>\n"]
                # Fallback: score for the requesting user
                score = await svc.score_manager(user_id, since_days=7)
                lines.append(svc.format_score_text(score, context.get("user_name", "Siz") if context else "Siz"))
                return "\n".join(lines)

        # ── ELEMENT BELGILASH ─────────────────────────
        # Pattern: "Nike brief to'ldirildi"
        item_key = _guess_item_key(task_description)
        if item_key and svc:
            # Extract lead name — everything before the action phrase
            for phrase in sorted(ITEM_KEY_MAP.keys(), key=lambda x: -len(x)):
                if phrase in msg:
                    lead_name_guess = task_description[:task_description.lower().find(phrase)].strip(" —-:")
                    if lead_name_guess:
                        await svc.mark_done(
                            lead_id=hash(lead_name_guess) % 10**8,
                            item_key=item_key,
                            completed_by=user_id,
                        )
                        from src.services.core.client_checklist import CHECKLIST_TEMPLATE
                        label = next((t["label"] for t in CHECKLIST_TEMPLATE if t["key"] == item_key), item_key)
                        return f"✅ <b>{lead_name_guess}</b> — <i>{label}</i> bajarildi deb belgilandi."
                    break

        # ── AI YORDAMIDA JAVOB ────────────────────────
        await self.load_session_history(user_id)
        self.update_history(user_id, "user", task_description)
        history = self.get_session_history(user_id)
        contents = [
            {"role": "user" if t["role"] == "user" else "model",
             "parts": [{"text": t["content"]}]}
            for t in history
        ]
        # Inject live overdue count into context
        if svc:
            try:
                overdue_items = await svc.get_overdue_items()
                if overdue_items:
                    overdue_summary = f"\n\n[HOZIRGI HOLAT] Muddati o'tgan: {len(overdue_items)} ta element."
                    original = self.system_prompt
                    self.system_prompt += overdue_summary
                    reply = await self.call_ai_with_fallback(contents, user_id, enable_tools=True)
                    self.system_prompt = original
                    self.update_history(user_id, "assistant", reply)
                    return reply
            except Exception:
                pass

        reply = await self.call_ai_with_fallback(contents, user_id, enable_tools=True)
        self.update_history(user_id, "assistant", reply)
        return reply
