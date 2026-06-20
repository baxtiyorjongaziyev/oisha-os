"""
analyze_calls.py — Legacy entry point (use run_call_analysis_pipeline.py for full pipeline).
"""
import asyncio
import logging
import sys

from src.settings import settings
from src.database import Database
from src.services.core.amocrm_sync import AmoCRMSync
from src.services.core.call_analyzer import CallAnalyzer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("src.analyze_calls")


async def main(limit: int = 15):
    logger.info("Initializing components for AmoCRM call recordings audit...")

    db = Database()
    await db.init_instance()

    amocrm = AmoCRMSync(
        subdomain=settings.AMOCRM_SUBDOMAIN,
        client_id=settings.AMOCRM_CLIENT_ID,
        client_secret=(
            settings.AMOCRM_CLIENT_SECRET.get_secret_value()
            if settings.AMOCRM_CLIENT_SECRET
            else ""
        ),
        redirect_url=settings.AMOCRM_REDIRECT_URL,
    )

    # CallAnalyzer now handles everything inline (no VoiceProcessor needed)
    analyzer = CallAnalyzer(amocrm=amocrm, db=db)

    try:
        stats = await analyzer.analyze_recent_calls(limit=limit)
        logger.info(
            f"🎉 [AUDIT COMPLETE]\n"
            f"- Scanned Leads/Deals: {stats.get('leads_scanned', 0)}\n"
            f"- Transcribed & Categorized Recordings: {stats.get('calls_processed', 0)}"
        )
    except Exception as e:
        logger.error(f"❌ [AUDIT FAILED] Call recordings analyzer crashed: {e}")
    finally:
        await db.close()


if __name__ == "__main__":
    limit_val = 15
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        limit_val = int(sys.argv[1])

    asyncio.run(main(limit=limit_val))
