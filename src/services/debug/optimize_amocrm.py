import asyncio
import logging
from datetime import datetime, timedelta, timezone
from amocrm_sync import AmoCRMSync
from settings import settings

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# AmoCRM IDs
PIPELINES = {
    "HUNTER": 10117998,
    "CLOSER": 10123314,
    "FARMER": 10123318
}

STATUSES = {
    "NEW_LEAD": 80178218,
    "NO_CONNECTION": 81332478,
    "OFFER_SENT": 80215322,
    "CLOSED_LOST": 143
}

async def optimize_leads():
    amo = AmoCRMSync(
        subdomain=settings.AMOCRM_SUBDOMAIN,
        client_id=settings.AMOCRM_CLIENT_ID,
        client_secret=settings.AMOCRM_CLIENT_SECRET.get_secret_value() if settings.AMOCRM_CLIENT_SECRET else None,
        redirect_url=settings.AMOCRM_REDIRECT_URL
    )
    
    # 1. Fetch leads in "New Lead" (Hunter)
    new_leads = await amo.get_leads(status_id=STATUSES["NEW_LEAD"])
    now = datetime.now(timezone.utc)
    
    for lead in new_leads[:5]: # Proccess only 5 for safety initially
        created_at = datetime.fromtimestamp(lead["created_at"], timezone.utc)
        if (now - created_at) > timedelta(hours=2):
            logger.info(f"Adding task for stalled NEW LEAD: {lead['id']}")
            await amo.create_task(
                element_id=lead["id"],
                text="⚠️ TEZKOR: Bu liddan 2 soatdan beri xabar yo'q. Iltimos, bog'laning!",
                complete_till=int((now + timedelta(hours=1)).timestamp())
            )

    # 2. Fetch leads in "Tijorat taklifi yuborildi" (Closer)
    offer_leads = await amo.get_leads(status_id=STATUSES["OFFER_SENT"])
    for lead in offer_leads:
        updated_at = datetime.fromtimestamp(lead["updated_at"], timezone.utc)
        if (now - updated_at) > timedelta(days=2):
            logger.info(f"Adding follow-up task for lead: {lead['id']}")
            await amo.create_task(
                element_id=lead["id"],
                text="📅 FOLLOW-UP: Tijorat taklifi yuborilganiga 2 kun bo'ldi. Mijoz bilan bog'laning.",
                complete_till=int((now + timedelta(hours=4)).timestamp())
            )

    # 3. Handle inactive leads (> 24h since last message)
    # This would typically be handled by checking the last message timestamp in DB
    # For now, we use lead's updated_at as a proxy
    all_active_leads = await amo.get_leads()
    for lead in all_active_leads:
        updated_at = datetime.fromtimestamp(lead["updated_at"], timezone.utc)
        if (now - updated_at) > timedelta(hours=24):
            # Move to a "Paused" or "Closed/Lost" status to clean up pipeline
            # logger.info(f"Auto-closing inactive lead: {lead['id']}")
            # await amo.update_lead_status(lead['id'], STATUSES["CLOSED_LOST"])
            pass

if __name__ == "__main__":
    asyncio.run(optimize_leads())
