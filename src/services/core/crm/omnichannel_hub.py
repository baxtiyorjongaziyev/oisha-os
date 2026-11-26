"""Omnichannel Messenger Hub for Jon CRM (Telegram & Instagram Native Direct).

Ushbu modul Wazzup/ChatApp o'rniga to'g'ridan-to'g'ri Meta Graph API
va Telegram orqali barcha kiruvchi va chiquvchi xabarlarni bitta
yagona aloqa markazida (Unified Inbox) saqlaydi va boshqaradi.
"""
from __future__ import annotations

from datetime import datetime
import json
import logging
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional
import urllib.request

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = "data/crm_dialer.db"


class OmnichannelHub:
    """Manages conversations, threads and message routing across Instagram and Telegram."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH) -> None:
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS crm_chat_threads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lead_id INTEGER,
                    channel TEXT NOT NULL,
                    external_user_id TEXT NOT NULL,
                    contact_name TEXT,
                    username TEXT,
                    phone TEXT,
                    last_message TEXT,
                    unread_count INTEGER DEFAULT 0,
                    responsible_name TEXT DEFAULT 'Shahnoza Abdijabborova',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(channel, external_user_id)
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS crm_chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id INTEGER NOT NULL,
                    direction TEXT NOT NULL,
                    sender_name TEXT,
                    text TEXT NOT NULL,
                    media_url TEXT,
                    status TEXT DEFAULT 'delivered',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(thread_id) REFERENCES crm_chat_threads(id)
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_threads_lead ON crm_chat_threads(lead_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_msg_thread ON crm_chat_messages(thread_id);")

    def ingest_incoming_message(
        self,
        channel: str,
        external_user_id: str,
        text: str,
        sender_name: Optional[str] = None,
        username: Optional[str] = None,
        phone: Optional[str] = None,
        media_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record an inbound message from Instagram Direct or Telegram."""
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, lead_id FROM crm_chat_threads WHERE channel = ? AND external_user_id = ?",
                (channel, external_user_id),
            )
            row = cur.fetchone()
            lead_id: Optional[int] = None
            if row:
                thread_id = row["id"]
                lead_id = row["lead_id"]
                cur.execute(
                    """
                    UPDATE crm_chat_threads
                    SET last_message = ?, unread_count = unread_count + 1, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (text, thread_id),
                )
            else:
                # Avtomatik bitim qidirish (telefon yoki ism bo'yicha)
                if phone:
                    lrow = cur.execute("SELECT id FROM dialer_leads WHERE phone LIKE ? LIMIT 1", (f"%{phone[-9:]}%",)).fetchone()
                    if lrow:
                        lead_id = lrow[0]
                cur.execute(
                    """
                    INSERT INTO crm_chat_threads (
                        lead_id, channel, external_user_id, contact_name, username, phone, last_message, unread_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                    """,
                    (lead_id, channel, external_user_id, sender_name or username or "Mijoz", username, phone, text),
                )
                thread_id = cur.lastrowid

            cur.execute(
                """
                INSERT INTO crm_chat_messages (thread_id, direction, sender_name, text, media_url)
                VALUES (?, 'in', ?, ?, ?)
                """,
                (thread_id, sender_name or "Mijoz", text, media_url),
            )
            conn.commit()

        return {"thread_id": thread_id, "lead_id": lead_id, "status": "ingested"}

    def get_threads_list(self, limit: int = 60) -> List[Dict[str, Any]]:
        """Fetch list of active conversations for imBox."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM crm_chat_threads ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_thread_messages(self, thread_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """Fetch message history for single conversation."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM crm_chat_messages WHERE thread_id = ? ORDER BY id ASC LIMIT ?", (thread_id, limit)
            ).fetchall()
            return [dict(r) for r in rows]

    async def _send_telegram_direct_message(self, recipient: str, text: str) -> bool:
        """Send message directly to client via Telethon Userbot or Bot runtime."""
        if not recipient or not text:
            return False
        clean_target = str(recipient).strip()
        # 1. Telethon Userbot orqali yuborish (shaxsiy / korporativ akkaunt)
        try:
            from src.context import app_ctx
            client = getattr(app_ctx, "client", None)
            if client and client.is_connected():
                # Agar telefon raqam bo'lsa va + bo'lsa
                clean_phone = clean_target.replace(" ", "").replace("-", "")
                if clean_phone.startswith("+") or (clean_phone.isdigit() and len(clean_phone) >= 9):
                    from src.services.core.telegram.temp_contacts import (
                        delete_temp_contact,
                        import_temp_contact,
                    )

                    temp_user = None
                    newly_imported = False
                    try:
                        temp_user, newly_imported = await import_temp_contact(client, clean_phone)
                        if temp_user:
                            await client.send_message(temp_user, text)
                            logger.info("[OMNICHANNEL] Telegram sent via Userbot to contact: %s", clean_phone)
                            return True
                    except Exception as c_err:
                        logger.debug("[OMNICHANNEL] Userbot contact import fallback: %s", c_err)
                    finally:
                        if newly_imported and temp_user is not None:
                            await delete_temp_contact(client, getattr(temp_user, "id", None))

                target = int(clean_target) if clean_target.lstrip("-").isdigit() else clean_target
                await client.send_message(target, text)
                logger.info("[OMNICHANNEL] Telegram sent via Userbot to %s", clean_target)
                return True
        except Exception as exc:
            logger.warning("[OMNICHANNEL] Telegram Userbot send failed for %s: %s", clean_target, exc)

        # 2. Bot runtime orqali fallback
        try:
            from src.context import app_ctx
            bot_runtime = getattr(app_ctx, "bot_runtime", None)
            if bot_runtime:
                target = int(clean_target) if clean_target.lstrip("-").isdigit() else clean_target
                await bot_runtime.send_message(target, text)
                logger.info("[OMNICHANNEL] Telegram sent via Bot runtime to %s", clean_target)
                return True
        except Exception as b_exc:
            logger.warning("[OMNICHANNEL] Telegram Bot runtime fallback failed: %s", b_exc)

        return False

    async def send_outbound_reply_async(
        self,
        lead_id: Optional[int] = None,
        thread_id: Optional[int] = None,
        channel: str = "Telegram",
        text: str = "",
        sender_name: str = "Shahnoza Abdijabborova",
        target_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send message directly to client via Telegram (Userbot/Bot) or Meta Graph API."""
        with self._get_conn() as conn:
            cur = conn.cursor()
            thread = None
            if thread_id:
                thread = cur.execute("SELECT * FROM crm_chat_threads WHERE id = ?", (thread_id,)).fetchone()
            elif lead_id:
                thread = cur.execute(
                    "SELECT * FROM crm_chat_threads WHERE lead_id = ? AND channel = ? LIMIT 1",
                    (lead_id, channel),
                ).fetchone()

            if not thread:
                ext_id = target_override or ""
                c_name = "Mijoz"
                phone_val = ""
                u_name = ""
                if lead_id:
                    lrow = cur.execute(
                        "SELECT name, contact_name, phone, custom_fields FROM dialer_leads WHERE id = ?",
                        (lead_id,),
                    ).fetchone()
                    if lrow:
                        c_name = lrow["contact_name"] or lrow["name"] or "Mijoz"
                        phone_val = lrow["phone"] or ""
                        try:
                            cf = json.loads(lrow["custom_fields"]) if lrow["custom_fields"] else {}
                        except Exception:
                            cf = {}
                        u_name = cf.get("telegram_username") or ""
                        if not ext_id:
                            ext_id = u_name or phone_val or f"lead_{lead_id}"
                if not ext_id:
                    ext_id = f"lead_{lead_id or 0}_{int(time.time())}"

                cur.execute(
                    """
                    INSERT INTO crm_chat_threads (
                        lead_id, channel, external_user_id, contact_name, username, phone, last_message, unread_count, responsible_name
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
                    """,
                    (lead_id, channel, ext_id, c_name, u_name, phone_val, text, sender_name),
                )
                actual_thread_id = cur.lastrowid
                conn.commit()
                thread = cur.execute("SELECT * FROM crm_chat_threads WHERE id = ?", (actual_thread_id,)).fetchone()

            actual_thread_id = thread["id"]
            channel_name = thread["channel"]
            ext_id = thread["external_user_id"]
            phone_val = thread["phone"] or ""
            u_name = thread["username"] or ""

            sent_ok = False
            if "Instagram" in channel_name:
                sent_ok = self._send_meta_direct_message(recipient_id=ext_id, text=text)
            elif "Telegram" in channel_name:
                recipient = target_override or u_name or phone_val or ext_id
                sent_ok = await self._send_telegram_direct_message(recipient=recipient, text=text)

            cur.execute(
                """
                INSERT INTO crm_chat_messages (thread_id, direction, sender_name, text, status)
                VALUES (?, 'out', ?, ?, ?)
                """,
                (actual_thread_id, sender_name, text, "sent" if sent_ok else "delivered"),
            )
            cur.execute(
                "UPDATE crm_chat_threads SET last_message = ?, unread_count = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (text, actual_thread_id),
            )
            conn.commit()

        return {"success": True, "sent": sent_ok, "thread_id": actual_thread_id, "channel": channel_name}

    def send_outbound_reply(
        self,
        thread_id: int,
        text: str,
        sender_name: str = "Shahnoza Abdijabborova",
    ) -> Dict[str, Any]:
        """Send message directly to client via Meta Graph API or Telegram."""
        with self._get_conn() as conn:
            cur = conn.cursor()
            thread = cur.execute("SELECT * FROM crm_chat_threads WHERE id = ?", (thread_id,)).fetchone()
            if not thread:
                return {"error": "Thread topilmadi"}

            channel = thread["channel"]
            ext_id = thread["external_user_id"]

            sent_ok = False
            if channel == "Instagram Direct":
                sent_ok = self._send_meta_direct_message(recipient_id=ext_id, text=text)
            else:
                sent_ok = True

            cur.execute(
                """
                INSERT INTO crm_chat_messages (thread_id, direction, sender_name, text, status)
                VALUES (?, 'out', ?, ?, ?)
                """,
                (thread_id, sender_name, text, "sent" if sent_ok else "pending"),
            )
            cur.execute(
                "UPDATE crm_chat_threads SET last_message = ?, unread_count = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (text, thread_id),
            )
            conn.commit()

        return {"success": True, "sent": sent_ok}

    def _send_meta_direct_message(self, recipient_id: str, text: str) -> bool:
        """Send message via Meta Graph API without external intermediary."""
        token = os.getenv("META_PAGE_ACCESS_TOKEN", "").strip()
        page_id = os.getenv("META_PAGE_ID", "103894334533931").strip()
        if not token:
            logger.warning("[OMNICHANNEL] META_PAGE_ACCESS_TOKEN mavjud emas.")
            return False

        url = f"https://graph.facebook.com/v19.0/{page_id}/messages"
        if not url.startswith("https://graph.facebook.com/"):
            return False

        payload = json.dumps({
            "recipient": {"id": recipient_id},
            "message": {"text": text},
            "messaging_type": "RESPONSE",
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{url}?access_token={token}",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310
                return resp.status == 200
        except Exception as exc:
            logger.error("[OMNICHANNEL] Meta send failed: %s", exc)
            return False
