"""Moizvonki SIM-card SMS client and missed-call auto-SMS automation.

Uses Moizvonki REST API v1 (`action: "calls.send_sms"`) so SMS messages are
dispatched directly from the corresponding manager's Android smartphone SIM.
"""
from __future__ import annotations

import logging
import os
import re
import sqlite3
import time
from typing import Any, Dict, Optional

import httpx

from src.services.core.crm.phone_blacklist import is_excluded_phone
from src.services.core.crm.team_roster import get_active_staff
from src.settings import settings

logger = logging.getLogger(__name__)

SMS_TEMPLATES: Dict[str, str] = {
    "missed_call": (
        "Assalomu alaykum! Jon Branding Agentligidan brending boʻyicha murojaatingiz "
        "yuzasidan qoʻngʻiroq qildik, ulana olmadik. Qulay vaqtingizda shu raqamga "
        "qayta qoʻngʻiroq qiling yoki Telegram orqali yozing."
    ),
    "post_call_kp": (
        "Assalomu alaykum! Jon Branding Agentligidan suhbatlashdik. Portfolio va "
        "tijorat taklifini Telegram orqali yubordik. Savollar boʻlsa shu raqamga "
        "qoʻngʻiroq qiling yoki Telegramʼdan yozing."
    ),
    "meeting_reminder": (
        "Assalomu alaykum! Jon Branding Agentligi bilan bugungi uchrashuvimizni "
        "eslatib qoʻymoqchimiz. Kelishilgan vaqtda kutyapmiz! Savollar boʻlsa "
        "shu raqamga bogʻlaning."
    ),
    "follow_up": (
        "Assalomu alaykum! Jon Branding Agentligidan. Brending loyihangiz boʻyicha "
        "biror savollar tugʻildimi? Qulay vaqtda shu raqamga qayta bogʻlaning yoki "
        "Telegramʼdan yozing."
    ),
}

_MISSED_STATUSES = {"missed", "busy", "no_answer", "unanswered", "failed", "cancel"}


def _digits_only(phone: str) -> str:
    return re.sub(r"\D", "", phone or "")


def _normalize_sms_phone(phone: str) -> str:
    digits = _digits_only(phone)
    if not digits:
        return ""
    if len(digits) == 9:
        digits = "998" + digits
    return f"+{digits}"


def _is_internal_team_phone(phone: str) -> bool:
    digits = _digits_only(phone)
    if not digits:
        return False
    local9 = digits[-9:] if len(digits) >= 9 else digits
    for member in get_active_staff():
        member_digits = _digits_only(member.phone)
        if not member_digits:
            continue
        member_local9 = member_digits[-9:] if len(member_digits) >= 9 else member_digits
        if digits == member_digits or (len(local9) == 9 and local9 == member_local9):
            return True
    return False


def _secret_value(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "get_secret_value"):
        return str(value.get_secret_value() or "").strip()
    return str(value).strip()


class MoizvonkiSmsClient:
    """Thin async client for Moizvonki REST API v1 `calls.send_sms`."""

    def __init__(self, settings_obj: Any = None, timeout: float = 15.0) -> None:
        self._settings = settings_obj if settings_obj is not None else settings
        self.timeout = timeout

    def _endpoint(self) -> str:
        domain = (
            getattr(self._settings, "MOIZVONKI_DOMAIN", None)
            or os.getenv("MOIZVONKI_DOMAIN")
            or "jonbrandingagency.moizvonki.ru"
        ).strip().replace("https://", "").replace("http://", "").rstrip("/")
        return f"https://{domain}/api/v1"

    def _api_key(self) -> str:
        return (
            _secret_value(getattr(self._settings, "MOIZVONKI_API_KEY", None))
            or os.getenv("MOIZVONKI_API_KEY", "").strip()
        )

    def _default_user(self) -> str:
        return (
            str(getattr(self._settings, "MOIZVONKI_EMAIL", None) or "").strip()
            or os.getenv("MOIZVONKI_EMAIL", "").strip()
        )

    async def send_sms(
        self,
        to_phone: str,
        text: str,
        user_name: str = "",
    ) -> Dict[str, Any]:
        """Send an SMS via the specified Moizvonki user's Android SIM card."""
        normalized = _normalize_sms_phone(to_phone)
        if not normalized:
            return {"sent": False, "reason": "invalid_phone"}
        if is_excluded_phone(normalized, self._settings):
            logger.info("[MOIZVONKI-SMS] Skipped blacklisted phone: %s", normalized)
            return {"sent": False, "reason": "blacklisted"}
        if _is_internal_team_phone(normalized):
            logger.info("[MOIZVONKI-SMS] Skipped internal team phone: %s", normalized)
            return {"sent": False, "reason": "internal_team"}

        api_key = self._api_key()
        sender = (user_name or "").strip() if "@" in (user_name or "") else self._default_user()
        if not api_key or not sender:
            logger.warning("[MOIZVONKI-SMS] Missing MOIZVONKI_API_KEY or user_name")
            return {"sent": False, "reason": "not_configured"}

        payload = {
            "user_name": sender,
            "api_key": api_key,
            "action": "calls.send_sms",
            "to": normalized,
            "text": text,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    self._endpoint(),
                    json=payload,
                    headers={"Content-Type": "application/json", "Accept": "application/json"},
                )
            ok = 200 <= resp.status_code < 300
            if not ok:
                logger.warning(
                    "[MOIZVONKI-SMS] API error status=%s to=%s sender=%s",
                    resp.status_code,
                    normalized,
                    sender,
                )
            return {
                "sent": ok,
                "status_code": resp.status_code,
                "to": normalized,
                "sender": sender,
            }
        except Exception as exc:
            logger.warning("[MOIZVONKI-SMS] Request failed to=%s: %s", normalized, exc)
            return {"sent": False, "reason": "request_error", "error": str(exc)}

    async def send_template(
        self,
        to_phone: str,
        template_key: str,
        user_name: str = "",
    ) -> Dict[str, Any]:
        """Send one of the predefined Jon Branding SMS templates."""
        text = SMS_TEMPLATES.get(template_key)
        if not text:
            return {"sent": False, "reason": "unknown_template"}
        return await self.send_sms(to_phone=to_phone, text=text, user_name=user_name)


class MissedCallAutoSms:
    """Automatically sends the missed-call SMS once per cooldown window."""

    def __init__(
        self,
        client: Optional[MoizvonkiSmsClient] = None,
        db_path: str = "data/moizvonki_sms_log.db",
        settings_obj: Any = None,
    ) -> None:
        self._settings = settings_obj if settings_obj is not None else settings
        self.client = client or MoizvonkiSmsClient(settings_obj=self._settings)
        self.db_path = db_path

    def _cooldown_seconds(self) -> int:
        hours = int(getattr(self._settings, "MOIZVONKI_AUTO_SMS_COOLDOWN_HOURS", 24) or 24)
        return max(1, hours) * 3600

    def _is_in_cooldown(self, normalized_phone: str, now_ts: Optional[float] = None) -> bool:
        now = now_ts if now_ts is not None else time.time()
        cutoff = now - self._cooldown_seconds()
        conn = None
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
            conn = sqlite3.connect(self.db_path)
            with conn:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS sent_sms_log ("
                    "phone TEXT PRIMARY KEY, template_key TEXT, sender TEXT, sent_at REAL)"
                )
                row = conn.execute(
                    "SELECT sent_at FROM sent_sms_log WHERE phone = ?",
                    (normalized_phone,),
                ).fetchone()
                return bool(row and float(row[0]) >= cutoff)
        except Exception as exc:
            logger.warning("[MOIZVONKI-SMS] Cooldown read failed: %s", exc)
            return False
        finally:
            if conn:
                conn.close()

    def _record_sent(
        self,
        normalized_phone: str,
        template_key: str,
        sender: str,
        now_ts: Optional[float] = None,
    ) -> None:
        now = now_ts if now_ts is not None else time.time()
        conn = None
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
            conn = sqlite3.connect(self.db_path)
            with conn:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS sent_sms_log ("
                    "phone TEXT PRIMARY KEY, template_key TEXT, sender TEXT, sent_at REAL)"
                )
                conn.execute(
                    "INSERT OR REPLACE INTO sent_sms_log (phone, template_key, sender, sent_at) "
                    "VALUES (?, ?, ?, ?)",
                    (normalized_phone, template_key, sender, now),
                )
        except Exception as exc:
            logger.warning("[MOIZVONKI-SMS] Cooldown write failed: %s", exc)
        finally:
            if conn:
                conn.close()

    @staticmethod
    def is_missed_call(status: str, duration: int) -> bool:
        norm_status = (status or "").strip().lower()
        if norm_status in _MISSED_STATUSES:
            return True
        return int(duration or 0) <= 0 and norm_status != "answered"

    async def handle_call_finish(
        self,
        phone: str,
        status: str,
        duration: int,
        user_account: str = "",
    ) -> Dict[str, Any]:
        """Send missed-call SMS from the manager's SIM if call went unanswered."""
        if not bool(getattr(self._settings, "MOIZVONKI_AUTO_SMS_ENABLED", True)):
            return {"sent": False, "reason": "disabled"}
        if not self.is_missed_call(status, duration):
            return {"sent": False, "reason": "not_missed"}

        normalized = _normalize_sms_phone(phone)
        if not normalized:
            return {"sent": False, "reason": "invalid_phone"}
        if is_excluded_phone(normalized, self._settings):
            return {"sent": False, "reason": "blacklisted"}
        if _is_internal_team_phone(normalized):
            return {"sent": False, "reason": "internal_team"}
        if self._is_in_cooldown(normalized):
            logger.info("[MOIZVONKI-SMS] Cooldown active for %s; skipping auto-SMS", normalized)
            return {"sent": False, "reason": "cooldown"}

        result = await self.client.send_template(
            to_phone=normalized,
            template_key="missed_call",
            user_name=user_account,
        )
        if result.get("sent"):
            self._record_sent(normalized, "missed_call", str(result.get("sender") or user_account))
            logger.info(
                "[MOIZVONKI-SMS] Auto missed-call SMS sent to=%s via=%s",
                normalized,
                result.get("sender"),
            )
        return result
