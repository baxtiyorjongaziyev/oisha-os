"""
Sales Analytics core service class.
"""
from __future__ import annotations

import re
import structlog
from src.services.core.crm.amocrm_pipeline_config import SALES_PIPELINE_ID
from src.services.core.sales_analytics.scorecard import ManagerScorecardMixin
from src.services.core.sales_analytics.stagnation import StagnationAlertMixin
from src.services.core.sales_analytics.funnel import PipelineFunnelMixin

logger = structlog.get_logger()


class SalesAnalytics(
    ManagerScorecardMixin,
    StagnationAlertMixin,
    PipelineFunnelMixin,
):
    """AmoCRM sotuvlar tahlili — KPI, Stagnatsiya, Pipeline Funnel."""

    SALES_PIPELINE = SALES_PIPELINE_ID
    HUNTER_PIPELINE = SALES_PIPELINE_ID
    CLOSER_PIPELINE = SALES_PIPELINE_ID

    STATUS_WON = 142
    STATUS_LOST = 143

    def __init__(self, amocrm_sync=None, db=None, bot=None):
        if amocrm_sync is None:
            from src.services.core.crm.amocrm_sync import AmoCRMSync
            from src.settings import settings

            self.amo = AmoCRMSync(
                settings.AMOCRM_SUBDOMAIN,
                settings.AMOCRM_CLIENT_ID,
                (
                    settings.AMOCRM_CLIENT_SECRET.get_secret_value()
                    if settings.AMOCRM_CLIENT_SECRET
                    else None
                ),
                settings.AMOCRM_REDIRECT_URL,
            )
            self.amo._load_token()
        else:
            self.amo = amocrm_sync

        self.db = db
        self.bot = bot

    async def send_scorecard(self, chat_id: int, thread_id: int = None):
        report = self.generate_manager_scorecard()
        await self._send_report(chat_id, report, thread_id)

    async def send_stagnation_alert(self, chat_id: int, thread_id: int = None):
        report = self.generate_stagnation_alert()
        if report:
            await self._send_report(chat_id, report, thread_id)

    async def send_funnel_report(self, chat_id: int, thread_id: int = None):
        report = self.generate_pipeline_funnel()
        await self._send_report(chat_id, report, thread_id)

    async def _send_report(self, chat_id: int, text: str, thread_id: int = None):
        if not self.bot or not text:
            return
        from src.services.core.tool_adapters import send_group_message_with_fallback

        try:
            await send_group_message_with_fallback(
                self.bot,
                chat_id=chat_id,
                text=text,
                parse_mode="HTML",
                thread_id=thread_id,
                allow_userbot_fallback=True,
            )
        except Exception as e:
            logger.warning(f"[ANALYTICS] HTML xato, plain text-ga o'tildi: {e}")
            clean = re.sub(r"<[^>]+>", "", text)
            await send_group_message_with_fallback(
                self.bot,
                chat_id=chat_id,
                text=clean,
                thread_id=thread_id,
                allow_userbot_fallback=True,
            )

SalesAnalyticsService = SalesAnalytics
