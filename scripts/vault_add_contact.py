"""Quick CLI to ingest a new contact into Obsidian Second Brain (`70-Odamlar/`)."""

import argparse
from src.services.core.vault_entity_sync import log_interaction_to_vault, sync_person_to_vault


def main() -> None:
    parser = argparse.ArgumentParser(description="Add/update a contact in Obsidian 70-Odamlar/")
    parser.add_argument("--name", required=True, help="Full name of the person")
    parser.add_argument("--phone", default=None, help="Phone number")
    parser.add_argument("--telegram", default=None, help="Telegram @username")
    parser.add_argument("--tag", action="append", default=["TEZ-NATIJA-7"], help="Tag(s) to attach")
    parser.add_argument("--note", default=None, help="Optional interaction note")
    parser.add_argument("--actor", default="Baxtiyorjon", help="Who interacted")
    args = parser.parse_args()

    if args.note:
        path = log_interaction_to_vault(
            person_name=args.name,
            actor=args.actor,
            channel="Networking",
            summary=args.note,
            phone=args.phone,
            telegram=args.telegram,
        )
        sync_person_to_vault(name=args.name, phone=args.phone, telegram=args.telegram, tags=args.tag)
    else:
        path = sync_person_to_vault(
            name=args.name,
            phone=args.phone,
            telegram=args.telegram,
            tags=args.tag,
            source="TEZ-NATIJA-7",
        )
    print(f"Synced: {path}")


if __name__ == "__main__":
    main()
