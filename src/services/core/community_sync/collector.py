"""Tadbirkorlar papkasidan guruhlar, aʼzolar va tanishtiruv postlarini yigʻish.

Faqat mavjud (Hetzner) Telethon klienti bilan chaqiriladi — yangi sessiya ochilmaydi.
"""

import logging

from src.services.core.contact_intro_parser import parse_contact_intro

from .cohorts import cohort_for_group
from .merge import absorb, resolve
from .models import Person

logger = logging.getLogger(__name__)


async def folder_peers(client, folder_id: int) -> list:
    from telethon import functions

    res = await client(functions.messages.GetDialogFiltersRequest())
    filters = getattr(res, "filters", res) or []
    for f in filters:
        if getattr(f, "id", None) == folder_id:
            return list(getattr(f, "include_peers", []) or [])
    logger.warning("[COMMUNITY_SYNC] folder %s topilmadi", folder_id)
    return []


def _from_member(m, cohort_code: str) -> Person:
    return Person(
        key=f"tg:{m.id}",
        tg_id=m.id,
        username=getattr(m, "username", None) or "",
        first_name=getattr(m, "first_name", None) or "",
        last_name=getattr(m, "last_name", None) or "",
        phone=("+" + m.phone) if getattr(m, "phone", None) else "",
        cohorts={cohort_code},
    )


def _apply_intro(p: Person, intro) -> None:
    """Intro postdagi haqiqiy ism profil nomidan ustun."""
    p.first_name = intro.first_name or p.first_name
    p.last_name = intro.last_name or p.last_name
    p.phone = intro.phone or p.phone
    p.company = intro.brand or p.company
    p.activity = intro.activity or p.activity
    p.region = intro.region or p.region


async def _collect_chat(client, chat, history_limit: int) -> list[Person]:
    cohort = cohort_for_group(getattr(chat, "title", ""))
    if cohort is None:
        return []
    members: dict[int, Person] = {}
    async for m in client.iter_participants(chat):
        if getattr(m, "bot", False) or getattr(m, "deleted", False):
            continue
        members[m.id] = _from_member(m, cohort.code)
    async for msg in client.iter_messages(chat, limit=history_limit):
        p = members.get(getattr(msg, "sender_id", None))
        text = getattr(msg, "message", None) or ""
        if p is None or not text:
            continue
        intro = parse_contact_intro(text, source_chat=chat.title)
        if intro:
            _apply_intro(p, intro)
    return list(members.values())


async def collect(client, folder_id: int, history_limit: int = 3000) -> list[Person]:
    people: list[Person] = []
    for peer in await folder_peers(client, folder_id):
        try:
            chat = await client.get_entity(peer)
            chat_people = await _collect_chat(client, chat, history_limit)
        except Exception as exc:  # bitta guruh xatosi butun ishni toʻxtatmaydi
            logger.error("[COMMUNITY_SYNC] guruh oʻqishda xato: %s", exc)
            continue
        for inc in chat_people:
            hit = resolve(people, inc)
            if hit:
                absorb(hit, inc)
            else:
                people.append(inc)
    return people
