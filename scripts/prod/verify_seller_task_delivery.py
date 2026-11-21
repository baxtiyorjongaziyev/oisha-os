"""Preview or send one real open due task per seller through the Oisha bot.

Only --send writes Telegram messages and persistent delivery receipts.
Never starts a Telegram update receiver or userbot session.
"""
import argparse
import asyncio
import json
import time

from aiogram import Bot
from src.database import Database
from src.settings import settings
from src.services.core.crm.amocrm_sync import AmoCRMSync
from src.services.core.crm.task_notifier.notifier import AmoCrmTaskNotifier
from src.services.core.crm.task_notifier.routing import resolve_seller, SELLERS
from src.services.core.crm.task_notifier.delivery import delivery_key


def secret(value):
    return value.get_secret_value() if hasattr(value, "get_secret_value") else value


async def main(send=False):
    crm = AmoCRMSync(
        subdomain=settings.AMOCRM_SUBDOMAIN, client_id=settings.AMOCRM_CLIENT_ID,
        client_secret=secret(settings.AMOCRM_CLIENT_SECRET), redirect_url=settings.AMOCRM_REDIRECT_URL,
    )
    db, bot = Database(), Bot(token=secret(settings.BOT_TOKEN))
    try:
        for seller in SELLERS.values():
            chat = await bot.get_chat(seller.chat_id)
            print(json.dumps({"seller": seller.name, "live_chat_id": chat.id, "live_username": chat.username}))
            assert chat.id == seller.chat_id and chat.type == "private"
        tasks = await crm.get_tasks(is_completed=False)
        now = time.time()
        tasks = sorted((t for t in tasks if 0 < int(t.get("complete_till") or 0) <= now),
                       key=lambda t: t["complete_till"], reverse=True)
        selected = {}
        for task in tasks:
            if task.get("entity_type") != "leads":
                continue
            lead = await crm.get_lead(task["entity_id"])
            seller = resolve_seller(lead)
            if seller and str((lead or {}).get("status_id")) not in {"142", "143"}:
                selected.setdefault(seller.name, (seller, task))
            if len(selected) == len(SELLERS):
                break
        print(json.dumps({"open_due_tasks_read": len(tasks), "selected": [
            {"seller": s.name, "task_id": t["id"], "lead_id": t["entity_id"], "chat_id": s.chat_id}
            for s, t in selected.values()
        ]}))
        if send:
            notifier = AmoCrmTaskNotifier(crm, db, bot)
            for seller, task in selected.values():
                kind = "overdue" if now - task["complete_till"] > 900 else "due"
                sent = await notifier.send_task_alert(task, kind)
                receipt = await db.get_state(delivery_key(task, seller, kind))
                print(json.dumps({"seller": seller.name, "sent": sent, "receipt": receipt}))
    finally:
        await bot.session.close()
        await db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--send", action="store_true")
    asyncio.run(main(parser.parse_args().send))
