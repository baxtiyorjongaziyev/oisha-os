"""Uzbek Entrepreneurs Main Handler - Orchestrates the full system."""
from __future__ import annotations

import logging
from typing import Optional

from src.context import app_ctx
from src.services.core.uzbek_voice_agent import UzbekVoiceAgent, get_vapi_config
from src.services.core.uzbek_call_queue import CallQueueManager
from src.services.core.uzbek_integrations import UzbekEntrepreneurIntegrator
from src.services.core.uzbek_entrepreneurs_scraper import run_scraping_campaign

logger = logging.getLogger(__name__)


class UzbekEntrepreneursHandler:
    """Main handler for Uzbek Entrepreneurs system."""

    def __init__(self):
        self.voice_agent: Optional[UzbekVoiceAgent] = None
        self.call_queue: Optional[CallQueueManager] = None
        self.integrator: Optional[UzbekEntrepreneurIntegrator] = None
        self._initialized = False

    async def initialize(self) -> bool:
        """Initialize all components."""
        if self._initialized:
            return True

        try:
            # Initialize Voice Agent
            vapi_config = get_vapi_config()
            if vapi_config:
                self.voice_agent = UzbekVoiceAgent(vapi_config)
                logger.info("[UZBEK_HANDLER] Voice Agent initialized")

            # Initialize Call Queue Manager
            self.call_queue = CallQueueManager()
            logger.info("[UZBEK_HANDLER] Call Queue Manager initialized")

            # Initialize Integrator
            if app_ctx.msg_controller and app_ctx.msg_controller.crm:
                self.integrator = UzbekEntrepreneurIntegrator(
                    amocrm_client=app_ctx.msg_controller.crm.amocrm,
                    telegram_client=app_ctx.client,
                )
                logger.info("[UZBEK_HANDLER] Integrator initialized")

            self._initialized = True
            logger.info("[UZBEK_HANDLER] System initialized successfully")
            return True

        except Exception as e:
            logger.error("[UZBEK_HANDLER] Initialization failed: %s", e)
            return False

    async def run_scraping_campaign(
        self,
        sources: list[str] = ["linkedin", "instagram", "telegram"],
        keywords: list[str] = ["uzbek entrepreneur", "ceo", "founder"],
        countries: list[str] = ["US", "UK", "Germany", "Turkey", "Russia"],
    ) -> dict:
        """Run scraping campaign to find Uzbek entrepreneurs."""
        logger.info("[UZBEK_HANDLER] Starting scraping campaign")

        results = await run_scraping_campaign(sources, keywords, countries)

        logger.info("[UZBEK_HANDLER] Scraping campaign completed: %s", results)
        return results

    async def run_call_campaign(self, limit: int = 10) -> dict:
        """Run automated call campaign using Voice Agent."""
        if not self.voice_agent:
            logger.error("[UZBEK_HANDLER] Voice Agent not initialized")
            return {}

        logger.info("[UZBEK_HANDLER] Starting call campaign (limit: %d)", limit)

        results = await self.voice_agent.run_call_campaign(limit)

        logger.info("[UZBEK_HANDLER] Call campaign completed: %s", results)
        return results

    async def process_interested_leads(self) -> int:
        """Process interested leads - sync to AmoCRM and queue for operators."""
        if not self.integrator:
            logger.error("[UZBEK_HANDLER] Integrator not initialized")
            return 0

        logger.info("[UZBEK_HANDLER] Processing interested leads")

        # Sync to AmoCRM
        synced_count = await self.integrator.sync_interested_to_amocrm()

        # Add to call queue
        queued_count = 0
        if self.call_queue:
            queued_count = await self.call_queue.auto_assign_interested_calls()

        logger.info(
            "[UZBEK_HANDLER] Processed leads: %s synced, %s queued",
            synced_count,
            queued_count,
        )
        return synced_count + queued_count

    async def start_queue_assignment_loop(self, interval_seconds: int = 30) -> None:
        """Start continuous call queue assignment loop."""
        if not self.call_queue:
            logger.error("[UZBEK_HANDLER] Call Queue not initialized")
            return

        logger.info("[UZBEK_HANDLER] Starting queue assignment loop")

        await self.call_queue.run_assignment_loop(interval_seconds)

    async def get_dashboard_stats(self) -> dict:
        """Get dashboard statistics."""
        try:
            from src.database_pool import db_pool
            from src.services.core.finance.hisobchi_schema import ensure_hisobchi_db

            _db = ensure_hisobchi_db(db_pool)

            # Get entrepreneur stats
            rows = await _db.execute(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN call_status = 'pending' THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN call_status = 'interested' THEN 1 ELSE 0 END) as interested,
                    SUM(CASE WHEN call_status = 'called' THEN 1 ELSE 0 END) as called,
                    SUM(CASE WHEN call_status = 'not_interested' THEN 1 ELSE 0 END) as not_interested,
                    SUM(CASE WHEN call_status = 'disconnected' THEN 1 ELSE 0 END) as disconnected,
                    AVG(lead_score) as avg_lead_score
                FROM uzbek_entrepreneurs
                """
            )

            entrepreneur_stats = dict(rows[0]) if rows else {}

            # Get queue stats
            queue_stats = {}
            if self.call_queue:
                queue_stats = await self.call_queue.get_queue_stats()

            # Get call log stats
            call_rows = await _db.execute(
                """
                SELECT
                    COUNT(*) as total_calls,
                    SUM(CASE WHEN pressed_digit = '1' THEN 1 ELSE 0 END) as pressed_1,
                    SUM(CASE WHEN pressed_digit = '2' THEN 1 ELSE 0 END) as pressed_2,
                    AVG(call_duration_seconds) as avg_duration
                FROM entrepreneur_call_logs
                """
            )

            call_stats = dict(call_rows[0]) if call_rows else {}

            return {
                "entrepreneurs": entrepreneur_stats,
                "queue": queue_stats,
                "calls": call_stats,
            }

        except Exception as e:
            logger.error("[UZBEK_HANDLER] Failed to get stats: %s", e)
            return {}

    async def shutdown(self) -> None:
        """Cleanup resources."""
        if self.voice_agent:
            await self.voice_agent.close()
            logger.info("[UZBEK_HANDLER] Voice Agent closed")

        logger.info("[UZBEK_HANDLER] System shutdown complete")


# Global handler instance
_uzbek_handler: Optional[UzbekEntrepreneursHandler] = None


async def get_uzbek_handler() -> UzbekEntrepreneursHandler:
    """Get or create global handler instance."""
    global _uzbek_handler

    if _uzbek_handler is None:
        _uzbek_handler = UzbekEntrepreneursHandler()
        await _uzbek_handler.initialize()

    return _uzbek_handler


# Telegram command handlers
async def handle_uzbek_stats_command(event) -> bool:
    """Handle /uzbek_stats command - show dashboard stats."""
    try:
        handler = await get_uzbek_handler()
        stats = await handler.get_dashboard_stats()

        message = (
            "📊 *Uzbek Entrepreneurs Dashboard*\n\n"
            f"*Jami tadbirkorlar:* {stats.get('entrepreneurs', {}).get('total', 0)}\n"
            f"*Kutilmoqda:* {stats.get('entrepreneurs', {}).get('pending', 0)}\n"
            f"*Qiziqdi:* {stats.get('entrepreneurs', {}).get('interested', 0)}\n"
            f"*Qo'ng'iroq qilindi:* {stats.get('entrepreneurs', {}).get('called', 0)}\n"
            f"*Ulanmadi:* {stats.get('entrepreneurs', {}).get('disconnected', 0)}\n\n"
            f"*O'rtacha lead score:* {stats.get('entrepreneurs', {}).get('avg_lead_score', 0):.1f}\n\n"
            f"*Jami qo'ng'iroqlar:* {stats.get('calls', {}).get('total_calls', 0)}\n"
            f"*1 bosdi:* {stats.get('calls', {}).get('pressed_1', 0)}\n"
            f"*2 bosdi:* {stats.get('calls', {}).get('pressed_2', 0)}\n"
            f"*O'rtacha davomiylik:* {stats.get('calls', {}).get('avg_duration', 0):.1f} sek\n\n"
            f"*Queue:* {stats.get('queue', {})}"
        )

        await event.respond(message, parse_mode="markdown")
        return True

    except Exception as e:
        logger.error("[UZBEK_HANDLER] Stats command failed: %s", e)
        await event.respond("❌ Xatolik yuz berdi")
        return False


async def handle_uzbek_scrape_command(event) -> bool:
    """Handle /uzbek_scrape command - start scraping campaign."""
    try:
        handler = await get_uzbek_handler()

        await event.respond("🔍 Scraping kampaniyasi boshlanmoqda...")

        results = await handler.run_scraping_campaign()

        message = f"✅ Scraping yakunlandi: {len(results)} task"
        await event.respond(message)
        return True

    except Exception as e:
        logger.error("[UZBEK_HANDLER] Scrape command failed: %s", e)
        await event.respond("❌ Xatolik yuz berdi")
        return False


async def handle_uzbek_call_command(event) -> bool:
    """Handle /uzbek_call command - start call campaign."""
    try:
        handler = await get_uzbek_handler()

        if not handler.voice_agent:
            await event.respond("❌ Voice Agent sozlanmagan")
            return False

        await event.respond("📞 Qo'ng'iroq kampaniyasi boshlanmoqda...")

        results = await handler.run_call_campaign(limit=10)

        message = (
            f"✅ Qo'ng'iroq kampaniyasi yakunlandi:\n"
            f"Jami: {results.get('total', 0)}\n"
            f"Qiziqdi: {results.get('interested', 0)}\n"
            f"Qayta qo'ng'iroq: {results.get('callback', 0)}\n"
            f"Ulanmadi: {results.get('disconnected', 0)}"
        )
        await event.respond(message)
        return True

    except Exception as e:
        logger.error("[UZBEK_HANDLER] Call command failed: %s", e)
        await event.respond("❌ Xatolik yuz berdi")
        return False


async def handle_uzbek_process_command(event) -> bool:
    """Handle /uzbek_process command - process interested leads."""
    try:
        handler = await get_uzbek_handler()

        await event.respond("⚙️ Qiziqqan leadlar qayta ishlanmoqda...")

        count = await handler.process_interested_leads()

        message = f"✅ {count} lead qayta ishlandi (AmoCRM + Queue)"
        await event.respond(message)
        return True

    except Exception as e:
        logger.error("[UZBEK_HANDLER] Process command failed: %s", e)
        await event.respond("❌ Xatolik yuz berdi")
        return False
