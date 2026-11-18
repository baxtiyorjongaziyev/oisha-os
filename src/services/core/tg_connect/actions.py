"""Yozish amallari navbati: avtonom chatlarda darhol, qolganida menejer tasdigʻi bilan.

Oqim: MCP ``tools/call`` → ``submit`` → (avtonom boʻlsa) ``execute`` darhol, aks holda
``pending`` + Oisha botida menejerga Tasdiqlash/Rad etish tugmalari. Tugmani faqat
oʻsha menejer bosa oladi (bot handler ``decide`` ga ``telegram_id`` beradi).
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Awaitable, Callable, Optional

from src.services.core.tg_connect import store, write_ops

logger = logging.getLogger(__name__)
TTL_S = 3600  # tasdiqlanmagan amal 1 soatdan keyin eskiradi
CB_PREFIX = "tgca:"

DDL = (
    """CREATE TABLE IF NOT EXISTS tg_connect_actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER NOT NULL,
        kind TEXT NOT NULL,
        payload TEXT NOT NULL,
        state TEXT NOT NULL,
        result TEXT,
        source TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        decided_at INTEGER)""",
    "CREATE INDEX IF NOT EXISTS idx_tgc_actions_tg ON tg_connect_actions(telegram_id, id)",
)

Notify = Callable[[int, int, str], Awaitable[bool]]


def quiet_hours(now: Optional[datetime] = None) -> bool:
    """``agent_policy`` qoidasi: 23:00–07:00 Toshkent — avtomatik yozish yoʻq."""
    t = (now or datetime.now(ZoneInfo("Asia/Tashkent"))).astimezone(ZoneInfo("Asia/Tashkent"))
    return t.hour >= 23 or t.hour < 7


async def init_tables(db) -> None:
    for ddl in DDL:
        await db.execute(ddl)
    await db.commit()


def buttons(action_id: int) -> dict:
    return {"inline_keyboard": [[
        {"text": "✅ Tasdiqlash", "callback_data": f"{CB_PREFIX}ok:{action_id}"},
        {"text": "❌ Rad etish", "callback_data": f"{CB_PREFIX}no:{action_id}"}]]}


async def bot_notify(telegram_id: int, action_id: int, text: str) -> bool:
    """Bot API ga HTTP: API jarayoni bot jarayonidan alohida ishlaydi."""
    import httpx

    from src.settings import settings

    token = settings.BOT_TOKEN.get_secret_value() if hasattr(settings.BOT_TOKEN, "get_secret_value") \
        else str(settings.BOT_TOKEN or "")
    if not token:
        logger.warning("tg_connect approval not sent: BOT_TOKEN missing")
        return False
    body = {"chat_id": telegram_id, "text": "🤖 AI sizning nomingizdan amal soʻrayapti:\n\n" + text,
            "reply_markup": buttons(action_id), "disable_web_page_preview": True}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(f"https://api.telegram.org/bot{token}/sendMessage", json=body)
        return resp.status_code == 200 and resp.json().get("ok") is True
    except Exception as exc:  # noqa: BLE001
        logger.warning("tg_connect approval notify failed: %s", type(exc).__name__)
        return False


async def _session(db, tg: int) -> str:
    acc = await store.account(db, tg)
    if not acc or acc.get("status") != "connected" or not acc.get("session_enc"):
        raise write_ops.WriteError("Oisha Connect is not connected")
    return store.decrypt_session(tg, acc["session_enc"])


async def _run(db, tg: int, action_id: int, kind: str, payload: dict, executor) -> dict:
    try:
        result = await executor(await _session(db, tg), kind, payload)
        state = "done"
    except write_ops.WriteError as e:
        result, state = {"error": str(e)}, "failed"
    except Exception as e:  # noqa: BLE001 - Telegram xato matni tashqariga chiqarilmaydi
        result, state = {"error": f"telegram_error:{type(e).__name__}"}, "failed"
    await db.execute("UPDATE tg_connect_actions SET state = ?, result = ?, decided_at = ? WHERE id = ?",
                     [state, json.dumps(result), int(time.time()), action_id])
    await db.commit()
    await store.audit(db, tg, f"write_{state}", "mcp", {"kind": kind, "action": action_id,
                                                         "chat": payload.get("chat_id")})
    return {"state": state, **result}


async def submit(db, tg: int, kind: str, payload: dict, *, autonomous: bool, titles: dict[int, str],
                 source: str = "mcp", notify: Optional[Notify] = None,
                 executor=write_ops.execute) -> dict:
    if autonomous and quiet_hours():
        autonomous = False  # tunda ⚡ chat ham menejer tasdigʻisiz yozmaydi
    now = int(time.time())
    rows = await db.execute(
        "INSERT INTO tg_connect_actions (telegram_id, kind, payload, state, source, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?) RETURNING id",
        [tg, kind, json.dumps(payload, ensure_ascii=False), "approved" if autonomous else "pending", source, now])
    await db.commit()
    action_id = int(rows[0]["id"])
    if autonomous:
        return {"action_id": action_id, **await _run(db, tg, action_id, kind, payload, executor)}
    sent = await (notify or bot_notify)(tg, action_id, write_ops.describe(kind, payload, titles))
    await store.audit(db, tg, "write_pending", source, {"kind": kind, "action": action_id})
    return {"action_id": action_id, "state": "pending_approval", "notified": sent,
            "note": "The manager must approve this in the Oisha bot. Call get_action_status later."}


async def get(db, tg: int, action_id: int) -> Optional[dict]:
    rows = await db.execute("SELECT id, kind, state, result, created_at FROM tg_connect_actions"
                            " WHERE id = ? AND telegram_id = ?", [action_id, tg])
    if not rows:
        return None
    r = dict(rows[0])
    if r["state"] == "pending" and time.time() - r["created_at"] > TTL_S:
        r["state"] = "expired"
    return {"action_id": r["id"], "kind": r["kind"], "state": r["state"],
            "result": json.loads(r["result"]) if r["result"] else None}


async def decide(db, tg: int, action_id: int, approve: bool, executor=write_ops.execute) -> dict:
    """Bot tugmasi: faqat amal egasi (``tg``) va faqat ``pending`` holatda."""
    rows = await db.execute(
        "UPDATE tg_connect_actions SET state = ?, decided_at = ? WHERE id = ? AND telegram_id = ?"
        " AND state = 'pending' AND created_at > ? RETURNING kind, payload",
        ["approved" if approve else "rejected", int(time.time()), action_id, tg, int(time.time()) - TTL_S])
    await db.commit()
    if not rows:
        return {"state": "not_pending"}
    kind, payload = rows[0]["kind"], json.loads(rows[0]["payload"])
    if not approve:
        await store.audit(db, tg, "write_rejected", f"bot:{tg}", {"kind": kind, "action": action_id})
        return {"state": "rejected"}
    return await _run(db, tg, action_id, kind, payload, executor)
