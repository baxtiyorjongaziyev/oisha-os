"""Autonomous Cockpit Engine for 24/7 Hands-Free Sales Operation.

Orchestrates proactive speed-to-lead SLA enforcement, morning executive pulses,
seller daily triage missions, ad spend anomaly detection, and evening wrapups
without requiring any manual slash command or button press.
"""
from __future__ import annotations

import html
import inspect
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from src.services.command_center.ad_attribution import AdAttributionEngine
from src.services.command_center.daily_closing import (
    collect_from_legacy_mock_bridge,
    format_evening_closing_card,
)
from src.services.command_center.live_db_bridge import LiveDataBridge
from src.services.command_center.speed_to_lead import SpeedToLeadCalculator
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


def _is_valid_chat_id(chat_id: Any) -> bool:
    """Return True if chat_id is a valid numeric Telegram user or group ID."""
    val = str(chat_id or "").strip()
    return bool(val) and val.lstrip("-").isdigit()


def _format_money(amount: float, currency: str) -> str:
    """Format monetary values cleanly with explicit currency."""
    if str(currency or "").upper() == "USD":
        return f"${amount:,.2f}"
    return f"{int(amount):,} soʻm"


class AutonomousCockpitEngine:
    """Coordinates autonomous monitoring, alerting, and proactive reporting."""

    def __init__(
        self,
        bridge: LiveDataBridge | None = None,
        *,
        state_path: str | Path | None = None,
    ) -> None:
        """Initialize autonomous engine with live bridge and optional persisted state."""
        self.bridge = bridge or LiveDataBridge()
        self.state_path = Path(state_path) if state_path else None
        self.reminded_leads: dict[str, datetime] = {}
        self.escalated_leads: dict[str, datetime] = {}
        self.notified_anomalies: set[str] = set()
        self.last_pulse_date: str | None = None
        self.last_wrapup_date: str | None = None
        if self.state_path:
            self._load_state()

    def _load_state(self) -> None:
        """Load deduplication watermarks from disk so restarts never replay alerts."""
        if not self.state_path or not self.state_path.exists():
            return
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(data, dict):
            return

        raw_reminded = self._parse_ts_map(data.get("reminded_leads"))
        raw_escalated = self._parse_ts_map(data.get("escalated_leads"))
        all_ts = list(raw_reminded.values()) + list(raw_escalated.values())
        anchor = max(all_ts) if all_ts else datetime.now(UTC)
        cutoff = anchor - timedelta(days=7)
        self.reminded_leads = {k: v for k, v in raw_reminded.items() if v >= cutoff}
        self.escalated_leads = {k: v for k, v in raw_escalated.items() if v >= cutoff}
        self.notified_anomalies = {str(k) for k in (data.get("notified_anomalies") or [])}
        self.last_pulse_date = data.get("last_pulse_date")
        self.last_wrapup_date = data.get("last_wrapup_date")

    def _parse_ts_map(self, raw: Any) -> dict[str, datetime]:
        if not isinstance(raw, dict):
            return {}
        parsed: dict[str, datetime] = {}
        for k, v in raw.items():
            try:
                dt = datetime.fromisoformat(str(v))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                parsed[str(k)] = dt
            except (ValueError, TypeError):
                continue
        return parsed

    def save_state(self, reference_time: datetime | None = None) -> None:
        """Persist deduplication watermarks atomically if state_path is configured."""
        if not self.state_path:
            return
        anchor = reference_time or datetime.now(UTC)
        cutoff = anchor - timedelta(days=7)
        today_tag = anchor.strftime("%Y%m%d")
        payload = {
            "reminded_leads": {
                k: v.isoformat() for k, v in self.reminded_leads.items() if v >= cutoff
            },
            "escalated_leads": {
                k: v.isoformat() for k, v in self.escalated_leads.items() if v >= cutoff
            },
            "notified_anomalies": sorted(
                k for k in self.notified_anomalies if k.endswith(f"_{today_tag}")
            ),
            "last_pulse_date": self.last_pulse_date,
            "last_wrapup_date": self.last_wrapup_date,
        }
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.state_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.state_path)
        except OSError as exc:
            logger.warning("[AUTOPILOT] Failed to save state: %s", exc)

    def _resolve_seller_tg(self, sellers: dict[str, str], manager_id: str) -> str | None:
        """Resolve a manager identifier to a valid numeric Telegram chat ID."""
        if not sellers or not manager_id:
            return None
        direct = sellers.get(manager_id)
        if _is_valid_chat_id(direct):
            return str(direct).strip()
        target_lower = manager_id.strip().lower()
        for key, val in sellers.items():
            if key.strip().lower() == target_lower and _is_valid_chat_id(val):
                return str(val).strip()
        return None

    async def scan_speed_to_lead_alerts(
        self,
        now: datetime | None = None,
        remind_min: int = 15,
        escalate_min: int = 30,
        seller_map: dict[str, str] | None = None,
        escalation_chat_id: str | None = None,
        max_age_minutes: int = 24 * 60,
    ) -> list[AutonomousAlert]:
        """Detect unanswered recent leads and generate alerts for managers and ROP."""
        current_time = now or datetime.now(UTC)
        interactions = await self.bridge.fetch_recent_lead_interactions()
        alerts: list[AutonomousAlert] = []
        sellers = seller_map or {}
        state_dirty = False

        for item in interactions:
            if item.first_response_at is not None:
                continue
            if "synthetic test" in (item.customer_name or "").lower():
                continue

            created = item.created_at if item.created_at.tzinfo else item.created_at.replace(tzinfo=UTC)
            wait_minutes = int((current_time - created).total_seconds() / 60)
            if wait_minutes < remind_min or wait_minutes > max_age_minutes:
                continue

            item_alerts, changed = self._alerts_for_waiting_lead(
                item, wait_minutes, current_time, escalate_min, sellers, escalation_chat_id
            )
            alerts.extend(item_alerts)
            state_dirty = state_dirty or changed

        if state_dirty:
            self.save_state(reference_time=current_time)
        return alerts

    def _alerts_for_waiting_lead(
        self,
        item: Any,
        wait_minutes: int,
        current_time: datetime,
        escalate_min: int,
        sellers: dict[str, str],
        escalation_chat_id: str | None,
    ) -> tuple[list[AutonomousAlert], bool]:
        """Build nudge/escalation alerts for one unanswered lead."""
        alerts: list[AutonomousAlert] = []
        changed = False
        lead_id, manager_id = item.lead_id, item.manager_id
        cust_safe = html.escape(item.customer_name)
        chan_safe = html.escape(item.channel)
        mgr_safe = html.escape(manager_id)

        tg_target = self._resolve_seller_tg(sellers, manager_id)
        if tg_target and lead_id not in self.reminded_leads:
            text = (
                "⏰ <b>[OISHA AVTO-ESLATMA]: Yangi lid kutmoqda!</b>\n\n"
                f"📌 <b>Mijoz:</b> {cust_safe} ({chan_safe})\n"
                f"⏳ <b>Kutish vaqti:</b> {wait_minutes} daqiqa\n\n"
                "Lid sovimasligi uchun zudlik bilan qoʻngʻiroq qiling yoki xabar yozing!"
            )
            alerts.append(
                AutonomousAlert(
                    alert_type="sla_nudge",
                    recipient_chat_id=tg_target,
                    message_text=text,
                    metadata={"lead_id": lead_id, "wait_minutes": wait_minutes},
                )
            )
            self.reminded_leads[lead_id] = current_time
            changed = True

        if wait_minutes >= escalate_min and lead_id not in self.escalated_leads:
            esc_chat = escalation_chat_id or getattr(settings, "TEAM_GROUP_ID", "")
            if _is_valid_chat_id(esc_chat):
                esc_text = (
                    "🚨 <b>[SLA BUZILIShI OGOHLANTIRISHI]</b>\n\n"
                    f"📌 <b>Mijoz:</b> {cust_safe} ({chan_safe})\n"
                    f"👤 <b>Masʼul:</b> {mgr_safe}\n"
                    f"⏳ <b>Kutish vaqti:</b> {wait_minutes} daqiqadan oshdi!\n\n"
                    "Menejer oʻz vaqtida javob bermadi. Lidni zudlik bilan boshqa sotuvchiga "
                    "biriktirish yoki ROP aralashuvi talab etiladi."
                )
                alerts.append(
                    AutonomousAlert(
                        alert_type="sla_escalation",
                        recipient_chat_id=str(esc_chat).strip(),
                        message_text=esc_text,
                        metadata={"lead_id": lead_id, "manager_id": manager_id},
                    )
                )
            self.escalated_leads[lead_id] = current_time
            changed = True

        return alerts, changed

    async def build_morning_executive_card(
        self,
        base_url: str | None = None,
    ) -> tuple[str, Any]:
        """Construct Executive Morning Pulse card from live DB sources."""
        interactions = await self.bridge.fetch_recent_lead_interactions()
        deals = await self.bridge.fetch_active_deal_records()
        camps, ad_leads = await self.bridge.fetch_ad_attribution_data()

        stl_metrics = SpeedToLeadCalculator().calculate(interactions)
        stuck_summary = StuckDealsRadar(default_threshold_days=3).analyze(deals)
        ad_summary = AdAttributionEngine().calculate(camps, ad_leads)
        raw_currency = getattr(self.bridge, "last_spend_currency", "UZS")
        spend_currency = raw_currency if isinstance(raw_currency, str) and raw_currency else "UZS"

        won_str = f"{ad_summary.total_revenue / 1_000_000:.1f} mln" if ad_summary.total_revenue else "0 mln"
        stuck_str = f"{stuck_summary.total_stuck_value / 1_000_000:.1f} mln" if stuck_summary.total_stuck_value else "0 mln"
        cpl_str = _format_money(ad_summary.cost_per_lead, spend_currency)
        spend_str = _format_money(ad_summary.total_spend, spend_currency)
        has_any = bool(interactions or deals or camps or ad_leads)
        footer = (
            "<i>Ushbu hisobot jonli maʼlumotlar asosida avtonom shakllantirildi.</i>"
            if has_any
            else "<i>Bazada joriy davr uchun faol maʼlumot topilmadi.</i>"
        )

        card_text = (
            "🌅 <b>Oisha-OS — Tonggi Boshqaruv va Savdo Pulsi</b>\n\n"
            f"🏆 <b>Joriy Yopilgan Savdo:</b> {won_str} soʻm\n"
            f"⚡ <b>Speed to Lead SLA:</b> {stl_metrics.sla_rate_pct}% "
            f"(Oʻrtacha javob: {stl_metrics.avg_response_minutes} daqiqa)\n"
            f"⏳ <b>Javobsiz yangi lidlar:</b> {stl_metrics.unanswered_leads} ta\n"
            f"🧊 <b>Qotib qolgan bitimlar (Radar):</b> {stuck_summary.total_stuck_deals} ta "
            f"({stuck_str} soʻm muzlagan)\n"
            f"📣 <b>Reklama CPL:</b> {cpl_str} (Jami sarf: {spend_str})\n\n"
            f"{footer}"
        )

        app_url = (base_url or getattr(settings, "WEBAPP_URL", "https://oisha.jonbranding.uz")).rstrip("/")
        keyboard = self._create_webapp_markup(f"{app_url}/metasell-console")
        return card_text, keyboard

    async def scan_ad_spend_anomalies(
        self,
        cpl_alert_threshold: float = 45_000.0,
        zero_leads_spend_limit: float = 120_000.0,
    ) -> list[AutonomousAlert]:
        """Identify underperforming UZS ad campaigns and generate owner alerts."""
        camps, ad_leads = await self.bridge.fetch_ad_attribution_data()
        raw_currency = getattr(self.bridge, "last_spend_currency", "UZS")
        spend_currency = raw_currency if isinstance(raw_currency, str) and raw_currency else "UZS"
        if spend_currency != "UZS":
            return []

        summary = AdAttributionEngine().calculate(camps, ad_leads)
        alerts: list[AutonomousAlert] = []
        owner_id = str(getattr(settings, "OWNER_ID", "") or "")
        if not _is_valid_chat_id(owner_id):
            return alerts

        state_dirty = False
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
                    f"📣 <b>Kampaniya:</b> {html.escape(perf.campaign_name)} ({html.escape(perf.platform)})\n"
                    f"💸 <b>Sarf:</b> {int(perf.spend):,} soʻm\n"
                    f"👥 <b>Kelgan lidlar:</b> {perf.new_leads} ta\n"
                    f"⚠️ <b>Holat:</b> {reason} (CPL: {int(perf.cost_per_lead):,} soʻm)\n\n"
                    "Byudjet isrofiga yoʻl qoʻymaslik uchun kreativ yoki auditoriyani "
                    "zudlik bilan qayta tekshiring!"
                )
                alerts.append(
                    AutonomousAlert(
                        alert_type="ad_anomaly",
                        recipient_chat_id=owner_id.strip(),
                        message_text=msg,
                        metadata={"campaign_id": camp_id, "cpl": perf.cost_per_lead},
                    )
                )
                self.notified_anomalies.add(camp_key)
                state_dirty = True

        if state_dirty:
            self.save_state()
        return alerts

    async def build_evening_closing_card(self, now: datetime | None = None) -> str:
        """Construct honest single-day wrapup card with real sales and overdue task counts."""
        fetch_snap = getattr(self.bridge, "fetch_daily_closing_snapshot", None)
        if inspect.iscoroutinefunction(fetch_snap):
            snap = await fetch_snap(now=now)
        else:
            snap = await collect_from_legacy_mock_bridge(self.bridge, now=now)
        return format_evening_closing_card(snap)

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
