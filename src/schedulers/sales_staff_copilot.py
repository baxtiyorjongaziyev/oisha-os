"""Sales staff AI copilot and hourly check-in handler for Oisha-OS.

Supports remote sales staff (specifically @RayxonJonbranding) by:
1. Automatically discovering, capturing, and binding staff numeric Telegram user_id.
2. Introducing Oisha warmly upon first contact and establishing the copilot role.
3. Intercepting replies to hourly check-ins or sales assistance inquiries.
4. Generating expert sales coaching and client-objection scripts via Hermes.
5. Persisting hourly status and assistance logs in team_reports database.
"""
from __future__ import annotations

import datetime
import logging
import sqlite3
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("SalesStaffCopilot")

SALES_COACH_SYSTEM_PROMPT = (
    "Sen — Jon Branding agentligining Bosh Sotuv Murabbiyi (Senior Sales Coach) "
    "va Baxtiyorjon Gaziyevning AI assistentisan.\n"
    "Masofadan (online) ishlayotgan sotuv menejerimiz Rayxon (@RayxonJonbranding) "
    "o'zining soatlik hisobotini yoki mijoz bilan muloqotdagi holatini yozdi.\n\n"
    "SENING ASOSIY VAZIFALARING:\n"
    "1. Agar Rayxon mijoz e'tirozi (narx qimmat, o'ylab ko'raman, boshqa agentlik arzonroq, "
    "qaror qabul qiluvchi yo'q, shartnoma cho'zilyapti) yoki biror qiyinchilik haqida yozgan bo'lsa:\n"
    "   - Unga aniq, psixologik jihatdan puxta va darhol mijozga yuborish/aytish mumkin bo'lgan "
    "tayyor javob skriptini taqdim et.\n"
    "   - Tashabbusni sotuvchi qo'lida ushlab qoluvchi ochiq savollarni ko'rsat.\n"
    "2. Agar Rayxon ijobiy natija yoki oddiy reja bo'yicha ishlayotganini yozgan bo'lsa "
    "(masalan: 3 ta mijozga taklif yubordim, hozir yangi lidlarga qo'ng'iroq qilyapman):\n"
    "   - Uni samimiy maqtang, kuch bering va keyingi qadam bo'yicha kichik taktik maslahat bering "
    "(masalan: taklif yuborilgach, 2 soat ichida qayta aloqaga chiqishni unutmang).\n"
    "3. Suhbat uslubi:\n"
    "   - O'zbek tilida, juda samimiy, do'stona, hurmat bilan ('Rayxon', 'Siz' deb murojaat qil), "
    "lekin qat'iy professional va natijaga yo'naltirilgan bo'lsin.\n"
    "   - Qisqa va amaliy (ortiqcha nazariya yo'q, 2-3 ta ixcham xatboshi).\n"
    "4. Hech qachon soxta ma'lumot, yolg'on va'da yoki to'qima narx aytma."
)

DEFAULT_RULE_BASED_ADVICE = (
    "Rayxon, ajoyib temp! Agar mijoz o'ylab ko'raman desa — "
    "«Albatta, o'ylab ko'ring. Lekin qaror qabul qilishingiz uchun aynan qaysi jihat (narx, muddat yoki xizmat tarkibi) "
    "bo'yicha qo'shimcha ma'lumot beray?» deb ochiq savol bering. "
    "Yangi lidlar bo'yicha qiyinchilik bo'lsa darhol yozing, birga yopamiz! 🤝"
)


def build_staff_intro_message(rep_name: str, user_id: int) -> str:
    """Warm introductory greeting from Oisha to the remote staff member."""
    clean_name = rep_name or "Rayxon"
    return (
        f"👋 <b>Assalomu alaykum {clean_name}! Tanishganimdan juda xursandman 🤝</b>\n\n"
        f"Men — <b>Oisha</b>, sizning shaxsiy AI assistentingiz va sotuv copilotingizman. "
        f"Profilingizni avtomatik tanib, tizimga bog'lab oldim (Telegram ID: <code>{user_id}</code>).\n\n"
        f"Endi har soatda siz bilan birga ishlaymiz:\n"
        f"• Qaysi mijozlar bilan muloqot qilganingizni aniqlab, natijalarni qayd qilib boraman.\n"
        f"• Mijoz e'tirozlari (narx qimmat, o'ylab ko'raman, ikkilanish) bo'yicha kuchli javob skriptlarini beraman.\n"
        f"• Bitimlarni tezroq va osonroq yopishingizda yordamlashaman.\n\n"
        f"Savol yoki yordam kerak bo'lsa, istalgan paytda menga yozishingiz mumkin! Bugungi rejalarni birga bajaramiz! 🚀"
    )


def get_known_staff_user_id(
    username: str = "RayxonJonbranding",
    db_path: str = "data/bot.db",
) -> Optional[int]:
    """Retrieve already bound numeric Telegram user_id for staff username."""
    clean_uname = username.lstrip("@").lower()
    try:
        conn = sqlite3.connect(db_path, timeout=5.0)
        c = conn.cursor()
        c.execute(
            "SELECT user_id FROM users WHERE lower(username) = ? LIMIT 1",
            (clean_uname,),
        )
        row = c.fetchone()
        if row and row[0]:
            conn.close()
            return int(row[0])

        c.execute("SELECT value FROM kv_settings WHERE key = 'STAFF_USER_ID_RAYXON' LIMIT 1")
        row = c.fetchone()
        conn.close()
        if row and row[0]:
            return int(row[0])
    except Exception as exc:
        logger.debug("[COPILOT] Error retrieving staff user_id: %s", exc)
    return None


def bind_and_welcome_staff(
    user_id: int,
    username: str,
    first_name: str,
    db_path: str = "data/bot.db",
    dialer_db_path: str = "data/crm_dialer.db",
) -> Tuple[bool, str]:
    """Auto-bind Telegram user_id, upsert user/seller records, and return intro message if new."""
    if not user_id:
        return False, ""

    clean_uname = (username or "").lstrip("@")
    clean_first = first_name or "Rayxon"
    now_iso = datetime.datetime.now().isoformat()
    is_new_intro = False

    try:
        conn = sqlite3.connect(db_path, timeout=5.0)
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO users (user_id, username, first_name, role, position, created_at)
            VALUES (?, ?, ?, 'closer', 'Sotuv menejeri (Closer)', ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = COALESCE(excluded.first_name, users.first_name),
                role = 'closer',
                position = 'Sotuv menejeri (Closer)'
            """,
            (user_id, clean_uname, clean_first, now_iso),
        )

        c.execute(
            """
            INSERT OR REPLACE INTO kv_settings (key, value, updated_at)
            VALUES ('STAFF_USER_ID_RAYXON', ?, ?)
            """,
            (str(user_id), now_iso),
        )

        intro_key = f"STAFF_INTRO_SENT_{user_id}"
        c.execute("SELECT value FROM kv_settings WHERE key = ? LIMIT 1", (intro_key,))
        row = c.fetchone()
        if not row:
            c.execute(
                "INSERT OR REPLACE INTO kv_settings (key, value, updated_at) VALUES (?, '1', ?)",
                (intro_key, now_iso),
            )
            is_new_intro = True

        conn.commit()
        conn.close()
        logger.info("[COPILOT] Bound staff user_id=%s (@%s), is_new_intro=%s", user_id, clean_uname, is_new_intro)
    except Exception as exc:
        logger.warning("[COPILOT] Error binding staff user_id: %s", exc)

    try:
        conn_d = sqlite3.connect(dialer_db_path, timeout=5.0)
        c_d = conn_d.cursor()
        c_d.execute(
            """
            UPDATE crm_seller_accounts
            SET tg = ?
            WHERE slug = 'rayxona' OR lower(tg) LIKE '%rayxon%'
            """,
            (f"@{clean_uname}" if clean_uname else "@RayxonJonbranding",),
        )
        conn_d.commit()
        conn_d.close()
    except Exception as exc:
        logger.debug("[COPILOT] Dialer accounts update notice: %s", exc)

    if is_new_intro:
        return True, build_staff_intro_message(clean_first, user_id)
    return False, ""


async def auto_resolve_staff_id(
    client: Any = None,
    username: str = "RayxonJonbranding",
    db_path: str = "data/bot.db",
) -> Optional[int]:
    """Proactively resolve staff user_id via Telethon client entity lookup if available."""
    clean_uname = username.lstrip("@")
    known_id = get_known_staff_user_id(clean_uname, db_path=db_path)
    if known_id:
        return known_id

    if client is not None and hasattr(client, "get_entity"):
        try:
            entity = await client.get_entity(f"@{clean_uname}")
            if entity and getattr(entity, "id", None):
                uid = int(entity.id)
                fname = getattr(entity, "first_name", "Rayxon")
                bind_and_welcome_staff(uid, clean_uname, fname, db_path=db_path)
                logger.info("[COPILOT] Auto-resolved entity for @%s -> user_id=%s", clean_uname, uid)
                return uid
        except Exception as exc:
            logger.debug("[COPILOT] Proactive get_entity for @%s skipped/unavailable: %s", clean_uname, exc)

    return None


def is_checkin_interaction(
    text: str,
    reply_to_text: Optional[str] = None,
    username: Optional[str] = None,
) -> bool:
    """True if message is a reply to check-in or from sales rep asking assistance."""
    uname = (username or "").lstrip("@").lower()
    is_rayxon = uname in {"rayxonjonbranding", "rayxona"}

    if reply_to_text:
        low_reply = reply_to_text.lower()
        if "soatlik check-in" in low_reply or "check-in" in low_reply:
            return True
        if "@rayxonjonbranding" in low_reply:
            return True

    if is_rayxon:
        low_text = text.lower()
        triggers = [
            "mijoz", "gaplashdim", "qongiroq", "qo'ng'iroq", "narx",
            "taklif", "yordam", "skript", "blok", "lid", "amocrm",
            "yopildi", "e'tiroz", "etiroz", "shartnoma"
        ]
        if any(trig in low_text for trig in triggers):
            return True

    return False


def save_checkin_report(
    rep_name: str,
    rep_username: str,
    report_text: str,
    advice_text: str,
    db_path: str = "data/bot.db",
) -> bool:
    """Save staff status report into team_reports table."""
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    now_iso = datetime.datetime.now().isoformat()
    content = f"Hisobot: {report_text}\n\nAI Maslahat: {advice_text}"
    user_identifier = rep_username if rep_username else rep_name

    try:
        conn = sqlite3.connect(db_path, timeout=5.0)
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO team_reports (user_id, report_date, report_type, content, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_identifier, today, "hourly_checkin", content, "processed", now_iso),
        )
        conn.commit()
        conn.close()
        logger.info("[COPILOT] Saved checkin report for %s", user_identifier)
        return True
    except Exception as exc:
        logger.warning("[COPILOT] Failed to save team_report: %s", exc)
        return False


async def generate_copilot_advice(
    rep_name: str,
    report_text: str,
) -> str:
    """Generate sales coach advice via Hermes or fallback router."""
    clean_prompt = (
        f"Sotuv menejeri {rep_name} (@RayxonJonbranding) quyidagi soatlik hisobotni berdi:\n"
        f"\"{report_text}\"\n\n"
        f"Unga sotuv bo'yicha aniq maslahat, mijoz bilan muloqot skripti va ruhiy quvvat ber."
    )

    try:
        from src.services.core.ai.hermes_provider import get_hermes_provider
        hermes = get_hermes_provider()
        if hermes.is_available():
            reply = await hermes.generate_response(
                prompt=clean_prompt,
                system_instruction=SALES_COACH_SYSTEM_PROMPT,
                timeout=60,
            )
            if reply and len(reply.strip()) > 20:
                return reply.strip()
    except Exception as exc:
        logger.debug("[COPILOT] Hermes generation fallback: %s", exc)

    try:
        from src.services.utils.free_ai_router import FreeAIProviderRouter
        router = FreeAIProviderRouter()
        res = await router.get_text(
            prompt=clean_prompt,
            system_instruction=SALES_COACH_SYSTEM_PROMPT,
        )
        if res and res.content and len(res.content.strip()) > 20:
            return res.content.strip()
    except Exception as exc:
        logger.debug("[COPILOT] FreeAIProvider fallback: %s", exc)

    return DEFAULT_RULE_BASED_ADVICE


def format_copilot_reply(advice: str, rep_name: str = "Rayxon") -> str:
    """Format copilot advice with clear visual markers for Telegram."""
    lines = [
        f"💡 <b>Sotuv Copilot (Oisha):</b>",
        "",
        advice.strip(),
    ]
    return "\n".join(lines)


async def handle_sales_staff_interaction(
    rep_name: str,
    rep_username: str,
    message_text: str,
    db_path: str = "data/bot.db",
) -> str:
    """Orchestrate copilot advice generation, persistence, and formatting."""
    advice = await generate_copilot_advice(rep_name, message_text)
    save_checkin_report(rep_name, rep_username, message_text, advice, db_path=db_path)
    return format_copilot_reply(advice, rep_name)
