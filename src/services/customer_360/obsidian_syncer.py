"""
Obsidian Customer 360 Syncer.

Formats unified Customer360Profile into Obsidian markdown and synchronizes
across local vaults (Documents & OneDrive) and the GitHub repository.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import subprocess
from typing import Any, Dict, List, Optional

from src.services.customer_360.models import Customer360Profile

logger = logging.getLogger(__name__)

DEFAULT_VAULT_PATHS = [
    r"C:\Users\baxti\Documents\Baxtiyorjon Gaziyev Second Brain",
    r"C:\Users\baxti\OneDrive\Документы\Obsidian Vault",
    "/home/ubuntu/obsidian-vault",
]


class Customer360ObsidianSyncer:
    """Synchronizes unified customer profiles to Obsidian Second Brain."""

    def __init__(self, vault_paths: Optional[List[str]] = None) -> None:
        self.vault_paths = [p for p in (vault_paths or DEFAULT_VAULT_PATHS) if os.path.exists(p)]

    def _sanitize_filename(self, name: str) -> str:
        clean = re.sub(r'[\\/*?:"<>|]', "", name).strip()
        return clean or "Noma'lum Mijoz"

    def format_markdown(self, profile: Customer360Profile) -> str:
        """Render Customer360Profile as rich Obsidian Markdown."""
        safe_name = profile.name or "Noma'lum Mijoz"
        tags_line = ", ".join([f"client/{t.lower()}" for t in profile.tags]) if profile.tags else "client/active"
        
        md = [
            "---",
            f"title: \"{safe_name}\"",
            "type: customer-360",
            "status: active",
            f"tags: [{tags_line}]",
            f"phone: \"{profile.phone}\"",
            f"telegram: \"{profile.telegram_username}\"",
            f"instagram: \"{profile.instagram_handle}\"",
            f"amocrm_lead_id: {profile.amocrm_lead_id or 'null'}",
            f"updated: {profile.updated_at}",
            "---",
            "",
            f"# 👤 {safe_name}",
            "",
            "## 📇 Kontaktlar va Identifikatorlar",
            f"- **📞 Telefon:** `{profile.phone or 'Kiritilmagan'}`",
            f"- **💬 Telegram:** @{profile.telegram_username}" if profile.telegram_username else "- **💬 Telegram:** Bog'lanmagan",
            f"- **📸 Instagram:** @{profile.instagram_handle}" if profile.instagram_handle else "- **📸 Instagram:** Bog'lanmagan",
            "",
            "## 📊 AmoCRM Holati",
            f"- **Bitim ID:** `#{profile.amocrm_lead_id}`" if profile.amocrm_lead_id else "- **Bitim ID:** Yo'q",
            f"- **Voronka va Bosqich:** {profile.amocrm_pipeline or 'Asosiy'} -> {profile.amocrm_status or 'Yangi'}",
            f"- **Byudjet:** {profile.amocrm_budget:,} so'm".replace(",", " ") if profile.amocrm_budget else "- **Byudjet:** Belgilanmagan",
            f"- **Mas'ul:** {profile.responsible_manager or 'Belgilanmagan'}",
            f"- **Teglar:** {', '.join(profile.tags)}" if profile.tags else "- **Teglar:** Yo'q",
            "",
            "## 🎨 Airtable Ijro & Moliya (JonBranding)",
            f"- **Loyiha:** {profile.airtable_project_name or 'Hali ochilmagan'}",
            f"- **Bosqich:** {profile.airtable_phase or 'Rejalashtirilmoqda'}",
            f"- **To'langan:** ${profile.airtable_paid:,.0f}" if profile.airtable_paid else "- **To'langan:** $0",
            f"- **Qarz:** ${profile.airtable_debt:,.0f}" if profile.airtable_debt else "- **Qarz:** $0",
            f"- **Muddati (Deadline):** {profile.airtable_deadline or 'Belgilanmagan'}",
            "",
            "## 📞 Telefon Qo'ng'iroqlari & AI Tahlillari (STT)",
        ]

        if not profile.calls:
            md.append("*Ushbu mijoz bo'yicha tahlil qilingan qo'ng'iroqlar tarixi hali mavjud emas.*")
        else:
            for c in profile.calls[:10]:
                mins = c.duration_seconds // 60
                secs = c.duration_seconds % 60
                dur_str = f"{mins}m {secs}s" if mins else f"{secs}s"
                
                ratio_str = f"Mijoz {c.client_talk_pct}% / Sotuvchi {c.manager_talk_pct}%"
                score_str = f"Sotuvchi: {c.seller_score}/10" if c.seller_score else ""
                
                md.append(f"### 🗓️ {c.timestamp} (Davomiyligi: {dur_str})")
                md.append(f"- **Toifa:** `{c.category}` | **Mijoz kayfiyati:** {c.client_mood}")
                md.append(f"- **Gapirish nisbati:** {ratio_str} | {score_str}")
                md.append(f"- **📝 Suhbat xulosasi:** {c.summary}")
                if c.agreed_datetime:
                    md.append(f"- **⏰ Kelishilgan vaqt:** {c.agreed_datetime}")
                if c.conversion_advice:
                    md.append(f"- **💡 Konversiya tavsiyasi:** {c.conversion_advice}")
                if c.transcript:
                    short_tr = c.transcript[:400] + ("..." if len(c.transcript) > 400 else "")
                    md.append(f"> **Transkript parcha:** _{short_tr}_")
                md.append("")

        md.extend([
            "## 💬 Telegram Yozishmalari",
        ])
        if not profile.telegram_messages:
            md.append("*Telegram orqali yozishmalar qayd etilmagan.*")
        else:
            for msg in profile.telegram_messages[-10:]:
                md.append(f"- {msg}")

        md.append("")
        return "\n".join(md)

    async def sync_profile(self, profile: Customer360Profile) -> str:
        """Write profile to all local vaults and git push."""
        content = self.format_markdown(profile)
        safe_name = self._sanitize_filename(profile.name)
        filename = f"{safe_name} — Mijoz 360.md"
        written_paths = []

        for vault in self.vault_paths:
            c20 = os.path.join(vault, "20-CLIENTS")
            m70 = os.path.join(vault, "70-Mijozlar")
            if os.path.exists(m70) and not os.path.exists(c20):
                filename = f"{safe_name}.md"
                os.makedirs(m70, exist_ok=True)
                filepath = os.path.join(m70, filename)
            else:
                filename = f"{safe_name} — Mijoz 360.md"
                target_dir = os.path.join(c20, safe_name)
                if os.path.exists(c20) and not os.path.exists(target_dir):
                    for existing in os.listdir(c20):
                        if safe_name.lower() in existing.lower():
                            target_dir = os.path.join(c20, existing)
                            break
                os.makedirs(target_dir, exist_ok=True)
                filepath = os.path.join(target_dir, filename)

            try:
                await asyncio.to_thread(self._write_file, filepath, content)
                written_paths.append(filepath)
                logger.info(f"[C360] Saved to {filepath}")
            except Exception as e:
                logger.error(f"[C360] Failed to write to {filepath}: {e}")

        # GitHub push asynchronously in background
        asyncio.create_task(self._push_to_github())

        return written_paths[0] if written_paths else ""

    def _write_file(self, path: str, content: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    async def _push_to_github(self) -> None:
        """Commit and push to GitHub repository."""
        primary_vault = self.vault_paths[0] if self.vault_paths else None
        if not primary_vault or not os.path.exists(os.path.join(primary_vault, ".git")):
            return

        def _do_git():
            try:
                subprocess.run(["git", "-C", primary_vault, "add", "20-CLIENTS/"], capture_output=True)
                subprocess.run(["git", "-C", primary_vault, "commit", "-m", "docs(c360): sync customer profile"], capture_output=True)
                subprocess.run(["git", "-C", primary_vault, "push", "origin", "master"], capture_output=True, timeout=15)
                logger.info("[C360] Pushed customer 360 updates to GitHub.")
            except Exception as e:
                logger.debug(f"[C360] Git push failed: {e}")

        await asyncio.to_thread(_do_git)
