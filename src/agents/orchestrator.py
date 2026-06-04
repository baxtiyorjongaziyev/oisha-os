import logging
import os
import time
from typing import Optional, Dict, Any
from src.agents.core import AgentManager
from src.services.utils.gemini_fallback import generate_content_with_fallback

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """Agentlarni boshqarish va vazifalarni yo'naltirish orkestratori."""

    def __init__(self, agent_manager: AgentManager):
        self.manager = agent_manager
        self._gemini_blocked_until = 0.0
        self._gemini_quota_cooldown_seconds = int(
            os.getenv("GEMINI_ROUTER_QUOTA_COOLDOWN_SECONDS", "300")
        )

    async def determine_intent(
        self, user_message: str, history: Optional[str] = None
    ) -> str:
        """Gemini yordamida user xabari mazmuniga qarab mos agentni tanlash."""
        # Agar PRIMARY model (Gemini) mavjud bo'lsa, undan intentni so'rash
        sales_agent = self.manager.get_agent("sales")
        if not sales_agent or not sales_agent.model_configs["gemini"]["client"]:
            return self._route_intent_fallback(user_message)
        if self._gemini_blocked_until > time.time():
            return self._route_intent_fallback(user_message)

        prompt = f"""
        Siz "JonBranding" agentligining "Dispatcher" (Router) botisiz.
        Vazifangiz - foydalanuvchi xabarini tahlil qilib, quyidagi agentlardan biriga yo'naltirish:

        SAVDO VA MIJOZ:
        1. 'sales' - Narx, xizmat, buyurtma, shartnoma, umumiy mijoz muloqoti
        2. 'brief' - Yangi loyiha uchun brief to'ldirish, loyiha ma'lumotlarini yig'ish
        3. 'welcome' - Yangi mijozni kutib olish, agentlik jarayonini tushuntirish

        LOYIHA JARAYONI:
        4. 'project_update' - Loyiha holati, progress, nima bajarildi, keyingi bosqich
        5. 'presentation' - Dizayn/brend taqdimot matni, konsepsiya tushuntirish
        6. 'ops' - Topshiriq, deadline, SOP, jamoa boshqaruvi

        KONTENT VA STRATEGIYA:
        7. 'copywriter' - Post, caption, reklama matni, SMM kontent-reja, email matn
        8. 'branding_advisor' - Brend strategiyasi, pozitsionlash, brand identity maslahat
        9. 'competitor_watch' - Raqobatchi tahlili, bozor o'rganish

        MOLIYA VA RETENTION:
        10. 'finance' - Invoice, to'lov, byudjet, moliyaviy hisobot
        11. 'feedback' - NPS, mijoz fikri, testimonial so'rash
        12. 'referral' - Referral dasturi, do'st tavsiya, chegirma taklif
        13. 'anniversary' - 1 oy/3 oy/6 oy/1 yil tabrik xabarlari
        14. 'upsell' - Keyingi xizmat taklifi, cross-sell

        NAZORAT:
        15. 'checklist' - Mijoz cheklisti ko'rish/belgilash, kechikkanlar, menejer ball/reyting

        BOSHQALAR:
        16. 'support' - FAQ, texnik yordam
        17. 'strategist' - Loyiha reja, uzoq muddatli strategiya
        18. 'researcher' - Chuqur bozor tadqiqoti, OSINT

        FOYDALANUVCHI XABARI: "{user_message}"
        SUHBAT TARIXI: {history or "Yo'q"}

        FAQAT agent_id ni qaytaring. Hech qanday qo'shimcha so'z yozmang.
        """

        try:
            client = sales_agent.model_configs["gemini"]["client"]
            model = sales_agent.model_configs["gemini"]["model"]
            response, _ = await generate_content_with_fallback(
                client,
                primary_model=model,
                contents=prompt,
                env_name="GEMINI_ROUTER_FALLBACK_MODELS",
                log_prefix="[ORCHESTRATOR]",
            )
            intent = response.text.strip().lower()
            _all_agents = {
                "sales", "support", "strategist", "researcher",
                "copywriter", "finance", "ops",
                "brief", "welcome", "project_update", "presentation",
                "feedback", "referral", "anniversary", "upsell",
                "branding_advisor", "competitor_watch", "checklist",
            }
            if intent in _all_agents:
                return intent
        except Exception as e:
            from src.services.utils.gemini_fallback import is_quota_error

            if is_quota_error(e):
                self._gemini_blocked_until = (
                    time.time() + self._gemini_quota_cooldown_seconds
                )
            logger.warning(
                "[ORCHESTRATOR] Gemini routing unavailable (%s); using fallback.",
                type(e).__name__,
            )
            
            # Fallback to Bedrock (Claude)
            if sales_agent.model_configs.get("bedrock") and sales_agent.model_configs["bedrock"]["client"]:
                try:
                    logger.info("[ORCHESTRATOR] Trying Bedrock for routing...")
                    reply = await sales_agent.call_bedrock([{"role": "user", "parts": [{"text": prompt}]}])
                    if reply:
                        intent = reply.strip().lower()
                        # Extract intent if Claude adds fluff
                        for possible in [
                            "sales", "support", "strategist", "researcher",
                            "copywriter", "finance", "ops", "brief", "welcome",
                            "project_update", "presentation", "feedback",
                            "referral", "anniversary", "upsell",
                            "branding_advisor", "competitor_watch", "checklist",
                        ]:
                            if possible in intent:
                                return possible
                except Exception as b_err:
                    logger.error(f"[ORCHESTRATOR] Bedrock routing error: {b_err}")

        return self._route_intent_fallback(user_message)

    def _route_intent_fallback(self, user_message: str) -> str:
        """Zaxira (fallback) keyword-based routing."""
        msg = user_message.lower()
        if any(w in msg for w in ["cheklisti", "checklist", "bajarildi", "overdue", "kechikkan", "menejer ball", "reyting"]):
            return "checklist"
        if any(w in msg for w in ["brief", "loyiha ma'lumot", "nima yarattirasiz", "yangi loyiha"]):
            return "brief"
        if any(w in msg for w in ["xush kelibsiz", "yangi mijoz", "onboarding", "birinchi marta"]):
            return "welcome"
        if any(w in msg for w in ["loyiha holat", "progress", "nima bajarildi", "qayerda"]):
            return "project_update"
        if any(w in msg for w in ["taqdimot", "presentation", "tushuntir", "konsepsiya"]):
            return "presentation"
        if any(w in msg for w in ["fikr", "baho", "nps", "testimonial", "mamnun", "rizo"]):
            return "feedback"
        if any(w in msg for w in ["referral", "do'st", "tavsiya", "yo'naltir"]):
            return "referral"
        if any(w in msg for w in ["1 oy", "6 oy", "1 yil", "bayram", "yillik", "sana"]):
            return "anniversary"
        if any(w in msg for w in ["keyingi xizmat", "yana nima", "qo'shimcha", "upsell", "brendbuk"]):
            return "upsell"
        if any(w in msg for w in ["brend strategiya", "pozitsion", "brand identity", "brend maslahat"]):
            return "branding_advisor"
        if any(w in msg for w in ["raqobatchi", "competitor", "bozor o'rgan", "raqobat tahlil"]):
            return "competitor_watch"
        if any(w in msg for w in ["post yoz", "caption", "reklama matn", "hook", "smm", "kontent", "instagram", "reels"]):
            return "copywriter"
        if any(w in msg for w in ["invoice", "hisob-faktura", "to'lov", "qarz", "byudjet", "daromad", "xarajat"]):
            return "finance"
        if any(w in msg for w in ["topshiriq", "deadline", "sop", "mas'ul", "vazifa", "ish tartibi"]):
            return "ops"
        if any(w in msg for w in ["narx", "qancha", "buyurtma", "xizmat"]):
            return "sales"
        if any(w in msg for w in ["reja", "strategiya", "loyiha", "holat"]):
            return "strategist"
        if any(w in msg for w in ["tadqiqot", "tahlil", "bozor", "osint"]):
            return "researcher"
        return "sales"

    async def get_agent_response(
        self,
        agent_id: str,
        user_id: int,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Belgilangan agent orqali javob olish."""
        agent = self.manager.get_agent(agent_id)
        if not agent:
            agent = self.manager.get_agent("sales")  # Fallback

        response = await agent.process_task(user_id, message, context=context)

        # Orqa fonda (background) xulosa qilish kerakligini tekshirish
        import asyncio

        asyncio.create_task(agent.check_and_summarize(user_id))

        return response
