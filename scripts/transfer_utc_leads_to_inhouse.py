"""Transfer the 10 known active UTC leads directly to Sotuv Bo'limi."""
from __future__ import annotations

import json
import sqlite3
import requests

TARGET_PIPELINE_ID = 11162698       # Sotuv Bo'limi
TARGET_STATUS_ID = 89067962         # Yangi LEads
DB_PATH = "data/leadgen_delivery.db"
TOKEN_PATH = "data/amocrm_token.json"

LEAD_IDS = [
    53881243,
    53881257,
    53881271,
    53881289,
    53881295,
    53881307,
    53881333,
    53881345,
    53881363,
    53881373,
]


def run():
    with open(TOKEN_PATH, "r", encoding="utf-8") as f:
        token = json.load(f)
    headers = {
        "Authorization": f"Bearer {token['access_token']}",
        "Content-Type": "application/json",
    }

    patch_body = [
        {
            "id": lid,
            "pipeline_id": TARGET_PIPELINE_ID,
            "status_id": TARGET_STATUS_ID,
            "tags_to_add": [{"name": "taqsimot:inhouse"}],
        }
        for lid in LEAD_IDS
    ]

    print(f"Executing batch PATCH for {len(LEAD_IDS)} leads...", flush=True)
    resp = requests.patch(
        "https://jonbranding.amocrm.ru/api/v4/leads",
        headers=headers,
        json=patch_body,
        timeout=15,
    )
    print(f"PATCH status code: {resp.status_code}", flush=True)

    if resp.status_code not in (200, 204):
        print(f"Error: {resp.text}", flush=True)
        return

    # Add explanatory note to leads
    note_text = (
        "🔄 [Tizim]: UTC outsource bekor qilingani sababli bitim "
        "'Sotuv Bo'limi' (Inhouse) voronkasining 'Yangi LEads' bosqichiga o'tkazildi."
    )
    note_payload = [{"note_type": "common", "params": {"text": note_text}}]

    print("Adding note to leads...", flush=True)
    for lid in LEAD_IDS:
        try:
            r_note = requests.post(
                f"https://jonbranding.amocrm.ru/api/v4/leads/{lid}/notes",
                headers=headers,
                json=note_payload,
                timeout=5,
            )
            print(f"Lead {lid}: note status {r_note.status_code}", flush=True)
        except Exception as e:
            print(f"Lead {lid}: note error {e}", flush=True)

    # Update local SQLite database
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                f"UPDATE deliveries SET destination = 'inhouse' WHERE lead_id IN ({','.join('?' for _ in LEAD_IDS)})",
                LEAD_IDS,
            )
        print("Updated deliveries table in data/leadgen_delivery.db", flush=True)
    except Exception as e:
        print(f"SQLite error: {e}", flush=True)

    print("\nSUCCESS: All 10 leads moved to Sotuv Bo'limi (Yangi LEads)!", flush=True)


if __name__ == "__main__":
    run()
