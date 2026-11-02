#!/usr/bin/env python3
"""CLI utility for Google Calendar operations in Oisha-OS ecosystem."""
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from src.services.core.gcalendar import GoogleCalendarSync


def main():
    parser = argparse.ArgumentParser(description="Oisha Google Calendar CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list
    list_parser = subparsers.add_parser("list", help="Tadbirlarni ko'rish")
    list_parser.add_argument("--date", help="Sana (YYYY-MM-DD)", default=None)
    list_parser.add_argument("--limit", type=int, default=10, help="Maksimal tadbirlar soni")
    list_parser.add_argument("--json", action="store_true", help="JSON formatda chiqarish")

    # create
    create_parser = subparsers.add_parser("create", help="Yangi tadbir yaratish")
    create_parser.add_argument("--summary", required=True, help="Tadbir mavzusi")
    create_parser.add_argument("--start", required=True, help="Boshlanish vaqti ISO-8601")
    create_parser.add_argument("--end", required=True, help="Tugash vaqti ISO-8601")
    create_parser.add_argument("--desc", default="", help="Tadbir tavsifi")
    create_parser.add_argument("--location", default="", help="Joylashuv")

    # free-slots
    free_parser = subparsers.add_parser("free", help="Bo'sh vaqtlarni olish")
    free_parser.add_argument("--date", help="Sana (YYYY-MM-DD)", default=None)

    args = parser.parse_args()
    sync = GoogleCalendarSync()

    if not sync.service:
        print(json.dumps({"error": "Google Calendar avtorizatsiyasi mavjud emas"}))
        sys.exit(1)

    if args.command == "list":
        events = sync.get_upcoming_events(date_str=args.date, limit=args.limit)
        if args.json:
            print(json.dumps(events, indent=2, ensure_ascii=False))
        else:
            if not events:
                print("Tadbirlar topilmadi.")
                return
            print(f"📅 Tadbirlar ro'yxati ({len(events)} ta):")
            for e in events:
                start = e.get("start", {}).get("dateTime") or e.get("start", {}).get("date")
                summary = e.get("summary", "(Mavzusiz)")
                print(f" • {summary} | Vaqt: {start}")

    elif args.command == "create":
        res = sync.create_event(
            summary=args.summary,
            start_time=args.start,
            end_time=args.end,
            description=args.desc,
            location=args.location,
        )
        if res:
            event_id = res.get("id") if isinstance(res, dict) else ""
            link = res.get("htmlLink") if isinstance(res, dict) else ""
            print(f"✅ Tadbir yaratildi!\nID: {event_id}\nHavola: {link}")
        else:
            print("❌ Tadbirni yaratib bo'lmadi.")
            sys.exit(1)

    elif args.command == "free":
        slots = sync.get_free_slots(date_str=args.date)
        print(f"🕒 Bo'sh vaqt oralig'i: {len(slots)} ta slot mavjud.")
        for s in slots:
            print(f" • {s}")


if __name__ == "__main__":
    main()
