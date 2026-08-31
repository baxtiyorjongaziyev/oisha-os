"""
Decision making and AI generation mixin for Autonomous Sales Closer.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from src.agents.closer.models import ConversationState
from src.agents.closer.proposals import ProposalEngine
from src.services.utils.gemini_fallback import generate_content_with_fallback
from src.settings import settings

logger = logging.getLogger(__name__)


class AutonomousDecisionsMixin:
    """Decision logic, objection resolution and prompt generation."""

    async def _make_autonomous_decision(
        self,
        message: str,
        state: ConversationState,
        assessment: Any,
    ) -> Dict[str, Any]:
        decision = {
            "action": "reply",
            "confidence": 0.8,
            "next_stage": state.stage,
            "autonomy_level": "full",
            "offer_proposal": False,
            "escalate_to_human": False,
            "discount_allowed": 0.0,
        }

        if assessment.objection == "price_high":
            if state.stage in ["negotiating", "closing"]:
                decision["discount_allowed"] = 10.0
                decision["action"] = "offer_discount"
            else:
                decision["action"] = "reframe_value"

        elif assessment.intent == "ready_to_buy":
            decision["action"] = "close_deal"
            decision["next_stage"] = "closing"
            decision["offer_proposal"] = True

        elif assessment.intent == "pricing":
            decision["action"] = "present_pricing"
            decision["next_stage"] = "negotiating"

        elif assessment.intent == "portfolio":
            decision["action"] = "show_cases"

        elif assessment.urgency in ["high", "critical"]:
            decision["action"] = "fast_track"
            decision["next_stage"] = "negotiating"

        if assessment.close_probability > 0.8:
            decision["next_stage"] = "closing"
        elif assessment.close_probability < 0.2 and len(state.history) > 6:
            decision["autonomy_level"] = "human_takeover"
            decision["escalate_to_human"] = True

        return decision

    async def _generate_response(
        self,
        message: str,
        state: ConversationState,
        decision: Dict[str, Any],
        assessment: Any,
    ) -> str:
        prompt = f"""Sen Jon Branding agentligining bosh sotuv bo'yicha maslahatchisisan.
Vazifang — mijoz bilan tabiiy, professional va ishonchli muloqot qilish.

Mijoz xabari: {message}
Joriy bosqich: {state.stage}
Mijoz niyati: {assessment.intent}
E'tiroz: {assessment.objection}
Qaror: {decision['action']}

Qoidalar:
- O'zbek tilida, do'stona va professional ohangda yoz.
- Qisqa va lo'nda javob ber (2-4 gap).
- Har doim aniq keyingi qadamni taklif qil (Call to Action).
- Narx so'ralsa, avval qiymatni ko'rsat, keyin taxminiy diapazon ber.
"""
        try:
            return await generate_content_with_fallback(
                prompt=prompt,
                model="gemini-1.5-flash",
                temperature=0.7,
            )
        except Exception as e:
            logger.error(f"AI response generation failed: {e}")
            return self._generate_fallback_response(decision)

    def _generate_fallback_response(self, decision: Dict[str, Any]) -> str:
        action = decision.get("action", "reply")
        fallbacks = {
            "present_pricing": "Bizning xizmatlarimiz narxi loyiha hajmiga qarab 5 mln so'mdan boshlanadi. Sizga qaysi xizmat qiziq?",
            "offer_discount": "Siz uchun maxsus 10% chegirma taqdim eta olamiz. Bu taklif sizga ma'qulmi?",
            "close_deal": "Ajoyib! Loyihani boshlash uchun shartnoma tayyorlaylikmi yoki uchrashuv belgilaymizmi?",
            "show_cases": "Bizning so'nggi muvaffaqiyatli loyihalarimiz bilan jonbranding.uz saytida tanishishingiz mumkin.",
            "reframe_value": "Biz nafaqat dizayn, balki brendingiz sotuvlarini oshiruvchi to'liq strategiya yaratamiz.",
        }
        return fallbacks.get(
            action,
            "Xabaringiz uchun rahmat! Savollaringizga mamnuniyat bilan javob beraman.",
        )

    def _get_objection_strategy(self, objection: str) -> str:
        strategies = {
            "price_high": "Qiymatni ta'kidlash, to'lovni bo'lib to'lashni taklif qilish.",
            "need_think": "Qo'shimcha savollarni aniqlash, keyslarni ko'rsatish.",
            "competitor": "Jon Branding ning ustunliklarini ko'rsatish (tezlik, sifat, kafolat).",
            "trust": "Kafolatlar, portfel va mijozlar sharhlarini taqdim etish.",
        }
        return strategies.get(objection, "Mijoz ehtiyojlarini chuqurroq o'rganish.")

    async def _generate_follow_up(self, state: ConversationState) -> str:
        return "Assalomu alaykum! Loyihangiz bo'yicha gaplashgan edik. Savollaringiz qolmadimi?"
