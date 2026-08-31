"""
Semantic AI-powered negotiation assessment and mission generator.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from google import genai
from src.agents.negotiation.models import NegotiationAssessment
from src.agents.negotiation.rule_assessor import NegotiationRuleMixin
from src.services.utils.gemini_fallback import generate_content_with_fallback
from src.settings import settings

logger = logging.getLogger(__name__)


class NegotiationEngine(NegotiationRuleMixin):
    """Two-mode assessment: fast rule-based and Gemini semantic."""

    @staticmethod
    async def assess_async(
        message: str,
        crm_status: str = "",
        *,
        autonomy_mode: str = "autonomous",
        history: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> NegotiationAssessment:
        """Gemini-powered semantic assessment — full NLP understanding."""
        context = context or {}
        try:
            client = genai.Client(api_key=settings.GEMINI_API_KEY.get_secret_value())

            history_text = ""
            if history:
                last_5 = history[-5:]
                history_text = "\n".join(
                    f"{m['role'].upper()}: {m['content']}" for m in last_5
                )

            # Qo'ng'iroq tahlili kontekstini qo'shish
            analysis_context = ""
            if "latest_call_analysis" in context:
                analysis = context["latest_call_analysis"]
                analysis_context = f"""
OXIRGI QO'NG'IROQ TAHLILI (Sifat bahosi: {analysis.get('overall_score')}/100):
- Xulosa: {analysis.get('summary')}
- Mijoz kayfiyati: {analysis.get('client_mood')}
- E'tirozlar: {analysis.get('objections')}
- Keyingi qadamlar: {analysis.get('next_steps')}
"""

            _MEDDPICC_INJECT = """
QUALIFICATION FRAMEWORK (apply silently during analysis):
MEDDPICC: Metrics | Economic Buyer | Decision Criteria | Decision Process | Paper Process | Pain | Champion | Competition
- Metrics: Can buyer quantify the cost of inaction? No number = no urgency.
- Economic Buyer: Has the buyer confirmed budget authority, or are we stuck with an influencer?
- Pain: Is stated pain specific and quantified, or generic? Generic = low urgency.
- Champion: Is our internal advocate willing to take difficult actions on our behalf?
Discovery lens: Is buyer talking 60%+? Have we surfaced implication questions (cost of inaction)?
Challenger signal: Can we reframe their problem before presenting solution?
SPIN check: Have we asked Situation (2-3 max) → Problem → Implication → Need-Payoff?
"""

            prompt = f"""
Sen "Oisha-OS" savdo tahlilchisisan. Quyidagi mijoz xabarini, suhbat tarixini va
real qo'ng'iroqlar tahlilini CHUQUR o'rganib, JSON formatida qaytarishing kerak.

SUHBAT TARIXI (oxirgi 5 xabar):
{history_text or "Yangi suhbat"}
{analysis_context}
{_MEDDPICC_INJECT}
JORIY XABAR: "{message}"
CRM HOLATI: "{crm_status}"
IS_GUEST: {(context or {}).get("is_guest", False)}
IS_BOT: {(context or {}).get("is_bot", False)} (Bot-to-Bot negotiation awareness)

Sening maqsading - agentga ushbu mijoz bilan AVTONOM (mustaqil) gaplashish uchun yo'riqnoma berish.

JSON sxemasi:
{{
  "stage": "new_lead|qualified|meeting_ready|closing",
  "intent": "qualify|pricing|meeting|closing|proof|nurture|complaint|referral",
  "objection": "none|price|trust|timing|competition|legal|budget|authority",
  "urgency": "high|normal|low",
  "sentiment": "positive|neutral|negative|excited|confused",
  "close_probability": 0.0-1.0,
  "recommended_status": "Initial Contact|Interested|Meeting Scheduled|Proposal Sent|Negotiating|Qualified|Won",
  "next_action": "qualify_need|value_anchor|show_relevant_case|schedule_strategy_session|confirm_scope_and_close|create_followup_commitment|handle_price_objection|escalate_to_senior",
  "approval_needed": true/false,
  "risk_flags": [],
  "pain_points": [],
  "buying_signals": [],
  "decision_factors": [],
  "autonomous_mission": "Agent o'zi bajarishi kerak bo'lgan aniq vazifa (uzbek tilida)"
}}

Qoidalar:
- autonomous_mission: Agent inson aralashuvisiz bajaradigan aniq harakat (masalan: 'Mijozga 3-chi paket narxini taklif qilish va uchrashuv belgilash').
- Agar qo'ng'iroq tahlilida e'tiroz bo'lgan bo'lsa, uni hozirgi matnli suhbatda hal qilishni hisobga ol.
- Faqat JSON qaytarish.
"""

            response, _ = await generate_content_with_fallback(
                client,
                primary_model=settings.GEMINI_CALL_MODEL,
                contents=prompt,
                env_name="GEMINI_NEGOTIATION_FALLBACK_MODELS",
                log_prefix="[NEGOTIATION]",
            )
            text = (response.text or "").strip()
            # Clean markdown code blocks if present
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)

            data = json.loads(text)

            return NegotiationAssessment(
                stage=data.get("stage", "new_lead"),
                intent=data.get("intent", "qualify"),
                objection=data.get("objection", "none"),
                urgency=data.get("urgency", "normal"),
                sentiment=data.get("sentiment", "neutral"),
                close_probability=max(0.0, min(1.0, float(data.get("close_probability", 0.3)))),
                autonomy_mode=autonomy_mode,
                recommended_status=data.get("recommended_status", "Initial Contact"),
                next_action=data.get("next_action", "qualify_need"),
                approval_needed=bool(data.get("approval_needed", False)),
                risk_flags=data.get("risk_flags", []),
                pain_points=data.get("pain_points", []),
                buying_signals=data.get("buying_signals", []),
                decision_factors=data.get("decision_factors", []),
                autonomous_mission=data.get("autonomous_mission", ""),
            )

        except Exception as exc:
            logger.warning("[NegotiationEngine] assess_async failed: %r — keyword fallback", exc)
            return NegotiationEngine.assess(
                message,
                crm_status,
                autonomy_mode=autonomy_mode,
                history=history,
                context=context,
            )

    # ─────────────────────────── SYNC KEYWORD ────────────────────────────

    @staticmethod

    @staticmethod
    async def generate_surgical_mission(
        assessment: NegotiationAssessment,
        summary: Optional[str] = None,
        pipeline_name: str = "HUNTER",
        role: str = "HUNTER",
    ) -> str:
        """Gemini yordamida menejer uchun 'Surgical Mission' yaratish."""

        if not summary:
            return f"Bitimni keyingi '{assessment.stage}' bosqichiga o'tkazing."

        try:
            client = genai.Client(api_key=settings.GEMINI_API_KEY.get_secret_value())

            pain_str = (
                ", ".join(assessment.pain_points)
                if assessment.pain_points
                else "aniqlanmagan"
            )
            signals_str = (
                ", ".join(assessment.buying_signals)
                if assessment.buying_signals
                else "yo'q"
            )

            prompt = f"""
Siz "Oisha-OS Surgical Strategist"siz. Menejer uchun keyingi 3 ta aniq harakat belgilang.

Menejer roli: {role} | Pipeline: {pipeline_name}
Suhbat xulosasi: {summary}
Tahlil: bosqich={assessment.stage}, intent={assessment.intent}, ehtimol={assessment.close_probability:.0%}
E'tiroz: {assessment.objection} | Sentiment: {assessment.sentiment}
Og'riq nuqtalar: {pain_str}
Sotib olish signallari: {signals_str}
Risk: {", ".join(assessment.risk_flags) or "yo'q"}

Format (qisqa, actionable):
[1] Strategiya: ...
[2] Keyingi savol: "..."
[3] Xavf faktori: ...

Faqat 3 qatorni qaytarish."""

            response, _ = await generate_content_with_fallback(
                client,
                primary_model=settings.GEMINI_CALL_MODEL,
                contents=prompt,
                env_name="GEMINI_NEGOTIATION_FALLBACK_MODELS",
                log_prefix="[NEGOTIATION MISSION]",
            )
            return (response.text or "").strip()

        except Exception as exc:
            logger.warning(
                "[NEGOTIATION] Mission generation failed; using legacy mission: %s",
                exc,
            )
            return NegotiationEngine._generate_legacy_mission(assessment, role)

    @staticmethod
    def _generate_legacy_mission(assessment: NegotiationAssessment, role: str) -> str:
        if assessment.objection == "price":
            return "[1] Narx e'tirozi: Qiymatni asoslang\n[2] Keyingi savol: 'Investitsiya qaytimini ko'rsataymi?'\n[3] Xavf: Chegirma bermaslik"
        if assessment.objection == "trust":
            return "[1] Ishonch qur: Case study yuboring\n[2] Keyingi savol: 'Qaysi sohadan case ko'rsatay?'\n[3] Xavf: Munosabat sovishi"
        if role == "HUNTER":
            return "[1] Kvalifikatsiya: Ehtiyojni aniqla\n[2] Keyingi savol: 'Hozir asosiy muammoyingiz nima?'\n[3] Xavf: Vaqt yo'qotish"
        return f"[1] Progress: '{assessment.stage}' bosqichiga o'tkazing\n[2] Keyingi savol: 'Qachon boshlashni xohlaysiz?'\n[3] Xavf: Muddatlar"


# ─────────────────── Gemini Audio STT (Voice → Assessment) ──────────────────




async def transcribe_and_assess_audio(
    audio_bytes: bytes,
    mime_type: str = "audio/ogg",
    crm_status: str = "",
) -> Dict[str, Any]:
    """
    Gemini multimodal audio analysis:
    1. Transcribes the audio
    2. Immediately assesses the negotiation state
    Returns: {"transcript": str, "assessment": NegotiationAssessment}
    """
    import base64

    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY.get_secret_value())

        audio_b64 = base64.b64encode(audio_bytes).decode()

        prompt = """
Ushbu audio yozuvni transkripsiya qil (original tilda — uz/ru/en).
So'ngra FAQAT quyidagi JSON formatda qaytarish:
{
  "transcript": "...",
  "language": "uz|ru|en",
  "speaker_intent": "...",
  "key_phrases": []
}
"""
        response, _ = await generate_content_with_fallback(
            client,
            primary_model=settings.GEMINI_CALL_MODEL,
            contents=[
                {
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": audio_b64,
                    }
                },
                prompt,
            ],
            env_name="GEMINI_NEGOTIATION_FALLBACK_MODELS",
            log_prefix="[NEGOTIATION AUDIO]",
        )

        text = (response.text or "").strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        data = json.loads(text)

        transcript = data.get("transcript", "")

        # Now semantic assessment of the transcript
        assessment = await NegotiationEngine.assess_async(
            transcript,
            crm_status,
            autonomy_mode="autonomous",
        )

        return {
            "transcript": transcript,
            "language": data.get("language", "uz"),
            "key_phrases": data.get("key_phrases", []),
            "assessment": assessment,
        }

    except Exception as e:
        logger.warning("[NEGOTIATION] Audio transcription/assessment failed: %s", e)
        return {
            "transcript": "",
            "language": "uz",
            "key_phrases": [],
            "assessment": NegotiationEngine.assess("", crm_status),
            "error": str(e),
        }
