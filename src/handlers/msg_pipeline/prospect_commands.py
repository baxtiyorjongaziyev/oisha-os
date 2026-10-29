"""Prospect controls called only after the admin authorization gate."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)
COMMANDS = {"/lead_sources", "/lead_scan", "/lead_candidates", "/lead_auto"}


async def handle_prospect_command(event, text, client, *, is_owner):
    parts = text.split()
    if not parts or parts[0] not in COMMANDS:
        return False
    if parts[0] in {"/lead_sources", "/lead_auto"} and len(parts) > 1 and not is_owner:
        await event.respond("Manba va avtomatika sozlamalarini faqat owner o'zgartiradi.")
        return True
    try:
        from src.services.core.leads.prospect_store import get_prospect_store

        store = get_prospect_store()
        await store.initialize()
        if parts[0] == "/lead_sources":
            await _sources(event, parts, client, store)
        elif parts[0] == "/lead_auto":
            if len(parts) == 2 and parts[1] in {"on", "off"}:
                await store.set_auto(parts[1] == "on")
            enabled = await store.auto_enabled()
            await event.respond(f"Lid qidirish avtomatikasi: {'on' if enabled else 'off'}. /lead_auto on|off")
        elif parts[0] == "/lead_scan":
            from src.services.core.leads.prospect_discovery import scan_prospects

            result = await scan_prospects(client, store)
            await event.respond(
                f"Qidiruv: {result['status']}. Yangi potensial mijozlar: "
                f"{result['new'] if result['new'] is not None else 'noma’lum'}.\n"
                + "\n".join(f"{s['chat_id']}: {s['status']}" for s in result["sources"])
                + "\nKo'rish: /lead_candidates. Qamrov: oxirgi 7 kun, har manbada 200 xabargacha."
            )
        else:
            await _candidates(event, store)
    except Exception as exc:
        logger.warning("Prospect command failed: %s", type(exc).__name__)
        await event.respond("Lid qidirish manbasi yoki saqlash tizimi ishlamadi. Natija tekshirilmagan.")
    return True


async def _sources(event, parts, client, store):
    if len(parts) == 2 and parts[1] == "discover":
        from src.services.core.leads.prospect_sources import suggest_sources

        result = await suggest_sources(client)
        lines = [f"{r['chat_id']} — {r['title']}\n{r['url']}" for r in result["sources"]]
        await event.respond(
            f"Manba qidiruvi: {result['status']}. Ko'rilgan qamrov: 250 dialoggacha.\n"
            + ("\n".join(lines) or "Mos ochiq manba topilmadi yoki manba ulanmagan.")
            + "\nBu nom bo'yicha tavsiya, lid sifati tekshirilmagan. Qo'shish: /lead_sources add <chat_id>",
            parse_mode=None,
        )
        return
    if len(parts) == 3 and parts[1] == "add":
        if client is None or not client.is_connected():
            await event.respond("Telegram manbasi ulanmagan.")
            return
        from telethon import utils
        from telethon.tl.types import Channel

        reference = int(parts[2]) if parts[2].lstrip("-").isdigit() else parts[2]
        entity = await client.get_entity(reference)
        if not isinstance(entity, Channel):
            await event.respond("Faqat ruxsat etilgan superguruh yoki kanal qo'shiladi.")
            return
        # Resolve and read before enabling; never join a new group automatically.
        await client.get_messages(entity, limit=1)
        await store.add_source(utils.get_peer_id(entity), entity.title)
    elif len(parts) == 3 and parts[1] == "remove":
        await store.disable_source(int(parts[2]))
    rows = await store.sources()
    lines = [f"{r['chat_id']} — {r['title']} | {r['last_status'] or 'tekshirilmagan'} | {r['last_scan'] or 'hali skanerlanmagan'}" for r in rows]
    await event.respond(
        "Manbalar:\n" + ("\n".join(lines) or "Manba sozlanmagan.")
        + "\n/lead_sources discover\n/lead_sources add @kanal yoki -100…\n/lead_sources remove <chat_id>",
        parse_mode=None,
    )


async def _candidates(event, store):
    rows = await store.recent()
    if not rows:
        await event.respond("Navbat bo'sh. Manba holati: /lead_sources. Qidiruv: /lead_scan")
        return
    for row in rows:
        await event.respond(
            f"Potensial mijoz — {row['service']}\n"
            f"Dalil: {row['evidence']}\nManba: {row['source_url']}\n"
            f"Xabar vaqti: {row['published_at']}\nTekshirilgan: {row['observed_at']}\n"
            f"Telefon: {row['phone'] or 'noma’lum'}\n"
            "Budjet va xarid muddati: noma’lum. CRM: tekshirilmagan.\n"
            "Keyingi qadam: ehtiyoj, budjet, muddat va qaror qiluvchini tekshirish.",
            parse_mode=None,
        )
