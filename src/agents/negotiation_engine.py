"""
NegotiationEngine — Semantic AI-powered assessment + surgical mission generation.
Replaces pure keyword matching with Gemini semantic understanding.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

import logging

from google import genai

from src.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class NegotiationAssessment:
    stage: str
    intent: str
    objection: str
    urgency: str
    sentiment: str
    close_probability: float
    autonomy_mode: str
    recommended_status: str
    next_action: str
    approval_needed: bool
    risk_flags: List[str] = field(default_factory=list)
    # Semantic extras
    pain_points: List[str] = field(default_factory=list)
    buying_signals: List[str] = field(default_factory=list)
    decision_factors: List[str] = field(default_factory=list)
    autonomous_mission: str = ""

    def to_payload(self) -> Dict[str, Any]:
        return asdict(self)


class NegotiationEngine:
    """
    Two-mode assessment:
    1. assess()         — fast synchronous keyword-based (fallback / no Gemini)
    2. assess_async()   — Gemini semantic analysis (preferred, requires API key)
    """

    # ─────────────────────────── ASYNC SEMANTIC ───────────────────────────

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
            if context and "latest_call_analysis" in context:
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

            response = await client.aio.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
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

        except Exception as _exc:
            logger.warning("[NegotiationEngine] assess_async failed: %r — keyword fallback", _exc)
            return NegotiationEngine.assess(
                message,
                crm_status,
                autonomy_mode=autonomy_mode,
                history=history,
                context=context,
            )

    # ─────────────────────────── SYNC KEYWORD ────────────────────────────

    @staticmethod
    def assess(
        message: str,
        crm_status: str = "",
        *,
        autonomy_mode: str = "autonomous",
        history: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> NegotiationAssessment:
        """Fast keyword-based fallback. Still reliable for common patterns."""
        del history, context

        msg = (message or "").lower()
        crm = (crm_status or "").lower()
        risk_flags: List[str] = []

        # ── Objection detection ──
        objection = "none"
        if any(
            w in msg
            for w in ["qimmat", "narx", "chegirma", "discount", "budget", "arzon"]
        ):
            objection = "price"
            risk_flags.append("price_pressure")
        elif any(
            w in msg
            for w in ["portfolio", "ishlar", "case", "garant", "ishonch", "tajriba"]
        ):
            objection = "trust"
        elif any(
            w in msg for w in ["keyin", "vaqt", "hozir emas", "kechroq", "keyinroq"]
        ):
            objection = "timing"
        elif any(
            w in msg for w in ["raqobatchi", "boshqa agentlik", "arzonroq", "taqqos"]
        ):
            objection = "competition"
            risk_flags.append("competitive_pressure")
        elif any(
            w in msg
            for w in ["shartnoma", "nda", "akt", "kpi", "yuridik", "legal", "advokat"]
        ):
            objection = "legal"
            risk_flags.append("legal_review")
        elif any(w in msg for w in ["byudjet", "mablag", "pul yo'q", "moliya"]):
            objection = "budget"
            risk_flags.append("budget_constraint")
        elif any(
            w in msg for w in ["rahbar", "direktor", "boshiq", "ruxsat", "kelishuv"]
        ):
            objection = "authority"
            risk_flags.append("authority_gate")

        # ── Sentiment ──
        if any(
            w in msg
            for w in ["jahlim", "yomon", "norozi", "muammo", "ishonmayman", "aldov"]
        ):
            sentiment = "negative"
            risk_flags.append("negative_sentiment")
        elif any(
            w in msg for w in ["zo'r", "yoqdi", "qiziq", "maqul", "ajoyib", "yaxshi"]
        ):
            sentiment = "positive"
        elif any(w in msg for w in ["tushunmadim", "aniqla", "nima", "qanday"]):
            sentiment = "confused"
        else:
            sentiment = "neutral"

        # ── Urgency ──
        urgency = "normal"
        if any(
            w in msg
            for w in ["tez", "bugun", "ertaga", "shoshilinch", "deadline", "zudlik"]
        ):
            urgency = "high"
        elif any(w in msg for w in ["keyinroq", "vaqt bor", "shoshilmaymiz", "asta"]):
            urgency = "low"

        # ── Intent ──
        intent = "qualify"
        if any(w in msg for w in ["narx", "qancha", "budget", "chegirma", "to'lov"]):
            intent = "pricing"
        elif any(
            w in msg
            for w in ["uchrashuv", "qo'ng'iroq", "call", "zoom", "meeting", "uchrash"]
        ):
            intent = "meeting"
        elif any(
            w in msg
            for w in [
                "tayyor",
                "boshlaymiz",
                "start",
                "to'laymiz",
                "shartnoma",
                "kelishdik",
            ]
        ):
            intent = "closing"
        elif any(
            w in msg
            for w in ["portfolio", "case", "misol", "ishlaringiz", "ko'rsating"]
        ):
            intent = "proof"
        elif any(
            w in msg for w in ["keyin", "o'ylab", "o'ylab ko'raman", "bayon qilaman"]
        ):
            intent = "nurture"
        elif any(
            w in msg for w in ["xato", "shikoyat", "norozi", "muammo", "noto'g'ri"]
        ):
            intent = "complaint"

        # ── Stage ──
        stage = "new_lead"
        if "meeting" in crm or intent == "meeting":
            stage = "meeting_ready"
        elif (
            "qualified" in crm or "interested" in crm or intent in {"pricing", "proof"}
        ):
            stage = "qualified"
        elif "won" in crm or "success" in crm or intent == "closing":
            stage = "closing"

        status_map = {
            "new_lead": "Initial Contact",
            "qualified": "Interested",
            "meeting_ready": "Meeting Scheduled",
            "closing": "Negotiating",
        }

        next_action_map = {
            "pricing": "value_anchor",
            "proof": "show_relevant_case",
            "meeting": "schedule_strategy_session",
            "closing": "confirm_scope_and_close",
            "nurture": "create_followup_commitment",
            "complaint": "escalate_to_senior",
        }

        # ── Probability ──
        prob = 0.3
        if stage == "qualified":
            prob += 0.15
        if stage == "meeting_ready":
            prob += 0.25
        if intent == "closing":
            prob += 0.20
        if sentiment == "positive":
            prob += 0.10
        if objection in {"price", "competition", "legal"}:
            prob -= 0.15
        if "negative_sentiment" in risk_flags:
            prob -= 0.20
        if urgency == "high":
            prob += 0.10
        prob = max(0.05, min(0.95, prob))

        approval_needed = any(
            f in risk_flags
            for f in [
                "legal_review",
                "competitive_pressure",
                "negative_sentiment",
                "budget_constraint",
            ]
        )
        if objection == "price" and any(w in msg for w in ["chegirma", "discount"]):
            approval_needed = True
            risk_flags.append("discount_request")

        # ── Buying signals ──
        buying_signals = []
        if any(w in msg for w in ["qachon", "qancha vaqt", "boshlash", "shartlar"]):
            buying_signals.append("timeline_inquiry")
        if any(w in msg for w in ["to'lash", "hisob", "invoice", "to'lov"]):
            buying_signals.append("payment_inquiry")

        return NegotiationAssessment(
            stage=stage,
            intent=intent,
            objection=objection,
            urgency=urgency,
            sentiment=sentiment,
            close_probability=round(prob, 2),
            autonomy_mode=autonomy_mode,
            recommended_status=status_map.get(stage, "Initial Contact"),
            next_action=next_action_map.get(intent, "qualify_need"),
            approval_needed=approval_needed,
            risk_flags=risk_flags,
            buying_signals=buying_signals,
        )

    # ─────────────────────── SURGICAL MISSION ────────────────────────────

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

            response = await client.aio.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
            )
            return (response.text or "").strip()

        except Exception:
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
        response = await client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                {
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": audio_b64,
                    }
                },
                prompt,
            ],
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
        return {
            "transcript": "",
            "language": "uz",
            "key_phrases": [],
            "assessment": NegotiationEngine.assess("", crm_status),
            "error": str(e),
        }
