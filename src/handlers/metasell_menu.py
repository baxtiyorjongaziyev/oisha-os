"""Telegram Bot Mini App Menu and Commands for Oisha Sales Cockpit.

Binds the interactive Oisha-OS Cockpit directly into the Telegram Bot menu via
Telegram WebApp (WebAppInfo), allowing sales managers, team leads, and ROPs
to launch the executive cockpit, AI sales simulator, and morning task triage
with a single tap without leaving Telegram.
"""
import logging
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import ContextTypes

from src.settings import settings

logger = logging.getLogger(__name__)


def build_telethon_cockpit_buttons(base_url: str | None = None) -> list[Any]:
    """Build Telethon-compatible Button list with WebApp URL for /start and menus."""
    try:
        from telethon import Button
    except ImportError:
        return []

    url = (base_url or getattr(settings, "WEBAPP_URL", "https://oisha.jonbranding.uz")).rstrip("/")
    return [
        [Button.url("🚀 Oisha Boshqaruv Markazi (Mini App)", f"{url}/metasell-console")],
        [
            Button.url("🎯 AI Simulyator", f"{url}/metasell-console#simulator"),
            Button.url("📋 Ertalabki Trijaj", f"{url}/metasell-console#tasks"),
        ],
    ]


async def configure_telegram_menu_button(
    bot_token: str | None = None,
    webapp_url: str | None = None,
) -> bool:
    """Set the Telegram bot bottom-left menu button to open Oisha WebApp."""
    token = bot_token or getattr(settings, "BOT_TOKEN", None)
    if hasattr(token, "get_secret_value"):
        token = token.get_secret_value()
    if not token:
        logger.warning("No bot token available to configure chat menu button")
        return False

    url = (webapp_url or getattr(settings, "WEBAPP_URL", "https://oisha.jonbranding.uz")).rstrip("/")
    api_url = f"https://api.telegram.org/bot{token}/setChatMenuButton"
    payload = {
        "menu_button": {
            "type": "web_app",
            "text": "🚀 Oisha Boshqaruv",
            "web_app": {"url": f"{url}/metasell-console"},
        }
    }
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(api_url, json=payload)
            if resp.status_code == 200 and resp.json().get("ok"):
                logger.info("Configured Telegram chat menu button to WebApp: %s", url)
                return True
            logger.warning("Telegram setChatMenuButton response not ok: %s", resp.text)
    except (ImportError, OSError, RuntimeError) as e:
        logger.warning("Error configuring Telegram chat menu button: %s", e)
    return False


def build_metasell_menu_keyboard(
    base_url: str | None = None,
    is_owner: bool = False,
    include_simulator: bool = True,
) -> InlineKeyboardMarkup:
    """Build Telegram InlineKeyboardMarkup containing WebApp buttons for Oisha Cockpit."""
    url = (base_url or getattr(settings, "WEBAPP_URL", "https://oisha.jonbranding.uz")).rstrip("/")

    buttons: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                "🚀 Oisha Boshqaruv Markazi (Mini App)",
                web_app=WebAppInfo(url=f"{url}/metasell-console"),
            )
        ]
    ]

    second_row: list[InlineKeyboardButton] = []
    if include_simulator:
        second_row.append(
            InlineKeyboardButton(
                "🎯 AI Savdo Simulyatori",
                web_app=WebAppInfo(url=f"{url}/metasell-console#simulator"),
            )
        )
    second_row.append(
        InlineKeyboardButton(
            "📋 Ertalabki Trijaj",
            web_app=WebAppInfo(url=f"{url}/metasell-console#tasks"),
        )
    )
    buttons.append(second_row)

    if is_owner:
        buttons.append(
            [
                InlineKeyboardButton(
                    "⚡ Tezkor ROP Xulosasi",
                    callback_data="metasell:summary",
                ),
                InlineKeyboardButton(
                    "📊 Reklama KPI",
                    web_app=WebAppInfo(url=f"{url}/metasell-console#ads"),
                ),
            ]
        )
    else:
        buttons.append(
            [
                InlineKeyboardButton(
                    "⚡ Tezkor ROP Xulosasi",
                    callback_data="metasell:summary",
                )
            ]
        )

    return InlineKeyboardMarkup(buttons)


def build_aiogram_metasell_keyboard(
    base_url: str | None = None,
    is_owner: bool = False,
) -> Any:
    """Construct an aiogram-compatible InlineKeyboardMarkup for Oisha WebApp."""
    try:
        from aiogram.types import InlineKeyboardButton as AiogramBtn
        from aiogram.types import InlineKeyboardMarkup as AiogramMarkup
        from aiogram.types import WebAppInfo as AiogramWebApp
    except ImportError:
        logger.warning("aiogram not installed, falling back to generic dict")
        return None

    url = (base_url or getattr(settings, "WEBAPP_URL", "https://oisha.jonbranding.uz")).rstrip("/")
    rows = [
        [
            AiogramBtn(
                text="🚀 Oisha Boshqaruv Markazi",
                web_app=AiogramWebApp(url=f"{url}/metasell-console"),
            )
        ],
        [
            AiogramBtn(
                text="🎯 AI Simulyator",
                web_app=AiogramWebApp(url=f"{url}/metasell-console#simulator"),
            ),
            AiogramBtn(
                text="📋 Ertalabki Trijaj",
                web_app=AiogramWebApp(url=f"{url}/metasell-console#tasks"),
            ),
        ],
        [
            AiogramBtn(
                text="⚡ Tezkor ROP Xulosasi",
                callback_data="metasell:summary",
            )
        ],
    ]
    return AiogramMarkup(inline_keyboard=rows)


def format_executive_digest(data: dict[str, Any]) -> str:
    """Format high-impact executive digest for Telegram chat message."""
    hero = data.get("hero", {})
    stl = data.get("speed_to_lead", {})
    stuck = data.get("stuck_deals", {})

    won_sum = hero.get("sales_won_amount", 0.0)
    won_sum_str = f"{won_sum / 1_000_000:.1f} mln" if won_sum else "0 mln"
    conv_rate = hero.get("conversion_rate_pct", 0.0)

    sla_pct = stl.get("sla_rate_pct", 0.0)
    unanswered = stl.get("unanswered_leads", 0)

    stuck_count = stuck.get("total_stuck_deals", 0)
    stuck_val = stuck.get("total_stuck_value", 0.0)
    stuck_val_str = f"{stuck_val / 1_000_000:.1f} mln" if stuck_val else "0 mln"

    return (
        "📊 <b>Oisha-OS — ROP Boshqaruv Xulosasi:</b>\n\n"
        f"🏆 <b>Yopilgan Savdo:</b> {won_sum_str} soʻm\n"
        f"📈 <b>Konversiya:</b> {conv_rate}%\n"
        f"⚡ <b>Speed to Lead (SLA):</b> {sla_pct}% (Kutayotganlar: {unanswered} ta)\n"
        f"⏳ <b>Qotib qolgan bitimlar:</b> {stuck_count} ta ({stuck_val_str} soʻm)\n\n"
        "Batafsil tahlil va topshiriqlarni koʻrish uchun pastdagi Mini App tugmasini bosing:"
    )


async def console_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /console and /cockpit command — send Telegram WebApp launcher keyboard."""
    if not update.effective_user or not update.message:
        return

    user_id = update.effective_user.id
    owner_id = getattr(settings, "OWNER_ID", 0)
    is_owner = str(user_id) == str(owner_id)

    reply_markup = build_metasell_menu_keyboard(is_owner=is_owner)
    text = (
        "💼 <b>Oisha-OS — Jon Branding Savdo va Boshqaruv Markaziga xush kelibsiz!</b>\n\n"
        "Sotuv voronkasi, qotib qolgan bitimlar, reklama konversiyasi va "
        "AI savdo simulyatorini toʻgʻridan-toʻgʻri Telegram ichida oching."
    )
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML")


async def cockpit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Alias for /cockpit command."""
    await console_command(update, context)


async def simulator_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /simulator command — direct launcher for AI sales practice."""
    if not update.message:
        return

    base_url = getattr(settings, "WEBAPP_URL", "https://oisha.jonbranding.uz").rstrip("/")
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🎯 Simulyatorni Boshlash (Mini App)",
                    web_app=WebAppInfo(url=f"{base_url}/metasell-console#simulator"),
                )
            ]
        ]
    )
    await update.message.reply_text(
        "🎧 <b>AI Savdo Simulyatori:</b>\n\n"
        "Mijoz eʼtirozlari bilan ishlash, narx muzokaralari va ehtiyojni aniqlash "
        "boʻyicha real ovozli mashgʻulotlarni boshlang.",
        reply_markup=keyboard,
        parse_mode="HTML",
    )


async def morning_triage_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /triage command — direct launcher for morning priorities."""
    if not update.message:
        return

    base_url = getattr(settings, "WEBAPP_URL", "https://oisha.jonbranding.uz").rstrip("/")
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📋 Ertalabki Vazifalarni Boshlash",
                    web_app=WebAppInfo(url=f"{base_url}/metasell-console#tasks"),
                )
            ]
        ]
    )
    await update.message.reply_text(
        "☀️ <b>Ertalabki Trijaj va Prioritetlar:</b>\n\n"
        "Bugungi muhim qoʻngʻiroqlar, muddati oʻtgan vazifalar va "
        "diqqat talab bitimlarni saralash uchun quyidagi tugmani bosing.",
        reply_markup=keyboard,
        parse_mode="HTML",
    )


async def handle_metasell_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline callback query for instant ROP summary."""
    query = update.callback_query
    if not query:
        return

    await query.answer()
    if query.data == "metasell:summary":
        sample_metrics = {
            "hero": {"sales_won_amount": 62_000_000.0, "conversion_rate_pct": 28.5},
            "speed_to_lead": {"sla_rate_pct": 74.2, "unanswered_leads": 3},
            "stuck_deals": {"total_stuck_deals": 5, "total_stuck_value": 115_000_000.0},
        }
        digest = format_executive_digest(sample_metrics)
        base_url = getattr(settings, "WEBAPP_URL", "https://oisha.jonbranding.uz").rstrip("/")
        mini_markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🔍 Toʻliq Hisobotni Ochish",
                        web_app=WebAppInfo(url=f"{base_url}/metasell-console"),
                    )
                ]
            ]
        )
        await query.message.reply_text(digest, reply_markup=mini_markup, parse_mode="HTML")
