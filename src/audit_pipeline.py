import asyncio
import logging
import sys
from src.settings import settings
from src.database import Database
from src.services.core.amocrm_sync import AmoCRMSync
from src.services.core.airtable_sync import AirtableSync
from src.services.core.pipeline_auditor import PipelineAuditor

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("src.audit_pipeline")


async def main(limit: int = 500):
    logger.info("Initializing components for CRM 500 Intelligence Audit...")

    # 1. Database Connection
    db = Database()
    await db.init_instance()

    # 2. AmoCRM Sync
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

    # 3. Airtable Sync
    airtable = AirtableSync()

    # 4. Pipeline Auditor
    auditor = PipelineAuditor(amocrm=amocrm, airtable=airtable, db=db)

    # Execute Audit
    try:
        report = await auditor.audit_all_deals(limit=limit)
        if report.get("success"):
            logger.info(
                f"🎉 [AUDIT COMPLETE]\n"
                f"- Scanned Deals: {report.get('scanned', 0)}\n"
                f"- Master JSON Report: {report.get('json_path')}\n"
                f"- Executive Dashboard CSV: {report.get('csv_path')}"
            )
        else:
            logger.error(
                f"❌ [AUDIT BLOCKER] Audit failed or was blocked: {report.get('reason')}\n"
                f"💡 Tip: AmoCRM key and Firestore are required to scan deals!"
            )
    except Exception as e:
        logger.error(f"❌ [AUDIT FAILED] CRM Auditor crashed: {e}")
    finally:
        await db.close()


if __name__ == "__main__":
    limit_val = 500
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        limit_val = int(sys.argv[1])

    asyncio.run(main(limit=limit_val))
