import os
import json
import re
import asyncio
from datetime import datetime
from typing import List, Dict, Any

import aiohttp
from telethon import TelegramClient
from telethon.tl.types import Message

PHONE_REGEX = re.compile(r"(?:\+?998|0)?(9\d{8})")

# Load configuration
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONFIG_DIR = os.path.join(BASE_DIR, "config")

KEYWORDS_PATH = os.path.join(CONFIG_DIR, "keywords.json")
ASSIGNMENTS_PATH = os.path.join(CONFIG_DIR, "assignments.json")
TELEGRAM_GROUPS_PATH = os.path.join(CONFIG_DIR, "telegram_groups.json")

with open(KEYWORDS_PATH, "r", encoding="utf-8") as f:
    KEYWORDS = json.load(f).get("keywords", [])

with open(ASSIGNMENTS_PATH, "r", encoding="utf-8") as f:
    ASSIGNMENTS = json.load(f).get("assignments", {})

with open(TELEGRAM_GROUPS_PATH, "r", encoding="utf-8") as f:
    TELEGRAM_GROUP_IDS = json.load(f).get("group_ids", [])

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, ".env"))
except ImportError:
    pass

from telethon.sessions import StringSession

API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
# Only the temp session is used; prod USERBOT_SESSION_STRING / TELEGRAM_MCP_SESSION_STRING
# belong to Oracle VM and must never be used locally (AuthKeyDuplicatedError).
SESSION = (os.getenv("TG_TEMP_SESSION", "") or "").strip().strip("'\"")

# If any credential is missing, we simply skip Telegram fetching (log via brain_log later)
if not API_ID or not API_HASH or not SESSION:
    client = None
else:
    client = TelegramClient(StringSession(SESSION), API_ID, API_HASH)

async def fetch_telegram_messages() -> List[Message]:
    """Search recent messages in configured public groups/channels for any of the KEYWORDS.
    Returns a list of Telethon Message objects that match.
    """
    if client is None:
        return []
    await client.start()
    matched = []
    for gid in TELEGRAM_GROUP_IDS:
        async for msg in client.iter_messages(gid, limit=200):
            if not msg.message:
                continue
            lowered = msg.message.lower()
            if any(kw.lower() in lowered for kw in KEYWORDS):
                matched.append(msg)
    await client.disconnect()
    return matched

def extract_phone_numbers(text: str) -> List[str]:
    return ["+998" + m for m in PHONE_REGEX.findall(text)]

# Placeholder functions for other platforms (to be implemented later)
async def query_facebook() -> List[Dict[str, Any]]: return []
async def query_instagram() -> List[Dict[str, Any]]: return []
async def query_linkedin() -> List[Dict[str, Any]]: return []

async def build_leads() -> List[Dict[str, Any]]:
    leads = []
    # Telegram
    tg_messages = await fetch_telegram_messages()
    for msg in tg_messages:
        phones = extract_phone_numbers(msg.message)
        if not phones:
            continue
        assigned = None
        for kw in KEYWORDS:
            if kw.lower() in msg.message.lower():
                assigned = ASSIGNMENTS.get(kw)
                break
        lead = {
            "source": "telegram",
            "chat_id": msg.chat_id,
            "message_id": msg.id,
            "text": msg.message,
            "phones": phones,
            "assigned_group": assigned,
            "timestamp": datetime.utcfromtimestamp(msg.date.timestamp()).isoformat() + "Z",
        }
        leads.append(lead)
    # Other platforms placeholders
    leads.extend(await query_facebook())
    leads.extend(await query_instagram())
    leads.extend(await query_linkedin())
    return leads

async def sync_lead_to_observer(lead: Dict[str, Any]):
    import subprocess, json, shlex
    payload = json.dumps(lead)
    cmd = f"python -m scripts.community_lead_sync '{payload}'"
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    if proc.returncode != 0:
        print(f"[lead_sync] error: {err.decode()}")
    else:
        print(f"[lead_sync] success: {out.decode()}")

async def main():
    leads = await build_leads()
    if not leads:
        print("[discover] No new leads found.")
        return
    print(f"[discover] Found {len(leads)} lead(s).")
    await asyncio.gather(*(sync_lead_to_observer(l) for l in leads))

if __name__ == "__main__":
    asyncio.run(main())
