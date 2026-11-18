"""Menejer sessiyasi bilan yozish amallari (Telethon). Faqat ``actions`` orqali chaqiriladi.

Har bir amal oldindan tekshirilgan ``payload`` oladi; bu yerda faqat bajariladi.
"""
from __future__ import annotations

from typing import Any, Callable
from urllib.parse import urlparse

from src.services.core.tg_connect.session_ops import SessionClientFactory, default_session_client

MAX_TEXT = 4096
MAX_IDS = 100
KINDS = ("send_message", "forward_messages", "edit_message", "delete_messages", "send_file")


class WriteError(ValueError):
    pass


def _text(v: Any) -> str:
    if not isinstance(v, str) or not v.strip():
        raise WriteError("text is required")
    if len(v) > MAX_TEXT:
        raise WriteError(f"text longer than {MAX_TEXT}")
    return v


def _ids(v: Any) -> list[int]:
    if not isinstance(v, list) or not v or len(v) > MAX_IDS:
        raise WriteError(f"message_ids must be a list of 1..{MAX_IDS} integers")
    try:
        return [int(x) for x in v]
    except (TypeError, ValueError):
        raise WriteError("message_ids must be integers")


def _int(v: Any, name: str) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        raise WriteError(f"{name} must be an integer")


def _url(v: Any) -> str:
    u = urlparse(v if isinstance(v, str) else "")
    if u.scheme != "https" or not u.netloc:
        raise WriteError("file_url must be an https:// URL")
    return v


def validate(kind: str, args: dict) -> dict:
    """MCP argumentlaridan toza ``payload`` va taʼsir qiladigan chatlar roʻyxati."""
    if kind == "send_message":
        p = {"chat_id": _int(args.get("chat_id"), "chat_id"), "text": _text(args.get("text"))}
        if args.get("reply_to") is not None:
            p["reply_to"] = _int(args.get("reply_to"), "reply_to")
    elif kind == "forward_messages":
        p = {"from_chat_id": _int(args.get("from_chat_id"), "from_chat_id"),
             "chat_id": _int(args.get("to_chat_id"), "to_chat_id"), "message_ids": _ids(args.get("message_ids"))}
    elif kind == "edit_message":
        p = {"chat_id": _int(args.get("chat_id"), "chat_id"), "message_id": _int(args.get("message_id"), "message_id"),
             "text": _text(args.get("text"))}
    elif kind == "delete_messages":
        p = {"chat_id": _int(args.get("chat_id"), "chat_id"), "message_ids": _ids(args.get("message_ids"))}
    elif kind == "send_file":
        caption = args.get("caption")
        p = {"chat_id": _int(args.get("chat_id"), "chat_id"), "file_url": _url(args.get("file_url")),
             "caption": _text(caption) if caption else "", "voice": bool(args.get("as_voice"))}
    else:
        raise WriteError(f"unknown action: {kind}")
    return p


def chats_of(kind: str, payload: dict) -> list[int]:
    return [payload["from_chat_id"], payload["chat_id"]] if kind == "forward_messages" else [payload["chat_id"]]


def describe(kind: str, p: dict, titles: dict[int, str]) -> str:
    """Tasdiq xabari uchun qisqa, odam oʻqiydigan tavsif (oʻzbekcha)."""
    chat = titles.get(p["chat_id"], str(p["chat_id"]))
    if kind == "send_message":
        head = f"✉️ Xabar yuborish → {chat}" + (" (javob)" if p.get("reply_to") else "")
        return f"{head}\n\n{p['text'][:1500]}"
    if kind == "forward_messages":
        src = titles.get(p["from_chat_id"], str(p["from_chat_id"]))
        return f"↪️ Forward: {src} → {chat}, {len(p['message_ids'])} ta xabar"
    if kind == "edit_message":
        return f"✏️ Xabarni tahrirlash ({chat}, #{p['message_id']})\n\n{p['text'][:1500]}"
    if kind == "delete_messages":
        return f"🗑 Xabarlarni oʻchirish ({chat}): {len(p['message_ids'])} ta"
    return f"📎 Fayl yuborish → {chat}\n{p['file_url']}" + (f"\n\n{p['caption'][:500]}" if p["caption"] else "")


async def execute(session: str, kind: str, p: dict,
                  factory: SessionClientFactory = default_session_client) -> dict:
    client = factory(session)
    await client.connect()
    try:
        return await _run(client, kind, p)
    finally:
        await client.disconnect()


async def _run(client: Any, kind: str, p: dict) -> dict:
    if kind == "send_message":
        m = await client.send_message(p["chat_id"], p["text"], reply_to=p.get("reply_to"))
        return {"message_id": int(m.id)}
    if kind == "forward_messages":
        ms = await client.forward_messages(p["chat_id"], p["message_ids"], from_peer=p["from_chat_id"])
        return {"message_ids": [int(m.id) for m in (ms if isinstance(ms, list) else [ms])]}
    if kind == "edit_message":
        m = await client.edit_message(p["chat_id"], p["message_id"], p["text"])
        return {"message_id": int(m.id)}
    if kind == "delete_messages":
        res = await client.delete_messages(p["chat_id"], p["message_ids"])
        return {"deleted": sum(int(getattr(r, "pts_count", 0)) for r in (res or []))}
    m = await client.send_file(p["chat_id"], p["file_url"], caption=p["caption"] or None, voice_note=p["voice"])
    return {"message_id": int(m.id)}


Executor = Callable[..., Any]
