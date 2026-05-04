import logging
import random
import time
from typing import List, Dict, Any
from src.services.core.amocrm_sync import AmoCRMSync
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
        self.tones = ["discipline_supportive", "discipline_strict", "discipline_sarcastic", "discipline_commander"]

    async def nag_about_stagnation(self, manager_id: int, manager_name: str, stagnant_leads: List[Dict]):
        """Stagnant lidlar haqida menejerga 'nagging' xabarini yuborish."""
        if not stagnant_leads:
            return

        count = len(stagnant_leads)
        total_value = sum(l.get('price', 0) or 0 for l in stagnant_leads)
        
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
                await self.bot.send_message(manager_id, message, parse_mode='html')
                logger.info(f"[NAGGER] Sent {tone} message to {manager_name}")
            else:
                logger.info(f"[NAGGER] Generated message ({tone}): {message}")
            
            # Log the action
            await self.db.log_agent_action(manager_id, "manager_nag", {
                "tone": tone,
                "leads_count": count,
                "total_value": total_value,
                "message": message
            })
            
            return message
        except Exception as e:
            logger.error(f"[NAGGER ERROR] {e}")
            return None

    async def generate_public_shame_report(self):
        """Guruhga jamoaviy 'Wall of Shame' hisobotini yuborish."""
        # This would aggregate stats for all managers
        pass
