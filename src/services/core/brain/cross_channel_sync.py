"""AmoCRM & Telegram Cross-Channel Intelligence Bridge for Obsidian Second Brain.

Extracts deal updates, call transcripts, and AI objections from AmoCRM, matches them with
Telegram chat history by phone/name, and persists unified customer intelligence cards
and weekly sales analytics into the Obsidian Second Brain vault.
"""
from __future__ import annotations

import os
import re
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

VAULT_PATHS = [
    r"C:\Users\baxti\Documents\JonBranding Second Brain",
    r"C:\Users\baxti\OneDrive\Документы\Obsidian Vault",
    "/home/ubuntu/obsidian-vault",
]


def _get_active_vault_path() -> Optional[Path]:
    for p in VAULT_PATHS:
        path = Path(p)
        if path.exists() and (path / "60-Wiki").exists():
            return path
    env_vault = os.getenv("VAULT_PATH")
    if env_vault and Path(env_vault).exists():
        return Path(env_vault)
    return None


def sanitize_text(text: str) -> str:
    """Removes card numbers, passwords, and sensitive credentials."""
    if not text:
        return ""
    # Mask 16-digit card numbers
    text = re.sub(r"\b(?:\d[ -]*?){13,16}\b", "[KARTA MA'LUMOTI]", text)
    # Mask passwords
    text = re.sub(r"(?i)(parol|password|secret)[:=]\s*\S+", r"\1: [YASHIRILGAN]", text)
    return text.strip()


class CrossChannelBrainSync:
    """Synchronizes AmoCRM deals and Telegram chats into unified Obsidian intelligence notes."""

    def __init__(self, vault_path: Optional[Path] = None) -> None:
        self.vault_path = vault_path or _get_active_vault_path()

    def sync_deal_and_call(
        self,
        lead_id: int,
        lead_name: str,
        phone: str,
        price: float = 0.0,
        status_name: str = "Aktiv",
        transcript: str = "",
        ai_analysis: str = "",
        telegram_messages: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        """Creates or updates a unified client intelligence note in 60-Wiki/pages/."""
        if not self.vault_path:
            logger.warning("[BRAIN_SYNC] No active Obsidian vault found on system.")
            return False

        pages_dir = self.vault_path / "60-Wiki" / "pages"
        pages_dir.mkdir(parents=True, exist_ok=True)

        clean_name = re.sub(r'[\\/*?:"<>|]', "", lead_name).strip() or f"Lead_{lead_id}"
        file_path = pages_dir / f"{clean_name}.md"

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        clean_transcript = sanitize_text(transcript)
        clean_ai = sanitize_text(ai_analysis)

        tg_section = ""
        if telegram_messages:
            tg_lines = []
            for msg in telegram_messages[-10:]:
                sender = msg.get("sender", "Unknown")
                text = sanitize_text(msg.get("text", ""))
                dt = msg.get("date", "")[:16]
                tg_lines.append(f"- **[{dt}] {sender}:** {text}")
            tg_section = "\n".join(tg_lines)
        else:
            tg_section = "_Telegram yozishmalari mavjud emas yoki hali ulanmagan._"

        note_content = f"""---
title: "{clean_name}"
type: client-intel
status: "{status_name}"
lead_id: {lead_id}
phone: "{phone}"
budget: {price}
updated: "{now_str}"
tags:
  - client
  - amocrm
  - cross-channel
sources:
  - "[[60-Wiki/pages/JonBranding Client and Project Registry]]"
---

# {clean_name}

**AmoCRM Lead ID:** `{lead_id}`  
**Holati:** `{status_name}`  
**Budjet:** {price:,.0f} so'm  
**Aloqa:** `{phone or "Ko'rsatilmagan"}`  
**Oxirgi yangilanish:** `{now_str}`  

---

## 🎯 AI Qo'ng'iroq Tahlili va Mijoz Ehtiyoji
{clean_ai or "_AI tahlili hali kiritilmagan._"}

## 🎙 Qo'ng'iroq Transkriptsiyasi (Asosiy qismlar)
> {clean_transcript or "Audio yozuv transkriptsiyasi kutilmoqda."}

---

## 💬 Telegram Yozishmalari Tarixi (Cross-Channel)
{tg_section}

---

## 🔗 Bog'lanishlar
- Markaz: [[JonBranding]]
- Reestr: [[pages/JonBranding Client and Project Registry|Mijozlar Reestri]]
- Sotuvlar: [[20-Areas/Savdo|Savdo Tizimi]]
"""
        try:
            file_path.write_text(note_content, encoding="utf-8")
            logger.info("[BRAIN_SYNC] Successfully synced client card: %s", file_path.name)
            return True
        except Exception as exc:
            logger.error("[BRAIN_SYNC] Failed to write client note: %s", exc)
            return False

    def compile_weekly_sales_intelligence(
        self,
        won_deals: List[Dict[str, Any]],
        lost_deals: List[Dict[str, Any]],
        objections_summary: str = "",
    ) -> bool:
        """Generates weekly sales intelligence synthesis note in 60-Wiki/pages/."""
        if not self.vault_path:
            return False

        pages_dir = self.vault_path / "60-Wiki" / "pages"
        pages_dir.mkdir(parents=True, exist_ok=True)
        file_path = pages_dir / "AmoCRM Weekly Intelligence.md"

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        won_table = ""
        if won_deals:
            rows = ["| Bitim Nomi | Summa | Mijoz | Sana |", "| :--- | :--- | :--- | :--- |"]
            for d in won_deals:
                rows.append(f"| {d.get('name', '')} | {d.get('price', 0):,.0f} so'm | {d.get('client', '')} | {d.get('date', '')[:10]} |")
            won_table = "\n".join(rows)
        else:
            won_table = "_Ushbu davrda muvaffaqiyatli yopilgan bitimlar yo'q._"

        lost_table = ""
        if lost_deals:
            rows = ["| Bitim Nomi | Sabab | Summa | Sana |", "| :--- | :--- | :--- | :--- |"]
            for d in lost_deals:
                reason = d.get("reason") or "Noma'lum"
                rows.append(f"| {d.get('name', '')} | {reason} | {d.get('price', 0):,.0f} so'm | {d.get('date', '')[:10]} |")
            lost_table = "\n".join(rows)
        else:
            lost_table = "_Ushbu davrda yo'qotilgan bitimlar yo'q._"

        content = f"""---
title: AmoCRM Weekly Intelligence
type: synthesis
status: active
updated: "{now_str}"
tags:
  - amocrm
  - sales/intelligence
  - second-brain
sources:
  - "[[20-Areas/Savdo]]"
---

# AmoCRM Haftalik Sotuvlar va Mijozlar Tahlili

Sana: **{now_str}** · Manba: [[AmoCRM Live Sync]] · Xotira: [[JonBranding]]

---

## 🏆 Muvaffaqiyatli Yopilgan Bitimlar (Won Deals)
{won_table}

---

## 🛑 Yo'qotilgan Bitimlar va Rad Sabablari (Lost Deals)
{lost_table}

---

## 💡 Mijozlar E'tirozlari va Bozor Signallari (AI Insights)
{objections_summary or "_E'tirozlar tahlili kiritilmoqda._"}

---

## 🎯 Keyingi Hafta Uchun Sotuv Strategiyasi
1. **Tezkor javob berish:** Yangi tushgan so'rovlarga dastlabki 15 daqiqada aloqaga chiqish.
2. **Qimmat deganlarga:** Qiymatni (branding + patent + qadoqlash integratsiyasi) isbotlovchi keyslarni taqdim qilish.
3. **Muzlagan bitimlar:** Closerlar orqali har 7 kunda avtomatlashtirilgan qayta qizdirish.
"""
        try:
            file_path.write_text(content, encoding="utf-8")
            logger.info("[BRAIN_SYNC] Weekly sales intelligence compiled successfully.")
            return True
        except Exception as exc:
            logger.error("[BRAIN_SYNC] Failed to compile weekly sales note: %s", exc)
            return False
