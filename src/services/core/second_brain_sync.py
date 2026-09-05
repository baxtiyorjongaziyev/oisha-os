"""
Second Brain (Obsidian Vault) Sync Service for Oisha-OS.
Handles automated ingestion of:
1. Voice notes and thoughts from Telegram into 00-Inbox/ and 50-Daily/
2. Won deals and project case studies from AmoCRM into 10-Projects/
"""

import asyncio
import datetime
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("SecondBrainSync")


def resolve_vault_path() -> Optional[Path]:
    """Find the active Obsidian Second Brain vault directory."""
    env_vault = os.getenv("BRAIN_VAULT") or os.getenv("SECOND_BRAIN_PATH")
    if env_vault and os.path.exists(env_vault):
        return Path(env_vault)

    candidate_paths = [
        Path(r"C:\Users\baxti\Documents\Baxtiyorjon Gaziyev Second Brain"),
        Path(r"C:\Users\baxti\Documents\JonBranding Second Brain"),
        Path(r"C:\Users\baxti\OneDrive\Документы\Obsidian Vault"),
        Path("/home/ubuntu/second-brain"),
        Path("/home/ubuntu/obsidian-vault"),
    ]

    for p in candidate_paths:
        if p.exists() and p.is_dir():
            return p

    return None


def _sanitize_filename(name: str, max_len: int = 50) -> str:
    """Sanitize strings for safe cross-platform file naming."""
    clean = re.sub(r'[\\/*?:"<>|]', "", name).strip()
    clean = re.sub(r"\s+", " ", clean)
    if len(clean) > max_len:
        clean = clean[:max_len].rstrip()
    return clean or "Nomlanmagan"


async def save_voice_note(
    text: str,
    sender_name: str = "Baxtiyorjon",
    sender_id: Optional[int] = None,
    source: str = "Telegram (@jonairobot)",
) -> Optional[str]:
    """
    Save an incoming transcribed voice memo to Obsidian Second Brain.
    Writes to 00-Inbox/ and appends a record in 50-Daily/<today>.md.
    """
    if not text or not text.strip():
        logger.debug("[SECOND_BRAIN] Voice note empty, skipping.")
        return None

    vault_path = resolve_vault_path()
    if not vault_path:
        logger.warning("[SECOND_BRAIN] Vault path not found, skipping voice memo.")
        return None

    now = datetime.datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")
    ts_file = now.strftime("%Y%m%d_%H%M%S")

    # 1. Write structured note to 00-Inbox/
    inbox_dir = vault_path / "00-Inbox"
    inbox_dir.mkdir(parents=True, exist_ok=True)

    clean_sender = _sanitize_filename(sender_name, 20)
    note_filename = f"Ovozli_{ts_file}_{clean_sender}.md"
    note_file = inbox_dir / note_filename

    content = f"""---
type: voice_memo
manba: {source}
yuboruvchi: {sender_name}
sana: {date_str} {time_str}
tags:
  - voice
  - inbox
  - ovozli_qayd
---

# 🎙️ Ovozli Qayd ({sender_name}) — {date_str} {time_str}

> {text.strip()}

---

## 💡 Keyingi Harakatlar
- [ ] Tahlil qilish va tegishli loyihaga ([[10-Projects/]]) yoki sohaga ([[20-Areas/]]) bog'lash
- [ ] Vazifa bo'lsa, kundalik rejaga kiritish
"""

    try:
        def _write_inbox():
            with open(note_file, "w", encoding="utf-8") as f:
                f.write(content)

        await asyncio.to_thread(_write_inbox)
        logger.info("✅ [SECOND_BRAIN] Voice memo saved to %s", note_file.name)
    except Exception as exc:
        logger.error("[SECOND_BRAIN] Failed to write voice memo: %s", exc)
        return None

    # 2. Append bullet to today's daily note (50-Daily/YYYY-MM-DD.md)
    try:
        daily_dir = vault_path / "50-Daily"
        daily_dir.mkdir(parents=True, exist_ok=True)
        daily_file = daily_dir / f"{date_str}.md"

        def _append_daily():
            bullet = f"\n- **🎙️ Ovozli ({time_str}, {sender_name}):** [[00-Inbox/{note_filename}|{text[:60]}...]]"
            if daily_file.exists():
                with open(daily_file, "a", encoding="utf-8") as f:
                    f.write(bullet)
            else:
                initial_content = f"# ☀️ Kunlik Fokus: {date_str}\n\n## 📝 Qaydlar va Xabarlar{bullet}\n"
                with open(daily_file, "w", encoding="utf-8") as f:
                    f.write(initial_content)

        await asyncio.to_thread(_append_daily)
    except Exception as exc:
        logger.debug("[SECOND_BRAIN] Daily note append skipped: %s", exc)

    return str(note_file)


async def save_won_case(
    case_data: Dict[str, Any],
    lead_data: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Save a completed AmoCRM project case study to 10-Projects/<title>.md in Second Brain.
    """
    vault_path = resolve_vault_path()
    if not vault_path:
        logger.warning("[SECOND_BRAIN] Vault path not found, skipping won case save.")
        return None

    lead_data = lead_data or {}
    title = case_data.get("title") or lead_data.get("name") or "Loyiha"
    client = case_data.get("client") or lead_data.get("name") or "Mijoz"
    short_desc = case_data.get("short_description") or "Muvaffaqiyatli yakunlandi."
    challenge = case_data.get("challenge") or "Mijozning brending va dizayn bo'yicha talablari."
    solution = case_data.get("solution") or "Jon Branding jamoasi tomonidan to'liq yechim ishlab chiqildi."
    results = case_data.get("results") or "Loyiha tasdiqlandi va topshirildi."
    price = lead_data.get("price", 0)
    lead_id = lead_data.get("id") or case_data.get("amocrm_lead_id") or "N/A"

    now = datetime.datetime.now()
    date_str = now.strftime("%Y-%m-%d")

    projects_dir = vault_path / "10-Projects"
    projects_dir.mkdir(parents=True, exist_ok=True)

    clean_filename = _sanitize_filename(client if client != "Mijoz" else title, 40)
    project_file = projects_dir / f"{clean_filename}.md"

    tags_list = case_data.get("tags") or ["branding", "case_study", "amo_won"]
    tags_yaml = "\n".join(f"  - {t}" for t in tags_list)

    try:
        formatted_price = f"{int(price):,}"
    except (ValueError, TypeError):
        formatted_price = str(price)

    markdown_body = f"""---
type: loyiha
status: yakunlangan
mijoz: {client}
amocrm_lead_id: {lead_id}
narx: {price}
sana: {date_str}
tags:
{tags_yaml}
---

# 🏆 Loyiha: {title}

> **Qisqacha:** {short_desc}

---

## 🎯 Muammo va Ehtiyoj (Challenge)
{challenge}

---

## 💡 Jon Branding Yechimi (Solution)
{solution}

---

## 📈 Erishilgan Natijalar (Results)
{results}

---

## 📋 Ma'lumotlar va Aloqador Bog'lanishlar
- **Mijoz:** [[70-Odamlar/{client}]]
- **Byudjet:** {formatted_price} so'm / u.e.
- **AmoCRM ID:** `{lead_id}`
- **Yakunlangan sana:** {date_str}
"""

    try:
        def _write_case():
            with open(project_file, "w", encoding="utf-8") as f:
                f.write(markdown_body)

        await asyncio.to_thread(_write_case)
        logger.info("✅ [SECOND_BRAIN] Won project case study saved to %s", project_file.name)
        return str(project_file)
    except Exception as exc:
        logger.error("[SECOND_BRAIN] Failed to write won case study: %s", exc)
        return None