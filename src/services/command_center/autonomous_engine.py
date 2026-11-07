"""Autonomous Cockpit Engine for 24/7 Hands-Free Sales Operation.

Orchestrates proactive speed-to-lead SLA enforcement, morning executive pulses,
seller daily triage missions, ad spend anomaly detection, and evening wrapups
without requiring any manual slash command or button press.
"""
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from src.services.command_center.ad_attribution import AdAttributionEngine
from src.services.command_center.live_db_bridge import LiveDataBridge
from src.services.command_center.speed_to_lead import (
    SpeedToLeadCalculator,
)
from src.services.command_center.stuck_deals import StuckDealsRadar
from src.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class AutonomousAlert:
    """Represents a generated autonomous proactive notification."""

    alert_type: str  # "sla_nudge", "sla_escalation", "ad_anomaly", "morning_pulse"
    recipient_chat_id: str
    message_text: str
    reply_markup: Any | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class AutonomousCockpitEngine:
    """Coordinates autonomous monitoring, alerting, and proactive reporting."""

    def __init__(self, bridge: LiveDataBridge | None = None) -> None:
        """Initialize autonomous engine with live database bridge."""
        self.bridge = bridge or LiveDataBridge()
        self.reminded_leads: dict[str, datetime] = {}
        self.escalated_leads: dict[str, datetime] = {}
        self.notified_anomalies: set[str] = set()

    async def scan_speed_to_lead_alerts(
        self,
        now: datetime | None = None,
        remind_min: int = 15,
        escalate_min: int = 30,
        seller_map: dict[str, str] | None = None,
        escalation_chat_id: str | None = None,
    ) -> list[AutonomousAlert]:
        """Detect unanswered leads and generate proactive alerts for managers and ROP."""
        current_time = now or datetime.now(UTC)
        interactions = await self.bridge.fetch_recent_lead_interactions()
        alerts: list[AutonomousAlert] = []
        sellers = seller_map or {}

        for item in interactions:
            if item.first_response_at is not None:
                continue

            created = item.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=UTC)

            wait_minutes = int((current_time - created).total_seconds() / 60)
            lead_id = item.lead_id
            manager_id = item.manager_id
            tg_target = sellers.get(manager_id, manager_id)

            # 1. 15-minute Seller Nudge
            if wait_minutes >= remind_min and lead_id not in self.reminded_leads:
                text = (
                    "⏰ <b>[OISHA AVTO-ESLATMA]: Yangi lid kutmoqda!</b>\n\n"
                    f"📌 <b>Mijoz:</b> {item.customer_name} ({item.channel})\n"
                    f"⏳ <b>Kutish vaqti:</b> {wait_minutes} daqiqa\n\n"
                    "Lid sovimasligi uchun zudlik bilan qoʻngʻiroq qiling yoki xabar yozing!"
                )
                alerts.append(
                    AutonomousAlert(
                        alert_type="sla_nudge",
                        recipient_chat_id=str(tg_target),
                        message_text=text,
                        metadata={"lead_id": lead_id, "wait_minutes": wait_minutes},
                    )
                )
                self.reminded_leads[lead_id] = current_time

            # 2. 30-minute ROP / Group Escalation
            if wait_minutes >= escalate_min and lead_id not in self.escalated_leads:
                esc_chat = escalation_chat_id or getattr(settings, "TEAM_GROUP_ID", "")
                if esc_chat:
                    esc_text = (
                        "🚨 <b>[SLA BUZILIShI OGOHLANTIRISHI]</b>\n\n"
                        f"📌 <b>Mijoz:</b> {item.customer_name} ({item.channel})\n"
                        f"👤 <b>Masʼul:</b> {manager_id}\n"
                        f"⏳ <b>Kutish vaqti:</b> {wait_minutes} daqiqadan oshdi!\n\n"
                        "Menejer oʻz vaqtida javob bermadi. Lidni zudlik bilan boshqa sotuvchiga "
                        "biriktirish yoki ROP aralashuvi talab etiladi."
                    )
                    alerts.append(
                        AutonomousAlert(
                            alert_type="sla_escalation",
                            recipient_chat_id=str(esc_chat),
                            message_text=esc_text,
                            metadata={"lead_id": lead_id, "manager_id": manager_id},
                        )
                    )
                self.escalated_leads[lead_id] = current_time

        return alerts

    async def build_morning_executive_card(
        self,
        base_url: str | None = None,
    ) -> tuple[str, Any]:
        """Construct rich Executive Morning Pulse card for CEO and management chat."""
        interactions = await self.bridge.fetch_recent_lead_interactions()
        deals = await self.bridge.fetch_active_deal_records()
        camps, ad_leads = await self.bridge.fetch_ad_attribution_data()

        stl_calc = SpeedToLeadCalculator()
        stl_metrics = stl_calc.calculate(interactions)

        radar = StuckDealsRadar(default_threshold_days=3)
        stuck_summary = radar.analyze(deals)

        ad_engine = AdAttributionEngine()
        ad_summary = ad_engine.calculate(camps, ad_leads)

        won_sum = ad_summary.total_revenue
        won_str = f"{won_sum / 1_000_000:.1f} mln" if won_sum else "0 mln"
        stuck_sum = stuck_summary.total_stuck_value
        stuck_str = f"{stuck_sum / 1_000_000:.1f} mln" if stuck_sum else "0 mln"
        cpl_val = int(ad_summary.cost_per_lead)

        card_text = (
            "🌅 <b>Oisha-OS — Tonggi Boshqaruv va Savdo Pulsi</b>\n\n"
            f"🏆 <b>Joriy Yopilgan Savdo:</b> {won_str} soʻm\n"
            f"⚡ <b>Speed to Lead SLA:</b> {stl_metrics.sla_rate_pct}% "
            f"(Oʻrtacha javob: {stl_metrics.avg_response_minutes} daqiqa)\n"
            f"⏳ <b>Javobsiz yangi lidlar:</b> {stl_metrics.unanswered_leads} ta\n"
            f"🧊 <b>Qotib qolgan bitimlar (Radar):</b> {stuck_summary.total_stuck_deals} ta "
            f"({stuck_str} soʻm muzlagan)\n"
            f"📣 <b>Reklama CPL:</b> {cpl_val:,} soʻm "
            f"(Jami sarf: {int(ad_summary.total_spend):,} soʻm)\n\n"
            "<i>Ushbu hisobot toʻliq avtonom rejimda shakllantirildi.</i>"
        )

        app_url = (base_url or getattr(settings, "WEBAPP_URL", "https://oisha.jonbranding.uz")).rstrip("/")
        keyboard = self._create_webapp_markup(f"{app_url}/metasell-console")
        return card_text, keyboard

    async def scan_ad_spend_anomalies(
        self,
        cpl_alert_threshold: float = 45_000.0,
        zero_leads_spend_limit: float = 120_000.0,
    ) -> list[AutonomousAlert]:
        """Identify underperforming ad campaigns and generate targetolog/owner alerts."""
        camps, ad_leads = await self.bridge.fetch_ad_attribution_data()
        ad_engine = AdAttributionEngine()
        summary = ad_engine.calculate(camps, ad_leads)
        alerts: list[AutonomousAlert] = []
        owner_id = str(getattr(settings, "OWNER_ID", "") or "")

        if not owner_id:
            return alerts

        for camp_id, perf in summary.campaign_performances.items():
            camp_key = f"{camp_id}_{datetime.now(UTC).strftime('%Y%m%d')}"
            if camp_key in self.notified_anomalies:
                continue

            is_high_cpl = perf.new_leads > 0 and perf.cost_per_lead > cpl_alert_threshold
            is_burning_cash = perf.new_leads == 0 and perf.spend >= zero_leads_spend_limit

            if is_high_cpl or is_burning_cash:
                reason = "CPL juda yuqori" if is_high_cpl else "Lidsiz sarf qilinmoqda"
                msg = (
                    "🚨 <b>[REKLAMA BYUDJETI XAVFI — AVTO-OGOHLANTIRISH]</b>\n\n"
                    f"📣 <b>Kampaniya:</b> {perf.campaign_name} ({perf.platform})\n"
                    f"💸 <b>Sarf:</b> {int(perf.spend):,} soʻm\n"
                    f"👥 <b>Kelgan lidlar:</b> {perf.new_leads} ta\n"
                    f"⚠️ <b>Holat:</b> {reason} (CPL: {int(perf.cost_per_lead):,} soʻm)\n\n"
                    "Byudjet isrofiga yoʻl qoʻymaslik uchun kreativ yoki auditoriyani "
                    "zudlik bilan qayta tekshiring!"
                )
                alerts.append(
                    AutonomousAlert(
                        alert_type="ad_anomaly",
                        recipient_chat_id=owner_id,
                        message_text=msg,
                        metadata={"campaign_id": camp_id, "cpl": perf.cost_per_lead},
                    )
                )
                self.notified_anomalies.add(camp_key)

        return alerts

    async def build_evening_closing_card(self) -> str:
        """Construct end-of-day wrapup card with achieved sales metrics."""
        interactions = await self.bridge.fetch_recent_lead_interactions()
        deals = await self.bridge.fetch_active_deal_records()
        camps, ad_leads = await self.bridge.fetch_ad_attribution_data()

        stl_calc = SpeedToLeadCalculator()
        stl_metrics = stl_calc.calculate(interactions)
        ad_engine = AdAttributionEngine()
        ad_summary = ad_engine.calculate(camps, ad_leads)

        won_str = f"{ad_summary.total_revenue / 1_000_000:.1f} mln" if ad_summary.total_revenue else "0 mln"
        answered_cnt = len([i for i in interactions if i.first_response_at is not None])

        return (
            "🌆 <b>Oisha-OS — Kunlik Savdo Sarhisobi (19:30)</b>\n\n"
            f"🏆 <b>Kunlik Tushum / Yopilgan Bitimlar:</b> {won_str} soʻm\n"
            f"📞 <b>Qayta ishlangan lidlar:</b> {answered_cnt} ta\n"
            f"⚡ <b>Kunlik SLA foizi:</b> {stl_metrics.sla_rate_pct}%\n"
            f"🎯 <b>Faol bitimlar soni:</b> {len(deals)} ta\n\n"
            "Barcha kechiktirilgan masalalar ertangi trijaj navbatiga biriktirildi. "
            "Rahmat, jamoa!"
        )

    def _create_webapp_markup(self, url: str) -> Any | None:
        """Safely build aiogram InlineKeyboardMarkup with WebApp button."""
        try:
            from aiogram.types import (
                InlineKeyboardButton,
                InlineKeyboardMarkup,
                WebAppInfo,
            )
            return InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🚀 Jonli Boshqaruv Markazi (Cockpit)",
                            web_app=WebAppInfo(url=url),
                        )
                    ]
                ]
            )
        except Exception:  # noqa: BLE001
            return None
