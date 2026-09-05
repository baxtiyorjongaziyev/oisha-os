"""Daily Analytics Reporter using GA4 and Gemini."""
import asyncio
import json
import logging

try:
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.analytics.data_v1beta.types import (
        DateRange,
        Dimension,
        Metric,
        RunReportRequest,
    )
except ImportError:
    BetaAnalyticsDataClient = None
    DateRange = None
    Dimension = None
    Metric = None
    RunReportRequest = None

from src.settings import settings
from src.services.core.agent_brain import OishaBrain

logger = logging.getLogger(__name__)

async def run_daily_analytics_report(bot_client=None):
    """Fetches GA4 data, analyzes with Gemini, and sends to Telegram."""
    ga_property_id = getattr(settings, "GA4_PROPERTY_ID", None)
    ga_creds_json = getattr(settings, "GA4_CREDENTIALS_JSON", None)
    admin_chat_id = getattr(settings, "TELEGRAM_ADMIN_CHAT_ID", None)

    if not ga_property_id or not ga_creds_json or not admin_chat_id or bot_client is None:
        logger.debug("[GA4] Configuration or bot client missing. Skipping daily analytics.")
        return

    if BetaAnalyticsDataClient is None:
        logger.warning("[GA4] google-analytics-data is not installed. Skipping daily analytics.")
        return

    try:
        creds_dict = json.loads(ga_creds_json)
        client = BetaAnalyticsDataClient.from_service_account_info(creds_dict)

        # Run report for yesterday
        request = RunReportRequest(
            property=f"properties/{ga_property_id}",
            dimensions=[
                Dimension(name="deviceCategory"),
                Dimension(name="sessionSource"),
            ],
            metrics=[
                Metric(name="activeUsers"),
                Metric(name="screenPageViews"),
                Metric(name="sessions")
            ],
            date_ranges=[DateRange(start_date="yesterday", end_date="yesterday")],
        )
        response = client.run_report(request)

        # Format raw data for AI
        raw_data = "Kechagi kun bo'yicha vebsayt statistikasi (GA4):\n"
        total_users = 0
        total_views = 0
        
        for row in response.rows:
            device = row.dimension_values[0].value
            source = row.dimension_values[1].value
            users = int(row.metric_values[0].value)
            views = int(row.metric_values[1].value)
            
            total_users += users
            total_views += views
            raw_data += f"- Manba: {source}, Qurilma: {device} -> Foydalanuvchilar: {users}, Ko'rishlar: {views}\n"
            
        raw_data += f"\nUmumiy aktiv foydalanuvchilar: {total_users}\nUmumiy sahifa ko'rishlar: {total_views}"

        # Analyze with OishaBrain
        brain = OishaBrain()
        prompt = (
            f"Siz Oisha - Jon Branding agentligining AI tahlilchisisiz.\n"
            f"Quyida kechagi kunning Google Analytics (GA4) ma'lumotlari berilgan.\n"
            f"Shu ma'lumotlarni o'rganib, rahbarlarga qisqa, tushunarli va chiroyli telegram xabar tayyorlang. "
            f"Xabarda nimalar yaxshi ishlagani, ko'proq qaysi qurilma va manbadan odam kelgani hamda xulosangizni yozing.\n\n"
            f"{raw_data}"
        )
        
        analysis = await brain.generate_response(prompt)
        
        # Send to Telegram
        await bot_client.send_message(
            admin_chat_id,
            f"📊 <b>Kunlik Vebsayt Analitikasi</b>\n\n{analysis}",
            parse_mode="HTML",
        )
        logger.info("[GA4] Daily analytics report sent successfully.")

    except Exception as e:
        logger.error(f"[GA4] Error generating daily analytics report: {e}")


async def daily_analytics_loop(bot_client=None) -> None:
    """Daily 09:00 automated GA4 analytics broadcast loop."""
    from src.time_utils import get_local_now

    await asyncio.sleep(60)
    while True:
        try:
            now = get_local_now()
            if now.hour == 9 and now.minute == 0:
                logger.info("[GA4] Triggering daily analytics report...")
                await run_daily_analytics_report(bot_client=bot_client)
                await asyncio.sleep(61)
        except Exception as e:
            logger.error("[GA4] Error in daily analytics loop: %s", e)
        await asyncio.sleep(30)
