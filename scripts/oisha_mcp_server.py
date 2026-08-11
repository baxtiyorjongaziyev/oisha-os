"""Oisha-OS uchun yagona MCP server.

Ilgari uchta alohida yozuv bor edi:
  - `telegram`        SSH -> Oracle, scripts/telegram_mcp_server.py
  - `oisha-telegram`  lokal, xuddi shu skript (lokalda API yo'q, hech qayerga
                      ulanmasdi)
  - `oisha-amocrm`    lokal, scripts/mcp_server.py

Bu modul ikkalasining toollarini bitta serverga yig'adi. Oracle VM'da
ishlashi ko'zda tutilgan: u yerda `.env`, userbot sessiyasi va FastAPI
control plane (127.0.0.1:8080) mavjud.

Telegram toollari HTTP orqali `/api/internal/mcp` ga boradi — userbot
sessiyasiga to'g'ridan-to'g'ri tegmaydi, chunki sessiya bitta jarayonga
tegishli (parallel ulanish AuthKeyDuplicatedError beradi).

AmoCRM / Airtable / Instagram toollari esa jarayon ichida to'g'ridan-to'g'ri
mos servis sinflarini chaqiradi.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

# Loyiha ildizini sys.path ga qo'shamiz — `src` paketini import qilish uchun.
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

from mcp.server.fastmcp import FastMCP  # noqa: E402

# MCP stdio protokoli stdout'ni band qiladi — barcha log stderr'ga ketishi shart.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("oisha-mcp")

try:  # structlog ixtiyoriy — servis modullari uni ishlatadi
    import structlog

    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(sys.stderr),
        cache_logger_on_first_use=True,
    )
except ImportError:  # pragma: no cover - structlog requirements'da bor
    logger.warning("structlog topilmadi; servis loglari stdout'ga oqishi mumkin")

mcp = FastMCP("oisha")

_API_BASE_URL = (
    os.environ.get("OISHA_API_URL") or "http://127.0.0.1:8080"
).rstrip("/") + "/api/internal/mcp"


# ─── Telegram (HTTP -> FastAPI control plane) ────────────────────────────────


def _api_request(url: str, data: Optional[bytes] = None) -> urllib.request.Request:
    """`/api/internal/mcp` uchun autentifikatsiyalangan so'rov tayyorlaydi.

    Ikki qatlam bor: Nginx Basic Auth va FastAPI internal secret. Ikkalasi ham
    faqat env'dan o'qiladi — kodda default qiymat saqlash uni repo tarixiga
    yozib qo'yadi va rotatsiyani imkonsiz qiladi.
    """
    headers: Dict[str, str] = {}

    auth_user = os.environ.get("OISHA_API_USER", "").strip()
    auth_pass = os.environ.get("OISHA_API_PASS", "").strip()
    secret = (os.environ.get("OISHA_API_SECRET") or "").strip()

    # FastAPI RBAC authenticates trusted service calls with the API secret as
    # a Bearer token.  The dedicated internal-secret header remains as the
    # route-level guard.  Without both, /api/internal/mcp returns 401 even
    # when the Telegram session itself is healthy.
    if secret:
        headers["Authorization"] = f"Bearer {secret}"
    elif auth_user and auth_pass:
        token = base64.b64encode(f"{auth_user}:{auth_pass}".encode()).decode()
        headers["Authorization"] = f"Basic {token}"
    elif auth_user or auth_pass:
        logger.warning(
            "[MCP] OISHA_API_USER/OISHA_API_PASS to'liq emas — Basic Auth o'tkazib yuborildi"
        )

    if secret:
        headers["X-Oisha-Internal-Secret"] = secret
    else:
        logger.warning("[MCP] OISHA_API_SECRET yo'q — internal API rad etadi")

    if data is not None:
        headers["Content-Type"] = "application/json"
    return urllib.request.Request(url, data=data, headers=headers)


def _call_api(url: str, data: Optional[bytes] = None) -> str:
    try:
        with urllib.request.urlopen(_api_request(url, data), timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return json.dumps(payload, indent=2, ensure_ascii=False)
    except urllib.error.HTTPError as exc:
        logger.error("[MCP] HTTP %s: %s", exc.code, url)
        return f"Error: API {exc.code} qaytardi ({exc.reason})."
    except urllib.error.URLError as exc:
        logger.error("[MCP] Ulanib bo'lmadi: %s", exc)
        return f"Error: Oisha API ga ulanib bo'lmadi. {exc.reason}"


@mcp.tool()
async def get_recent_dialogs(limit: int = 10) -> str:
    """Telegram'dagi eng oxirgi dialoglarni (chatlarni) olish."""
    return _call_api(f"{_API_BASE_URL}/dialogs?limit={limit}")


@mcp.tool()
async def get_chat_history(chat_id: str, limit: int = 20) -> str:
    """Muayyan Telegram chat yoki foydalanuvchi bo'yicha oxirgi xabarlarni olish."""
    return _call_api(f"{_API_BASE_URL}/messages/{chat_id}?limit={limit}")


@mcp.tool()
async def send_telegram_message(user_id: str, text: str) -> str:
    """Telegram orqali foydalanuvchi yoki guruhga xabar yuborish.

    Mutatsiya — gateway sozlangan bo'lsa Owner tasdig'idan o'tadi.
    """
    payload = json.dumps({"user_id": str(user_id), "text": text}).encode("utf-8")
    result = _call_api(f"{_API_BASE_URL}/send_message", data=payload)
    if result.startswith("Error:"):
        return result
    return f"Xabar {user_id} ga yuborildi."


@mcp.tool()
async def analyze_private_chats() -> str:
    """Shaxsiy chatlarni tahlil qilish (papka filtrlari asosida)."""
    return _call_api(f"{_API_BASE_URL}/analyze_private_chats")


# ─── AmoCRM / Airtable / Instagram (jarayon ichida) ──────────────────────────

_services: Dict[str, Any] = {}


def _amocrm():
    """AmoCRM klientini kech yaratamiz — import paytida tarmoqqa chiqmasin."""
    if "amocrm" not in _services:
        from src.services.core.crm.amocrm_sync import AmoCRMSync
        from src.settings import settings

        _services["amocrm"] = AmoCRMSync(
            subdomain=settings.AMOCRM_SUBDOMAIN,
            client_id=settings.AMOCRM_CLIENT_ID,
            # AmoCRMSync SecretStr'ni o'zi ochadi.
            client_secret=settings.AMOCRM_CLIENT_SECRET,
            redirect_url=settings.AMOCRM_REDIRECT_URL,
        )
    return _services["amocrm"]


def _airtable():
    if "airtable" not in _services:
        from src.services.core.airtable_sync import AirtableSync

        _services["airtable"] = AirtableSync()
    return _services["airtable"]


def _instagram():
    if "instagram" not in _services:
        from src.services.core.instagram_agent import InstagramGraphClient

        _services["instagram"] = InstagramGraphClient()
    return _services["instagram"]


def _as_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


@mcp.tool()
async def check_amo_auth() -> str:
    """AmoCRM avtorizatsiya holatini tekshirish va 401/403 xatolarini diagnostika qilish."""
    try:
        status = await _amocrm().get_account_status()
    except Exception as exc:
        logger.error("[MCP] check_amo_auth: %s", exc, exc_info=True)
        return f"Xato: {exc}"
    if status:
        return f"AUTH OK: {status.get('name')} (ID: {status.get('id')})"
    return "AUTH FAILED: token eskirgan yoki yaroqsiz. Yangi Authorization Code kerak."


@mcp.tool()
async def list_lost_leads() -> str:
    """AmoCRM'dagi 'Lost' (143) statusidagi bitimlar sonini olish."""
    import requests

    amocrm = _amocrm()
    url = (
        f"{amocrm.base_url}/api/v4/leads"
        "?filter[statuses][0][status_id]=143&limit=250"
    )
    try:
        resp = requests.get(url, headers=amocrm._get_headers(), timeout=30)
    except Exception as exc:
        logger.error("[MCP] list_lost_leads: %s", exc, exc_info=True)
        return f"Xato: {exc}"
    if resp.status_code != 200:
        return f"Bitimlarni olishda xato: {resp.status_code}"
    leads = resp.json().get("_embedded", {}).get("leads", [])
    return f"'Lost' (143) statusida {len(leads)} ta bitim topildi."


@mcp.tool()
async def create_amo_lead(name: str, phone: str, price: float = 0) -> str:
    """AmoCRM'da yangi bitim va kontakt yaratish."""
    try:
        lead_id = await _amocrm().create_lead(name, phone, price=price)
    except Exception as exc:
        logger.error("[MCP] create_amo_lead: %s", exc, exc_info=True)
        return f"Xato: {exc}"
    return (
        f"Bitim '{name}' AmoCRM'da yaratildi (ID: {lead_id})."
        if lead_id
        else "Bitim yaratilmadi."
    )


@mcp.tool()
async def get_sales_report() -> str:
    """AmoCRM'dan oylik sotuv hisobotini (Plan-Fakt) olish."""
    try:
        report = _amocrm().get_sales_report()
    except Exception as exc:
        logger.error("[MCP] get_sales_report: %s", exc, exc_info=True)
        return f"Xato: {exc}"
    return (
        f"Fakt: {report['fact']:,} so'm\n"
        f"Reja: {report['target']:,} so'm\n"
        f"Bajarilishi: {report['percent']:.1f}%"
    )


@mcp.tool()
async def get_airtable_projects() -> str:
    """Airtable'dan loyihalar ro'yxatini va muddatlarini olish."""
    try:
        projects = _airtable().get_projects()
    except Exception as exc:
        logger.error("[MCP] get_airtable_projects: %s", exc, exc_info=True)
        return f"Xato: {exc}"
    return f"Airtable'da {len(projects)} ta loyiha topildi."


@mcp.tool()
async def get_instagram_profile() -> str:
    """Ulangan Instagram Creator/Business profilini read-only olish."""
    try:
        return _as_json(_instagram().get_profile())
    except Exception as exc:
        logger.error("[MCP] get_instagram_profile: %s", exc, exc_info=True)
        return f"Xato: {exc}"


@mcp.tool()
async def list_instagram_recent_media(limit: int = 10) -> str:
    """Instagram akkauntining oxirgi postlarini read-only olish."""
    try:
        return _as_json(_instagram().list_media(limit=limit))
    except Exception as exc:
        logger.error("[MCP] list_instagram_recent_media: %s", exc, exc_info=True)
        return f"Xato: {exc}"


@mcp.tool()
async def get_instagram_latest_post() -> str:
    """Instagram akkauntidagi eng oxirgi post va uning sanasini olish."""
    try:
        result = _instagram().list_media(limit=5)
    except Exception as exc:
        logger.error("[MCP] get_instagram_latest_post: %s", exc, exc_info=True)
        return f"Xato: {exc}"

    if not result.get("ok"):
        return _as_json(result)

    media = result.get("data") or []
    latest = max(media, key=lambda item: item.get("timestamp") or "", default=None)
    return _as_json(
        {
            "ok": True,
            "username": latest.get("username") if latest else None,
            "latest_post": latest,
            "checked_count": len(media),
        }
    )


if __name__ == "__main__":
    mcp.run()
