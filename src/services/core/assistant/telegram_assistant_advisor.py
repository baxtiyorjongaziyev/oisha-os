"""Telegram Real-Time Assistant Advisor for Oisha-OS.

Audits incoming client messages, questions, and follow-up requests in Baxtiyorjon's Telegram,
generates actionable 1-2-3 step instructions for business assistant Shahnoza (@jonbranding_assistant),
delivers notifications via @jonairobot, and records recommendations in the Obsidian Second Brain.
"""
from __future__ import annotations

import os
import re
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# Shahnoza's identifiers
SHAHNOZA_USER_ID = 8802892610
SHAHNOZA_USERNAME = "jonbranding_assistant"

VAULT_PATHS = [
    r"C:\Users\baxti\Documents\JonBranding Second Brain",
    r"C:\Users\baxti\OneDrive\Документы\Obsidian Vault",
    "/home/ubuntu/obsidian-vault",
]


def _get_active_vault_path() -> Optional[Path]:
    for p in VAULT_PATHS:
        path = Path(p)
        if path.exists() and (path / "20-Areas").exists():
            return path
    env_vault = os.getenv("VAULT_PATH")
    if env_vault and Path(env_vault).exists():
        return Path(env_vault)
    return None


class TelegramAssistantAdvisor:
    """Audits Telegram conversations and provides real-time recommendations to assistant Shahnoza."""

    def __init__(self, vault_path: Optional[Path] = None, assistant_id: int = SHAHNOZA_USER_ID) -> None:
        self.vault_path = vault_path or _get_active_vault_path()
        self.assistant_id = assistant_id
        self._processed_msg_ids: Set[str] = set()

    def analyze_chat_for_assistant(
        self,
        chat_id: int,
        chat_title: str,
        messages: List[Dict[str, Any]],
        owner_id: int = 150074828,
    ) -> Optional[Dict[str, Any]]:
        """Analyzes a conversation and extracts an actionable recommendation for Shahnoza."""
        if not messages:
            return None

        last_msg = messages[-1]
        msg_id = str(last_msg.get("id", ""))
        unique_key = f"{chat_id}_{msg_id}"

        if unique_key in self._processed_msg_ids:
            return None

        sender = last_msg.get("sender", "Mijoz")
        text = last_msg.get("text", "").strip()
        sender_id = last_msg.get("sender_id")

        # Ignore messages sent by Baxtiyorjon or Shahnoza herself
        if sender_id in (owner_id, self.assistant_id):
            return None

        if len(text) < 3:
            return None

        # Categorize action trigger
        action_needed = False
        action_type = "Umumiy so'rov"
        recommendation = ""

        lower_text = text.lower()
        if any(k in lower_text for k in ["narx", "qancha", "narxi", "qimmat", "tolov", "to'lov", "byudjet"]):
            action_needed = True
            action_type = "Narx / Byudjet so'rovi"
            recommendation = (
                f"Mijozga ({chat_title}) xizmatlar tarifi va portfolio namunasini yuboring. "
                "Byudjetini aniqlab, qisqa briefing o'tkazing."
            )
        elif any(k in lower_text for k in ["qachon", "tayyor", "status", "qayerda", "fayl", "logo", "maketi", "korgan"]):
            action_needed = True
            action_type = "Loyiha statusi / Fayl so'rovi"
            recommendation = (
                f"Mijoz ({chat_title}) ish jarayonini so'ramoqda. Dizayn guruhidan statusni oling va "
                "mijozga bugungi muddatni ma'lum qiling."
            )
        elif any(k in lower_text for k in ["korish", "ko'rish", "uchrash", "zoom", "gaplash", "qongiroq", "qo'ng'iroq"]):
            action_needed = True
            action_type = "Uchrashuv / Qo'ng'iroq"
            recommendation = (
                f"Mijoz ({chat_title}) suhbatlashmoqchi. Baxtiyorjonning bo'sh vaqtiga qarab 15 daqiqalik "
                "strategik sessiya yoki qo'ng'iroq vaqtini belgilang."
            )
        elif any(k in lower_text for k in ["rahmat", "boladi", "bo'ladi", "tasdiq", "ma'qul", "start"]):
            action_needed = True
            action_type = "Tasdiqlash / Keyingi bosqich"
            recommendation = (
                f"Mijoz ({chat_title}) ijobiy javob berdi. Shartnoma yoki avans to'lovi uchun rekvizitlarni tayyorlang."
            )
        elif "?" in text or len(text.split()) >= 4:
            # Unanswered question
            action_needed = True
            action_type = "Javob talab qiluvchi savol"
            recommendation = (
                f"Mijozning ({chat_title}) savoliga aniqlik kiriting va zarur bo'lsa Baxtiyorjonga xabar bering."
            )

        if not action_needed:
            return None

        self._processed_msg_ids.add(unique_key)
        return {
            "chat_id": chat_id,
            "chat_title": chat_title,
            "sender": sender,
            "text": text,
            "action_type": action_type,
            "recommendation": recommendation,
            "date": last_msg.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")),
        }

    def format_telegram_alert(self, task: Dict[str, Any]) -> str:
        """Formats an executive Uzbek notification for Shahnoza."""
        return (
            f"⚡ <b>Yangi Tavsiya (Shaxsiy Yordamchi Shahnoza uchun)</b>\n\n"
            f"👤 <b>Mijoz / Chat:</b> {task['chat_title']}\n"
            f"📌 <b>Yo'nalish:</b> {task['action_type']}\n"
            f"💬 <b>Mijoz xabari:</b> <i>\"{task['text'][:150]}\"</i>\n\n"
            f"🎯 <b>Qilinishi kerak bo'lgan vazifa:</b>\n"
            f"👉 {task['recommendation']}\n\n"
            f"⏱ <i>Real-time Telegram Audit</i>"
        )

    def record_in_obsidian(self, tasks: List[Dict[str, Any]]) -> bool:
        """Appends generated assistant tasks to 20-Areas/Yordamchi Vazifalari.md."""
        if not self.vault_path or not tasks:
            return False

        areas_dir = self.vault_path / "20-Areas"
        areas_dir.mkdir(parents=True, exist_ok=True)
        file_path = areas_dir / "Yordamchi Vazifalari.md"

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        new_lines = [f"\n### ⚡ Audit: {now_str}"]
        for t in tasks:
            new_lines.append(f"- [ ] **{t['chat_title']}** ({t['action_type']}): {t['recommendation']}")
            new_lines.append(f"  > _\"{t['text'][:100]}\"_")

        content_to_append = "\n".join(new_lines) + "\n"

        if file_path.exists():
            existing = file_path.read_text(encoding="utf-8")
            file_path.write_text(existing + content_to_append, encoding="utf-8")
        else:
            header = f"""---
title: Shaxsiy Yordamchi Vazifalari va Tavsiyalar
type: area
status: active
updated: "{now_str}"
tags:
  - assistant
  - tasks
  - jonbranding
sources:
  - "[[Telegram Live Ekosistemasi]]"
---

# Shaxsiy Yordamchi (Shahnoza) Vazifalar Oqimi

Telegramdagi mijozlar so'rovlari asosida AI tomonidan real-time shakllantirilgan tavsiyalar va operativ vazifalar.
"""
            file_path.write_text(header + content_to_append, encoding="utf-8")

        logger.info("[ASSISTANT_ADVISOR] Appended %d tasks to Yordamchi Vazifalari.md", len(tasks))
        return True
