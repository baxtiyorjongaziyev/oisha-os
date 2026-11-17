"""Telegram kontaktlari: öqish + kunlik limitli drip navbati (FloodWait xavfsiz)."""

import logging
from datetime import datetime, timedelta

from ..models import Person, display_name
from .base import NAME_PHONE, keys_of, result, split_name

logger = logging.getLogger(__name__)


class TelegramAdapter:
    name = "telegram"
    fields = NAME_PHONE

    def __init__(self, client, store):
        self.client = client
        self.store = store

    async def read_all(self, people: dict[str, Person]) -> dict[str, dict[str, str]]:
        from telethon import functions

        res = await self.client(functions.contacts.GetContactsRequest(hash=0))
        by_id = {u.id: u for u in getattr(res, "users", [])}
        rows = {}
        for key, p in people.items():
            u = by_id.get(p.tg_id)
            if not u:
                continue
            first, last = split_name(f"{u.first_name or ''} {u.last_name or ''}")
            phone = getattr(u, "phone", None)
            rows[key] = {
                "first_name": first,
                "last_name": last,
                "phone": ("+" + phone) if phone else "",
            }
        return rows

    async def apply(self, changes, people: dict[str, Person]) -> dict:
        """Töğridan-töğri yozmaydi: navbatga qöyadi, drip() bajaradi."""
        res = result()
        for key in keys_of(changes):
            p = people.get(key)
            if not p or not (p.tg_id or p.username or p.phone):
                continue
            await self.store.enqueue_tg(key, p.username, p.phone)
            res["deferred"] += 1
        return res


async def _add_one(client, p: Person, username: str) -> None:
    from telethon import functions

    entity = await client.get_input_entity(username or p.tg_id)
    name = display_name(p)
    first, _, last = name.partition(" ")
    await client(
        functions.contacts.AddContactRequest(
            id=entity,
            first_name=first,
            last_name=last,
            phone=p.phone or "",
            add_phone_privacy_exception=False,
        )
    )


async def drip(store, client, people: dict[str, Person], limit: int, now: datetime) -> dict:
    from telethon.errors import FloodWaitError

    res = result()
    due = await store.due_tg(limit, now)
    for i, row in enumerate(due):
        p = people.get(row["key"])
        if not p:
            await store.mark_tg(row["key"], "failed")
            res["failed"] += 1
            continue
        try:
            await _add_one(client, p, row.get("username") or "")
        except FloodWaitError as e:
            await store.mark_tg(row["key"], "deferred", now + timedelta(seconds=e.seconds))
            res["deferred"] += len(due) - i
            logger.warning("[COMMUNITY_SYNC] FloodWait %ss, drip töxtadi", e.seconds)
            break
        except Exception as exc:
            logger.error("[COMMUNITY_SYNC] tg add %s: %s", row["key"], exc)
            await store.mark_tg(row["key"], "failed")
            res["failed"] += 1
            continue
        await store.mark_tg(row["key"], "done")
        res["ok"] += 1
    return res
