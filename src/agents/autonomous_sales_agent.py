"""
Autonomous Sales Agent - Self-directed AI sales conversations
Oisha-OS Surgical Closer
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import json

from src.agents.core import BaseAgent
from src.agents.negotiation_engine import NegotiationEngine, NegotiationAssessment
from src.settings import settings


@dataclass
class ConversationState:
    """Suhbat holati"""

    user_id: str
    stage: str = "initial"  # initial, qualifying, negotiating, closing, won/lost
    context: Dict[str, Any] = field(default_factory=dict)
    history: List[Dict[str, Any]] = field(default_factory=list)
    last_interaction: datetime = field(default_factory=datetime.now)
    deal_value: Optional[float] = None
    objections: List[str] = field(default_factory=list)
    commitment_achieved: bool = False
    autonomy_level: str = "full"  # full, assisted, human_takeover

    def add_message(self, role: str, content: str, metadata: Dict = None):
        self.history.append(
            {
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata or {},
            }
        )
        self.last_interaction = datetime.now()

    def is_stale(self, hours: int = 24) -> bool:
        return datetime.now() - self.last_interaction > timedelta(hours=hours)


@dataclass
class DealProposal:
    """Taklif paketi"""

    service_type: str
    base_price: float
    scope: Dict[str, Any]
    timeline: str
    payment_terms: str
    guarantees: List[str]
    urgency_bonus: Optional[float] = None

    def total_value(self) -> float:
        total = self.base_price
        if self.urgency_bonus:
            total += self.urgency_bonus
        return total

    def to_dict(self) -> Dict:
        return {
            "service": self.service_type,
            "price": self.total_value(),
            "scope": self.scope,
            "timeline": self.timeline,
            "payment": self.payment_terms,
            "guarantees": self.guarantees,
        }


class AutonomousSalesAgent(BaseAgent):
    """
    Avtonom savdo agenti - mustaqil ravishda mijozlar bilan
    suhbatlashib, kelishuvlarga erishadi
    """

    def __init__(self, db=None):
        api_keys: Dict[str, str] = {}
        try:
            api_keys["gemini"] = settings.GEMINI_API_KEY.get_secret_value()
        except Exception:
            api_keys = {}

        super().__init__(
            agent_id="SurgicalCloser",
            system_prompt="""Siz "Oisha-OS Surgical Closer"siz - Jon.Branding agentligining
            avtonom savdo agenti. Vazifangiz:

            1. Mijoz ehtiyojlarini aniqlang (Qualification)
            2. Qiymat taklif qiling (Value Proposition)
            3. E'tirozlarni yenging (Objection Handling)
            4. Konsensusga erishing (Closing)

            Ohang: Professional, ishonchli, hos'iyatli.
            Qoidalaringiz:
            - Har doim mijoz manfaatini o'ylang
   - Narxni qiymat bilan asoslang
            - Vaqt chegaralarini hurmat qiling
            - Kimyoviy tortishish (rapport) yaratib, professional qoling
            """,
            api_keys=api_keys,
            db=db,
        )
        self.db = db
        self.conversations: Dict[str, ConversationState] = {}
        self.pricing_engine = PricingEngine()
        self.negotiation = NegotiationEngine()

    async def process_task(
        self,
        user_id: int,
        task_description: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """BaseAgent adapter: route orchestrator tasks into the sales conversation flow."""
        context = context or {}
        result = await self.handle_incoming(
            user_id=str(user_id),
            message=task_description,
            crm_data=context,
            autonomy_level=context.get("autonomy_level", "assisted"),
        )
        return str(result.get("response") or "")

    async def handle_incoming(
        self,
        user_id: str,
        message: str,
        crm_data: Dict = None,
        autonomy_level: str = "full",
    ) -> Dict[str, Any]:
        """Kiruvchi xabarni qayta ishlash"""

        # 1. Conversation state ni olish/yaratish (DB dan yoki xotiradan)
        state = await self._get_or_create_state(user_id, crm_data)
        state.add_message("user", message)
        state.autonomy_level = autonomy_level

        # 2. Tahlil qilish — semantic Gemini preferred, keyword fallback
        assessment = await NegotiationEngine.assess_async(
            message=message,
            crm_status=crm_data.get("status", "") if crm_data else "",
            autonomy_mode=autonomy_level,
            history=state.history,
        )

        # 3. Stage yangilash
        state.stage = assessment.stage
        if assessment.objection != "none":
            state.objections.append(assessment.objection)

        # 4. Avtonom qaror qabul qilish
        decision = await self._make_autonomous_decision(state, assessment, message)

        # 5. Javob yaratish
        response = await self._generate_response(state, assessment, decision, message)

        state.add_message(
            "assistant",
            response,
            {"assessment": assessment.to_payload(), "decision": decision},
        )

        # Persistently save state to DB
        await self._save_state_to_db(state)

        return {
            "response": response,
            "assessment": assessment.to_payload(),
            "state": {
                "stage": state.stage,
                "deal_value": state.deal_value,
                "autonomy_level": state.autonomy_level,
                "commitment": state.commitment_achieved,
            },
            "actions": decision.get("actions", []),
        }

    async def _make_autonomous_decision(
        self, state: ConversationState, assessment: NegotiationAssessment, message: str
    ) -> Dict[str, Any]:
        """Avtonom qaror qabul qilish mexanizmi"""

        actions = []

        # Scenario 1: Mijoz tayyor (Closing)
        if assessment.intent == "closing" and assessment.close_probability > 0.7:
            proposal = await self.pricing_engine.generate_proposal(
                context=state.context, urgency=assessment.urgency
            )
            actions.append({"type": "generate_proposal", "payload": proposal.to_dict()})
            state.deal_value = proposal.total_value()

        # Scenario 2: E'tiroz (Objection)
        elif assessment.objection != "none":
            actions.append(
                {
                    "type": "handle_objection",
                    "objection": assessment.objection,
                    "strategy": self._get_objection_strategy(assessment.objection),
                }
            )

        # Scenario 3: Narx so'rovi (Pricing)
        elif assessment.intent == "pricing":
            if state.context.get("qualified", False):
                # Range bering, aniq narx emas
                actions.append(
                    {
                        "type": "provide_range",
                        "range": self.pricing_engine.get_price_range(state.context),
                    }
                )
            else:
                actions.append(
                    {
                        "type": "qualify_before_pricing",
                        "message": "Avval ehtiyojlaringizni aniqlab olsak, to'g'ri narxni aytaman",
                    }
                )

        # Scenario 4: Uchrashuv so'rovi
        elif assessment.intent == "meeting":
            actions.append(
                {
                    "type": "schedule_meeting",
                    "priority": "high" if assessment.urgency == "high" else "normal",
                }
            )
            state.commitment_achieved = True

        # Scenario 5: Risk yuqori bo'lsa - human takeover
        if assessment.approval_needed and assessment.close_probability < 0.3:
            state.autonomy_level = "human_takeover"
            actions.append(
                {
                    "type": "escalate",
                    "reason": f"Risk: {', '.join(assessment.risk_flags)}",
                    "to": "senior_manager",
                }
            )

        return {
            "actions": actions,
            "strategy": assessment.next_action,
            "probability": assessment.close_probability,
        }

    async def _generate_response(
        self,
        state: ConversationState,
        assessment: NegotiationAssessment,
        decision: Dict,
        original_message: str,
    ) -> str:
        """AI yordamida javob yaratish"""

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=settings.GEMINI_API_KEY.get_secret_value())

            # Context tayyorlash
            context_str = json.dumps(
                {
                    "stage": state.stage,
                    "history_length": len(state.history),
                    "objections": state.objections,
                    "qualified": state.context.get("qualified", False),
                },
                ensure_ascii=False,
            )

            prompt = f"""
            Kontekst: {context_str}
            
            Mijoz xabari: {original_message}
            
            Tahlil:
            - Maqsad: {assessment.intent}
            - E'tiroz: {assessment.objection}
            - Urgency: {assessment.urgency}
            - Sentiment: {assessment.sentiment}
            - Close prob: {assessment.close_probability}
            
            Tavsiya etilgan harakat: {assessment.next_action}
            
            Javob talablari:
            1. Professional va ishonchli ohang
            2. Mijoz ehtiyojlarini ko'rsating
   3. Biror narsa taklif qiling (value)
            4. Keyingi qadamni aniq belgilang
            5. Qisqa va aniq (3-4 gap)
            
            Javob:
            """

            response = await asyncio.to_thread(
                client.models.generate_content,
                model="gemini-2.0-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.7, max_output_tokens=300
                ),
            )

            return response.text.strip()

        except Exception:
            # Fallback: rule-based response
            return self._generate_fallback_response(assessment, decision)

    def _generate_fallback_response(
        self, assessment: NegotiationAssessment, decision: Dict
    ) -> str:
        """AI ishlamaganda zaxira rejimi"""

        responses = {
            "price": "Narx bizning sifat va natijalarimizga mos keladi. Sizga investitsiya qaytimi (ROI) hisoblab ko'rsataman.",
            "trust": "Tushunaman. Sizga bizning eng so'nggi loyihalarimiz va natijalarimiz haqida gapirib beraman.",
            "timing": "Vaqt muhim. Qachon boshlash maqsad qilganingizni ayting - shunda optimal reja tuzib beraman.",
            "competition": "Boshqa variantlar ham bor. Lekin bizning farqimiz - 100% garanitialangan natija.",
            "closing": "Ajoyib! Shartnoma shartlari va to'lov tartibini ko'rib chiqamiz. Qachon boshlaymiz?",
            "meeting": "Uchrashuv belgilaymiz. Hafta davomida qachon qulay?",
            "nurture": "Albatta, o'ylab ko'ring. Men 2 kundan keyin yana bog'lanib, savollaringizga javob beraman.",
        }

        if assessment.objection != "none":
            return responses.get(assessment.objection, responses["nurture"])

        return responses.get(assessment.intent, "Sizga qanday yordam bera olaman?")

    def _get_objection_strategy(self, objection: str) -> str:
        """E'tiroz strategiyasi"""
        strategies = {
            "price": "value_anchor",
            "trust": "social_proof",
            "timing": "urgency_create",
            "competition": "differentiation",
            "legal": "risk_mitigation",
        }
        return strategies.get(objection, "explore_deeper")

    async def _get_or_create_state(
        self, user_id: str, crm_data: Dict = None
    ) -> ConversationState:
        """State olish yoki yaratish (xotira → DB → yangi)"""
        if user_id in self.conversations:
            return self.conversations[user_id]

        # DB dan yuklashga harakat qilish
        if self.db:
            try:
                raw = await self.db.get_state(f"surgical_conv_{user_id}")
                if raw:
                    data = json.loads(raw)
                    state = ConversationState(
                        user_id=user_id,
                        stage=data.get("stage", "initial"),
                        context=data.get("context", crm_data or {}),
                        history=data.get("history", []),
                        last_interaction=datetime.fromisoformat(
                            data.get("last_interaction", datetime.now().isoformat())
                        ),
                        deal_value=data.get("deal_value"),
                        objections=data.get("objections", []),
                        commitment_achieved=data.get("commitment_achieved", False),
                        autonomy_level=data.get("autonomy_level", "full"),
                    )
                    self.conversations[user_id] = state
                    return state
            except Exception:
                pass

        state = ConversationState(user_id=user_id, context=crm_data or {})
        self.conversations[user_id] = state
        return state

    async def _save_state_to_db(self, state: ConversationState):
        """State ni DB ga saqlash"""
        if not self.db:
            return
        try:
            data = {
                "stage": state.stage,
                "context": state.context,
                "history": state.history[-50:],  # Oxirgi 50 ta xabar
                "last_interaction": state.last_interaction.isoformat(),
                "deal_value": state.deal_value,
                "objections": state.objections,
                "commitment_achieved": state.commitment_achieved,
                "autonomy_level": state.autonomy_level,
            }
            await self.db.set_state(
                f"surgical_conv_{state.user_id}", json.dumps(data, ensure_ascii=False)
            )
        except Exception:
            pass

    def get_active_deals(self) -> List[Dict]:
        """Aktiv bitimlarni olish"""
        deals = []
        for user_id, state in self.conversations.items():
            if state.stage not in ["won", "lost"] and not state.is_stale(72):
                deals.append(
                    {
                        "user_id": user_id,
                        "stage": state.stage,
                        "value": state.deal_value,
                        "objections": state.objections,
                        "last_activity": state.last_interaction.isoformat(),
                        "autonomy": state.autonomy_level,
                    }
                )
        return sorted(deals, key=lambda x: x["value"] or 0, reverse=True)

    async def follow_up_stale_leads(self) -> List[Dict]:
        """Eskirgan leadlarga follow-up"""
        follow_ups = []

        for user_id, state in self.conversations.items():
            if state.is_stale(48) and state.stage not in ["won", "lost"]:
                message = await self._generate_follow_up(state)
                follow_ups.append(
                    {
                        "user_id": user_id,
                        "message": message,
                        "stage": state.stage,
                        "priority": (
                            "high"
                            if state.deal_value and state.deal_value > 5000
                            else "medium"
                        ),
                    }
                )
                state.last_interaction = datetime.now()  # Update to prevent spam

        return follow_ups

    async def _generate_follow_up(self, state: ConversationState) -> str:
        """Follow-up xabar yaratish"""
        prompts = {
            "qualified": "Sizning loyihangiz bo'yicha yangiliklar bor. Qisqa uchrashuv belgilaymizmi?",
            "negotiating": "Narx va shartlar bo'yicha sizga mos variant tayyorladim. Ko'rib chiqamizmi?",
            "meeting_ready": "Uchrashuv vaqtini tasdiqlaymiz. Qachon qulay?",
            "initial": "Sizga yuborgan ma'lumotlar yetib bordimi? Savollaringiz bormi?",
        }
        return prompts.get(state.stage, "Qanday yordam bera olaman?")


class PricingEngine:
    """Dynamic pricing engine"""

    def __init__(self):
        self.base_prices = {
            "branding": {"min": 3000, "base": 5000, "max": 15000},
            "web": {"min": 2000, "base": 4000, "max": 12000},
            "marketing": {"min": 1500, "base": 3000, "max": 8000},
            "consulting": {"min": 1000, "base": 2000, "max": 5000},
        }

    async def generate_proposal(
        self, context: Dict[str, Any], urgency: str = "normal"
    ) -> DealProposal:
        """Taklif paketi yaratish"""

        service = context.get("service_type", "branding")
        scope_size = context.get("scope", "medium")  # small, medium, large

        base = self.base_prices.get(service, self.base_prices["branding"])

        # Scope multiplier
        multipliers = {"small": 0.7, "medium": 1.0, "large": 1.5, "enterprise": 2.5}
        multiplier = multipliers.get(scope_size, 1.0)

        price = base["base"] * multiplier

        # Urgency bonus
        urgency_bonus = None
        if urgency == "high":
            urgency_bonus = price * 0.2  # 20% tezlik bonusi

        return DealProposal(
            service_type=service,
            base_price=price,
            scope={
                "size": scope_size,
                "includes": self._get_scope_includes(service, scope_size),
            },
            timeline=self._get_timeline(scope_size, urgency),
            payment_terms="50% boshlanishda, 50% tugatganda",
            guarantees=["30 kunlik bepul tuzatish", "Sifat kafolati"],
            urgency_bonus=urgency_bonus,
        )

    def get_price_range(self, context: Dict) -> Dict:
        """Narx diapazoni"""
        service = context.get("service_type", "branding")
        base = self.base_prices.get(service, self.base_prices["branding"])
        return {"min": base["min"], "max": base["max"], "typical": base["base"]}

    def _get_scope_includes(self, service: str, scope: str) -> List[str]:
        """Scope tarkibini aniqlash"""
        includes = {
            "branding": ["Logo dizayn", "Brandbook", "Guidelines"],
            "web": ["UX/UI dizayn", "Development", "SEO asoslari"],
            "marketing": ["Strategiya", "Content plan", "Ad management"],
            "consulting": ["Audit", "Strategiya", "Roadmap"],
        }
        return includes.get(service, ["Professional service"])

    def _get_timeline(self, scope: str, urgency: str) -> str:
        """Timeline aniqlash"""
        base_days = {"small": 7, "medium": 14, "large": 30, "enterprise": 60}
        days = base_days.get(scope, 14)

        if urgency == "high":
            days = int(days * 0.7)  # 30% tezroq

        return f"{days} ish kuni"


# Singleton instance
_autonomous_agent: Optional[AutonomousSalesAgent] = None


def get_autonomous_agent(db=None) -> AutonomousSalesAgent:
    """Global agent instance. Pass db on first call to enable persistence."""
    global _autonomous_agent
    if _autonomous_agent is None:
        _autonomous_agent = AutonomousSalesAgent(db=db)
    elif db is not None and _autonomous_agent.db is None:
        _autonomous_agent.db = db
    return _autonomous_agent
