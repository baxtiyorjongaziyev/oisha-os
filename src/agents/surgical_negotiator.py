"""
Surgical Negotiator - Main orchestrator for autonomous negotiations
Oisha-OS Ideal AI Agent
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from src.agents.autonomous_sales_agent import (
    AutonomousSalesAgent, 
    ConversationState,
    get_autonomous_agent
)
from src.agents.deal_lifecycle_manager import (
    DealLifecycleManager,
    DealStage,
    DealPriority,
    get_lifecycle_manager
)
from src.agents.negotiation_engine import NegotiationEngine, NegotiationAssessment
from src.agents.contract_generator import ContractGenerator, RiskAssessor
from src.services.core.gcontacts import GoogleContactsSync


class SurgicalNegotiator:
    """
    Asosiy negotiator - barcha komponentlarni muvofiqlashtiruvchi
    
    Vazifalari:
    1. Kiruvchi leadlarni qabul qilish va tahlil qilish
    2. Avtonom suhbatlarni boshqarish
    3. Bitim lifecycle'ni kuzatish
    4. Shartnomalarni yaratish
    5. Risklarni baholash
    6. CRM bilan sinxronlash
    """
    
    def __init__(self):
        self.sales_agent = get_autonomous_agent()
        self.lifecycle = get_lifecycle_manager()
        self.contract_gen = ContractGenerator()
        self.risk_assessor = RiskAssessor()
        self.gcontacts = GoogleContactsSync()
        
        # Register lifecycle handlers
        self._register_handlers()
        
        # Active negotiations
        self.active_sessions: Dict[str, Dict] = {}
    
    def _register_handlers(self):
        """Lifecycle handler'larni ro'yxatdan o'tkazish"""
        
        # When deal reaches PROPOSAL stage
        self.lifecycle.register_stage_handler(
            DealStage.PROPOSAL,
            self._on_proposal_stage
        )
        
        # When deal reaches COMMITMENT stage  
        self.lifecycle.register_stage_handler(
            DealStage.COMMITMENT,
            self._on_commitment_stage
        )
        
        # When deal is WON
        self.lifecycle.register_stage_handler(
            DealStage.CLOSED_WON,
            self._on_deal_won
        )
    
    async def handle_lead(
        self,
        user_id: str,
        message: str,
        user_info: Dict[str, Any] = None,
        source: str = "telegram"
    ) -> Dict[str, Any]:
        """
        Yangi leadni qayta ishlash - asosiy kirish nuqtasi
        
        Bu metod:
        1. Avtonom sales agent orqali javob yaratadi
        2. Deal lifecycle'ni yangilaydi
        3. CRMga saqlaydi
        4. Risklarni baholaydi
        """
        
        # 1. Get or create deal
        deal = self.lifecycle.get_deal_by_user(user_id)
        
        if not deal:
            # New lead - create deal
            deal = self.lifecycle.create_deal(
                user_id=user_id,
                service_type=user_info.get("interest", "") if user_info else "",
                source=source
            )
            
            # Save to Google Contacts
            if user_info:
                await self._save_to_contacts(user_info)
        
        # 2. Get CRM data if available
        crm_data = await self._get_crm_data(user_id)
        
        # 3. Determine autonomy level based on risk
        autonomy_level = self._determine_autonomy(deal, message)
        
        # 4. Process through autonomous agent
        result = await self.sales_agent.handle_incoming(
            user_id=user_id,
            message=message,
            crm_data=crm_data,
            autonomy_level=autonomy_level
        )
        
        # 5. Update deal based on assessment
        assessment = result.get("assessment", {})
        await self._update_deal_from_assessment(deal, assessment)
        
        # 6. Save to CRM
        await self._save_to_crm(user_id, result, deal)
        
        # 7. Check if contract needed
        if deal.stage == DealStage.COMMITMENT:
            contract = await self._generate_contract_if_needed(deal, user_info)
            result["contract"] = contract
        
        return {
            "response": result["response"],
            "deal_id": deal.id,
            "stage": deal.stage.value,
            "assessment": assessment,
            "actions": result.get("actions", []),
            "contract": result.get("contract"),
            "requires_approval": assessment.get("approval_needed", False)
        }
    
    async def _update_deal_from_assessment(
        self, 
        deal: Any, 
        assessment: Dict
    ):
        """Tahlil asosida deal'ni yangilash"""
        
        intent = assessment.get("intent", "")
        stage = assessment.get("stage", "new_lead")
        
        # Map to deal stages
        stage_mapping = {
            "new_lead": DealStage.NEW,
            "qualified": DealStage.QUALIFIED,
            "meeting_ready": DealStage.NEGOTIATION,
            "closing": DealStage.COMMITMENT
        }
        
        new_stage = stage_mapping.get(stage, deal.stage)
        
        # Only advance, never go back
        if self._is_stage_advanced(deal.stage, new_stage):
            self.lifecycle.advance_stage(
                deal.id,
                new_stage,
                reason=f"AI assessment: {intent}"
            )
        
        # Update priority based on urgency
        urgency = assessment.get("urgency", "normal")
        if urgency == "high":
            deal.priority = DealPriority.HOT
        elif urgency == "low":
            deal.priority = DealPriority.COLD
        
        # Update value if mentioned
        prob = assessment.get("close_probability", 0)
        if prob > 0.7 and not deal.value:
            # Likely to close, try to get value from context
            pass
    
    def _is_stage_advanced(self, current: DealStage, proposed: DealStage) -> bool:
        """Tekshirish - yangi bosqich oldingidan keyinmi"""
        order = [
            DealStage.NEW,
            DealStage.QUALIFIED,
            DealStage.PROPOSAL,
            DealStage.NEGOTIATION,
            DealStage.COMMITMENT,
            DealStage.CLOSED_WON
        ]
        
        try:
            current_idx = order.index(current)
            proposed_idx = order.index(proposed)
            return proposed_idx > current_idx
        except ValueError:
            return False
    
    def _determine_autonomy(self, deal: Any, message: str) -> str:
        """Avtonomiya darajasini aniqlash"""
        
        # Check deal value
        if deal.value and deal.value > 15000:
            return "assisted"  # High value needs oversight
        
        # Check for risky keywords
        risky_words = ["shartnoma", "yuridik", "advokat", "sud", "talabnoma"]
        if any(word in message.lower() for word in risky_words):
            return "human_takeover"
        
        # Check stage
        if deal.stage in [DealStage.COMMITMENT, DealStage.NEGOTIATION]:
            return "assisted"
        
        return "full"
    
    async def _on_proposal_stage(self, deal: Any, old_stage: Optional[DealStage] = None):
        """PROPOSAL bosqichiga o'tganda"""
        
        # Generate proposal automatically if not exists
        if not deal.value:
            pricing = await self.sales_agent.pricing_engine.generate_proposal(
                context={"service_type": deal.service_type or "branding"},
                urgency="normal"
            )
            deal.value = pricing.total_value()
        
        # Notify user
        print(f"[SURGICAL] Deal {deal.id} moved to PROPOSAL. Value: ${deal.value}")
    
    async def _on_commitment_stage(self, deal: Any, old_stage: Optional[DealStage] = None):
        """COMMITMENT bosqichiga o'tganda"""
        
        # Risk assessment
        risk = self.risk_assessor.assess_deal_risk(
            deal_value=deal.value or 0,
            client_history={},  # Would come from CRM
            negotiation_flags=[],
            service_complexity="medium"
        )
        
        if risk["requires_approval"]:
            deal.notes.append(f"[{datetime.now().isoformat()}] APPROVAL REQUIRED")
            deal.notes.extend(risk["recommendations"])
        else:
            # Auto-generate contract
            deal.notes.append(f"[{datetime.now().isoformat()}] Contract auto-generated")
    
    async def _on_deal_won(self, deal: Any, old_stage: Optional[DealStage] = None):
        """Bitim yutganda"""
        
        # Create task for fulfillment
        deal.tasks.append({
            "type": "fulfillment",
            "description": f"Start {deal.service_type} project",
            "due": (datetime.now() + timedelta(days=1)).isoformat(),
            "status": "pending"
        })
        
        # Send to project management
        print(f"[SURGICAL] DEAL WON! {deal.id} - ${deal.value}")
    
    async def _generate_contract_if_needed(
        self, 
        deal: Any, 
        user_info: Dict
    ) -> Optional[Dict]:
        """Kerak bo'lsa shartnoma yaratish"""
        
        if not deal.value:
            return None
        
        # Risk assessment
        risk = self.risk_assessor.assess_deal_risk(
            deal_value=deal.value,
            client_history={},
            negotiation_flags=deal.notes
        )
        
        # Generate contract
        contract = self.contract_gen.generate_contract(
            service_type=deal.service_type or "branding",
            client_data=user_info or {},
            deal_data={
                "value": deal.value,
                "scope": deal.context.get("scope", []),
                "timeline_days": 14,
                "guarantees": ["30 kunlik bepul tuzatish", "Sifat kafolati"]
            }
        )
        
        contract["risk_assessment"] = risk
        
        return contract
    
    async def _save_to_contacts(self, user_info: Dict):
        """Google Contacts'ga saqlash"""
        try:
            self.gcontacts.create_contact(
                first_name=user_info.get("first_name", ""),
                last_name=user_info.get("last_name", ""),
                phones=[user_info.get("phone")] if user_info.get("phone") else [],
                note=f"Source: {user_info.get('source', 'Oisha-OS')}",
                group_name="Oisha Leads"
            )
        except Exception as e:
            print(f"[SURGICAL] Contact save error: {e}")
    
    async def _get_crm_data(self, user_id: str) -> Dict:
        """CRM'dan ma'lumot olish"""
        # This would integrate with AmoCRM
        return {}
    
    async def _save_to_crm(self, user_id: str, result: Dict, deal: Any):
        """CRM'ga saqlash"""
        # This would push to AmoCRM
        pass
    
    async def run_daily_cycle(self) -> Dict[str, Any]:
        """Kunlik avtomatlashtirish tsikli"""
        
        results = {
            "follow_ups_sent": [],
            "deals_advanced": [],
            "contracts_generated": [],
            "pipeline_stats": {}
        }
        
        # 1. Stale leads'ga follow-up
        follow_ups = await self.sales_agent.follow_up_stale_leads()
        results["follow_ups_sent"] = follow_ups
        
        # 2. Automation rules
        actions = await self.lifecycle.run_automation_cycle()
        results["automation_actions"] = actions
        
        # 3. Pipeline stats
        results["pipeline_stats"] = self.lifecycle.get_pipeline_stats()
        
        # 4. Overdue deals
        overdue = self.lifecycle.get_overdue_deals()
        results["overdue_count"] = len(overdue)
        
        return results
    
    def get_dashboard(self) -> Dict[str, Any]:
        """Real-time dashboard ma'lumotlari"""
        
        stats = self.lifecycle.get_pipeline_stats()
        active_deals = self.sales_agent.get_active_deals()
        
        return {
            "summary": stats,
            "active_negotiations": active_deals[:10],  # Top 10
            "requires_attention": [
                d for d in active_deals 
                if d.get("autonomy") == "human_takeover"
            ],
            "hot_deals_today": [
                d for d in active_deals
                if d.get("priority") == "high"
            ],
            "autonomy_stats": {
                "full": len([d for d in active_deals if d.get("autonomy") == "full"]),
                "assisted": len([d for d in active_deals if d.get("autonomy") == "assisted"]),
                "human": len([d for d in active_deals if d.get("autonomy") == "human_takeover"])
            }
        }


# Singleton
_surgical_negotiator: Optional[SurgicalNegotiator] = None


def get_surgical_negotiator() -> SurgicalNegotiator:
    """Global negotiator instance"""
    global _surgical_negotiator
    if _surgical_negotiator is None:
        _surgical_negotiator = SurgicalNegotiator()
    return _surgical_negotiator


# Convenience function for quick use
async def negotiate(
    user_id: str,
    message: str,
    user_info: Dict = None
) -> Dict[str, Any]:
    """Tezkor negotiator chaqiruvi"""
    negotiator = get_surgical_negotiator()
    return await negotiator.handle_lead(user_id, message, user_info)
