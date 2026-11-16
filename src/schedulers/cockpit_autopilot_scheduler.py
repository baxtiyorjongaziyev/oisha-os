"""Cockpit Autopilot Background Scheduler for 24/7 Hands-Free Automation.

Runs autonomous monitoring loops without requiring manual commands:
  - Every 2 minutes: Proactive Speed-to-Lead SLA watchdog (15m nudge, 30m escalation).
  - Every 2 hours: Ad spend & CPL anomaly watchdog.
  - Daily 08:45 Tashkent: Morning Executive Pulse delivered to CEO and team.
  - Daily 19:30 Tashkent: Evening sales wrapup and closing summary.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from typing import Any

from src.services.command_center.autonomous_engine import (
    AutonomousAlert,
    AutonomousCockpitEngine,
)
from src.services.core.telegram.bot_runtime import BotRuntimePort, TelethonBotRuntime
from src.settings import settings
from src.time_utils import get_local_now, is_quiet_hours, is_sunday

logger = logging.getLogger("CockpitAutopilot")

_DEFAULT_STATE_PATH = "data/cockpit_autopilot_state.json"


def parse_seller_map(raw_map: str) -> dict[str, str]:
    """Parse 'mgr_1:123456,mgr_2:654321' into a string key-value dictionary."""
    mapping: dict[str, str] = {}
    for pair in (raw_map or "").split(","):
        if ":" in pair:
            key, val = pair.split(":", 1)
            mapping[key.strip()] = val.strip()
    return mapping


def _as_bot_runtime(bot_client: Any) -> BotRuntimePort | None:
    """Wrap raw bot client into normalized BotRuntimePort."""
    if bot_client is None:
        return None
    if hasattr(bot_client, "backend") and hasattr(bot_client, "send_message"):
        return bot_client
    return TelethonBotRuntime(bot_client)


class CockpitAutopilotScheduler:
    """Manages scheduled background execution of all autonomous cockpit tasks."""

    def __init__(
        self,
        bot_runtime: Any,
        engine: AutonomousCockpitEngine | None = None,
    ) -> None:
        """Initialize autopilot scheduler with bot runtime and autonomous engine."""
        self.bot = _as_bot_runtime(bot_runtime)
        self.engine = engine or AutonomousCockpitEngine(state_path=_DEFAULT_STATE_PATH)
        self.last_pulse_date: str | None = getattr(self.engine, "last_pulse_date", None)
        self.last_wrapup_date: str | None = getattr(self.engine, "last_wrapup_date", None)
        self.seller_map = parse_seller_map(os.getenv("SELLER_TELEGRAM_MAP", ""))

    async def send_alert(self, alert: AutonomousAlert) -> bool:
        """Deliver proactive alert through the bot runtime safely."""
        if not self.bot or not alert.recipient_chat_id:
            return False

        try:
            kwargs: dict[str, Any] = {
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            }
            if alert.reply_markup:
                kwargs["reply_markup"] = alert.reply_markup

            await self.bot.send_message(
                alert.recipient_chat_id,
                alert.message_text,
                **kwargs,
            )
            logger.info("[AUTOPILOT] Alert %s sent to %s", alert.alert_type, alert.recipient_chat_id)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[AUTOPILOT] Failed to send %s alert to %s: %s",
                alert.alert_type,
                alert.recipient_chat_id,
                exc,
            )
            return False

    async def execute_speed_to_lead_cycle(
        self,
        now: datetime | None = None,
        force: bool = False,
    ) -> int:
        """Run single speed to lead check cycle and dispatch generated alerts."""
        if not force and (is_quiet_hours(now) or is_sunday(now)):
            return 0

        escalation_chat = getattr(settings, "TEAM_GROUP_ID", None) or getattr(settings, "ROP_CEO_CHAT_ID", None)
        alerts = await self.engine.scan_speed_to_lead_alerts(
            now=now,
            seller_map=self.seller_map,
            escalation_chat_id=str(escalation_chat) if escalation_chat else None,
        )

        sent_count = 0
        for alert in alerts:
            if await self.send_alert(alert):
                sent_count += 1
        return sent_count

    async def execute_ad_anomaly_cycle(
        self,
        now: datetime | None = None,
        force: bool = False,
    ) -> int:
        """Run single marketing attribution check and notify owner if anomalies exist."""
        if not force and is_quiet_hours(now):
            return 0

        alerts = await self.engine.scan_ad_spend_anomalies()
        sent_count = 0
        for alert in alerts:
            if await self.send_alert(alert):
                sent_count += 1
        return sent_count

    async def execute_morning_pulse_if_due(self, now: datetime | None = None) -> bool:
        """Send daily 08:45 AM Tashkent morning executive pulse if not yet sent today."""
        current = now or get_local_now()
        today = current.strftime("%Y-%m-%d")

        if is_sunday(current) or self.last_pulse_date == today:
            return False

        if current.hour == 8 and current.minute >= 45:
            owner_id = str(getattr(settings, "OWNER_ID", "") or "")
            group_id = str(getattr(settings, "TEAM_GROUP_ID", "") or "")

            text, markup = await self.engine.build_morning_executive_card()
            targets = {target for target in [owner_id, group_id] if target}

            for chat_id in targets:
                alert = AutonomousAlert(
                    alert_type="morning_pulse",
                    recipient_chat_id=chat_id,
                    message_text=text,
                    reply_markup=markup,
                )
                await self.send_alert(alert)

            self.last_pulse_date = today
            if hasattr(self.engine, "last_pulse_date"):
                self.engine.last_pulse_date = today
            if hasattr(self.engine, "save_state"):
                self.engine.save_state()
            logger.info("[AUTOPILOT] Morning pulse completed for %s", today)
            return True

        return False

    async def execute_evening_wrapup_if_due(self, now: datetime | None = None) -> bool:
        """Send daily 19:30 PM Tashkent evening wrapup if not yet sent today."""
        current = now or get_local_now()
        today = current.strftime("%Y-%m-%d")

        if is_sunday(current) or self.last_wrapup_date == today:
            return False

        if current.hour == 19 and current.minute >= 30:
            group_id = str(getattr(settings, "TEAM_GROUP_ID", "") or getattr(settings, "OWNER_ID", ""))
            if group_id:
                wrapup_text = await self.engine.build_evening_closing_card()
                alert = AutonomousAlert(
                    alert_type="evening_wrapup",
                    recipient_chat_id=group_id,
                    message_text=wrapup_text,
                )
                await self.send_alert(alert)

            self.last_wrapup_date = today
            if hasattr(self.engine, "last_wrapup_date"):
                self.engine.last_wrapup_date = today
            if hasattr(self.engine, "save_state"):
                self.engine.save_state()
            logger.info("[AUTOPILOT] Evening wrapup completed for %s", today)
            return True

        return False

    async def run_autopilot_loop(self) -> None:
        """Master background loop running 24/7 on Contabo VPS."""
        logger.info("[AUTOPILOT] Cockpit Autopilot 24/7 background loop started.")
        await asyncio.sleep(10)

        tick_counter = 0
        while True:
            try:
                await self.execute_speed_to_lead_cycle()
                await self.execute_morning_pulse_if_due()
                await self.execute_evening_wrapup_if_due()

                tick_counter += 1
                if tick_counter >= 60:
                    await self.execute_ad_anomaly_cycle()
                    tick_counter = 0

            except Exception:
                logger.exception("[AUTOPILOT] Loop unexpected error")

            await asyncio.sleep(120)


def start_cockpit_autopilot_scheduler(bot_runtime: Any) -> asyncio.Task | None:
    """Start cockpit autopilot loop in the global asyncio runtime."""
    enabled = os.getenv("ENABLE_COCKPIT_AUTOPILOT", "1").strip().lower() in {"1", "true", "yes", "on"}
    if not enabled:
        logger.info("[AUTOPILOT] Cockpit Autopilot is disabled by environment setting.")
        return None

    scheduler = CockpitAutopilotScheduler(bot_runtime)
    task = asyncio.create_task(scheduler.run_autopilot_loop(), name="cockpit_autopilot_loop")
    logger.info("[AUTOPILOT] Background autopilot task created.")
    return task
