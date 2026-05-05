import asyncio
import datetime
import logging
import sys

# Project imports
project_dir = r"c:\Users\baxti\.gemini\antigravity\playground\oisha-os"
sys.path.append(project_dir)

import settings
from amocrm_sync import AmoCRMSync
from database import Database
from telegram import Bot

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("re_engagement")


async def run_re_engagement():
    """Qolib ketgan leadlarga (AmoCRM) qayta murojaat qilish."""
    db = Database()
    amocrm = AmoCRMSync(
        subdomain=settings.settings.AMOCRM_SUBDOMAIN,
        client_id=settings.settings.AMOCRM_CLIENT_ID,
        client_secret=(
            settings.settings.AMOCRM_CLIENT_SECRET.get_secret_value()
            if settings.settings.AMOCRM_CLIENT_SECRET
            else None
        ),
        redirect_url=settings.settings.AMOCRM_REDIRECT_URL,
    )

    logger.info("Scanning for stagnant leads in AmoCRM...")

    leads = amocrm.get_all_leads(limit=50)
    if not leads:
        logger.info("No leads found.")
        return

    # Telegram botni yuklash
    bot = Bot(token=settings.settings.BOT_TOKEN.get_secret_value())

    now = datetime.datetime.now()
    re_engaged_count = 0

    for lead in leads:
        status_id = lead.get("status_id")
        updated_at = lead.get("updated_at")

        # Hunter Pipeline: Malakalash kutilmoqda (80178218)
        STAGNANT_STATUS_ID = 80178218
        HOURS_THRESHOLD = 24

        if status_id == STAGNANT_STATUS_ID:
            dt_updated = datetime.datetime.fromtimestamp(updated_at)
            diff = now - dt_updated

            if diff.total_seconds() > (HOURS_THRESHOLD * 3600):
                lead_id = lead.get("id")
                phone = amocrm.get_lead_phone(lead_id)

                if phone:
                    clean_phone = (
                        phone.replace("+", "").replace(" ", "").replace("-", "")
                    )
                    user_id = await db.get_user_id_by_phone(clean_phone)

                    if user_id:
                        logger.info(f"Re-engaging user {user_id} for lead {lead_id}")
                        try:
                            # Persona-based dynamic message
                            from src.services.core.persona_hub import (
                                EXTERNAL_CONCIERGE_PROMPT,
                            )

                            # We use ResearcherAgent to generate a personalized nudge
                            from src.agents.researcher_agent import ResearcherAgent

                            api_keys = {
                                "gemini": settings.settings.GEMINI_API_KEY.get_secret_value()
                            }
                            agent = ResearcherAgent(
                                "re_engager", EXTERNAL_CONCIERGE_PROMPT, api_keys
                            )

                            prompt = "Mijoz bilan muloqot 24 soatdan beri to'xtab qolgan. Uni samimiy va ekspert sifatida 're-engage' qiling. Uning loyihasi/qiziqishi bo'yicha yordam taklif qiling."
                            message = await agent.process_task(user_id, prompt)

                            await bot.send_message(chat_id=user_id, text=message)

                            # AmoCRM-da statusni yangilash (Muloqot boshlandi - 80178222)
                            await amocrm.update_lead_status(lead_id, 80178222)
                            re_engaged_count += 1
                        except Exception as e:
                            logger.error(f"Failed to send message to {user_id}: {e}")
                else:
                    logger.info(f"No phone for lead {lead_id}, skipping.")

    logger.info(f"Re-engagement process finished. Re-engaged: {re_engaged_count}")


if __name__ == "__main__":
    asyncio.run(run_re_engagement())
