import logging
import random
from typing import List, Dict
from src.services.core.crm.amocrm_sync import AmoCRMSync
from src.services.core.persona_hub import get_persona
from src.utils.ai_utils import safe_ai_call

logger = logging.getLogger("ManagerNagger")


class ManagerNagger:
    """Menejerlarni 'turtib' turish va intizomni saqlash xizmati."""

    def __init__(self, amo: AmoCRMSync, db, bot=None, ai_client=None):
        self.amo = amo
        self.db = db
        self.bot = bot
        self.ai = ai_client
        self.tones = [
            "discipline_supportive",
            "discipline_strict",
            "discipline_sarcastic",
            "discipline_commander",
        ]

    async def nag_about_stagnation(
        self, manager_id: int, manager_name: str, stagnant_leads: List[Dict]
    ):
        """Stagnant lidlar haqida menejerga 'nagging' xabarini yuborish."""
        if not stagnant_leads:
            return

        count = len(stagnant_leads)
        total_value = sum(l.get("price", 0) or 0 for l in stagnant_leads)

        # Select tone based on history or random
        # (Ideal state: we increase pressure if they ignore previous messages)
        tone = random.choice(self.tones)

        system_prompt = get_persona(is_team_member=True, task_type=tone)
        user_prompt = f"""
        Menejer {manager_name} uchun xabar yarating.
        Hozirgi holat: {count} ta lid 7 kundan beri harakatsiz.
        Umumiy qiymati: {total_value:,} so'm.
        
        Vazifa: Menejerni darhol ushbu lidlar bilan ishlashga undash.
        Xabar o'zbek tilida bo'lsin.
        """

        try:
            message = await safe_ai_call(self.ai, system_prompt, user_prompt)

            # Send to Telegram if bot is available
            if self.bot and manager_id:
                await self.bot.send_message(manager_id, message, parse_mode="html")
                logger.info(f"[NAGGER] Sent {tone} message to {manager_name}")
            else:
                logger.info(f"[NAGGER] Generated message ({tone}): {message}")

            # Log the action
            await self.db.log_agent_action(
                manager_id,
                "manager_nag",
                {
                    "tone": tone,
                    "leads_count": count,
                    "total_value": total_value,
                    "message": message,
                },
            )

            return message
        except Exception as e:
            logger.error(f"[NAGGER ERROR] {e}")
            return None

    async def generate_public_shame_report(self):
        """Guruhga jamoaviy 'Wall of Shame' hisobotini yuborish."""
        import asyncio
        import src.config as config
        
        try:
            stagnated_leads = await asyncio.to_thread(self.amo.check_stagnated_leads, hours=24)
            if not stagnated_leads:
                logger.info("[NAGGER] No stagnated leads for public shame report.")
                return None

            # 2. Group stagnated leads by manager
            manager_groups = {}
            for lead in stagnated_leads:
                mgr_id = lead.get("responsible_user_id") or 0
                if mgr_id not in manager_groups:
                    manager_groups[mgr_id] = []
                manager_groups[mgr_id].append(lead)

            # 3. Form details for prompt
            reports_detail = []
            for mgr_id, leads in manager_groups.items():
                mgr_name = self.amo.get_user_name(mgr_id) or f"User {mgr_id}"
                lead_names = ", ".join([l.get("name", "Noma'lum") for l in leads[:3]])
                if len(leads) > 3:
                    lead_names += f" va yana {len(leads) - 3} ta"
                reports_detail.append(
                    f"- {mgr_name} (ID: {mgr_id}): {len(leads)} ta stagnatsiya bitimlari ({lead_names})"
                )

            report_str = "\n".join(reports_detail)

            # 4. Generate report content using sarcastic/strict enforcer AI tone
            system_prompt = get_persona(is_team_member=True, task_type="discipline_sarcastic")
            user_prompt = f"""
            Biznes guruhga yuborish uchun 'Wall of Shame' (Qoidabuzarlar ro'yxati) hisobotini tayyorlang.
            Hozirgi holat: Quyidagi xodimlarda 24 soatdan ko'p vaqt davomida stagnatsiyada qolgan bitimlar aniqlandi:
            {report_str}

            Vazifa: Ularni qattiq, kinoyali (sarcastic) va tartibli uslubda tanqid qilib, darhol CRMda ishlashga undovchi jamoaviy xabar yarating.
            Xabar o'zbek tilida bo'lsin va Telegram HTML formatlash qoidalariga rioya qilsin.
            """

            message = await safe_ai_call(self.ai, system_prompt, user_prompt)
            if not message:
                message = f"🚨 **OISHA: TARTIB-INTIZOM NAZORATI (Wall of Shame)** 🚨\n\nQuyidagi xodimlarda qotib qolgan bitimlar aniqlandi. Darhol CRMni tozalang:\n{report_str}"

            # 5. Send to Telegram group
            group_id = getattr(config, "CRM_GROUP_ID", None) or getattr(config, "TEAM_GROUP_ID", None)
            if self.bot and group_id:
                if hasattr(self.bot, "send_message"):
                    try:
                        await self.bot.send_message(group_id, message, parse_mode="html")
                    except Exception as e:
                        logger.error(f"[NAGGER ERROR] HTML send failed, trying plain: {e}")
                        await self.bot.send_message(group_id, message)
                logger.info("[NAGGER] Sent Wall of Shame report to Telegram group.")

            # Log the action
            await self.db.log_agent_action(
                0,
                "public_shame_report",
                {
                    "leads_count": len(stagnated_leads),
                    "managers_count": len(manager_groups),
                    "message": message,
                },
            )
            return message
        except Exception as e:
            logger.error(f"[NAGGER ERROR] public shame report failed: {e}")
            return None
