"""Google Contacts, Telegram Contacts (drip), and Obsidian Second Brain adapters."""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, List

from .models import UnifiedClientProfile

logger = logging.getLogger(__name__)
_ILLEGAL_FS_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _safe_filename(name: str, max_len: int = 80) -> str:
    clean = _ILLEGAL_FS_RE.sub("-", name or "").strip(" .")
    return (re.sub(r"\s+", " ", clean) or "Mijoz")[:max_len]


def build_unified_notes(profile: UnifiedClientProfile) -> str:
    """Structured notes block shared by Google Contacts and Second Brain."""
    lines = []
    if profile.telegram_username:
        lines.append(f"Telegram: @{profile.telegram_username}")
    if profile.company:
        lines.append(f"Kompaniya: {profile.company}")
    if profile.activity:
        lines.append(f"Soha: {profile.activity}")
    if profile.region:
        lines.append(f"Hudud: {profile.region}")
    if profile.stage:
        lines.append(f"Holat: {profile.stage}")
    if profile.amocrm_lead_id:
        lines.append(f"amoCRM: https://jonbranding.amocrm.ru/leads/detail/{profile.amocrm_lead_id}")
    if profile.airtable_record_id:
        lines.append(f"Airtable ID: {profile.airtable_record_id}")
    if profile.notes:
        lines.append(profile.notes)
    return "\n".join(lines)


class GoogleContactsUnifiedAdapter:
    """Syncs UnifiedClientProfile to Google Contacts via GoogleContactsSync."""

    name = "google_contacts"

    def __init__(self, gcontacts: Any) -> None:
        self.gcontacts = gcontacts

    def sync_profile(self, profile: UnifiedClientProfile, *, dry_run: bool = True) -> str:
        if not profile.phone or not profile.full_name:
            return "skipped"
        if dry_run:
            return "would_update" if profile.google_resource_name else "would_create"
        phones = [profile.phone]
        if profile.google_resource_name and hasattr(self.gcontacts, "update_person"):
            ok = bool(
                self.gcontacts.update_person(
                    profile.google_resource_name,
                    profile.first_name,
                    profile.last_name,
                    phones,
                )
            )
            return "updated" if ok else "failed"
        if hasattr(self.gcontacts, "create_person"):
            res = self.gcontacts.create_person(
                profile.first_name,
                profile.last_name,
                phones,
                profile.tags[:5],
            )
            if res:
                profile.google_resource_name = str(res)
                return "created"
            return "failed"
        return "skipped"


class TelegramContactsUnifiedAdapter:
    """FloodWait-safe daily-capped Telegram contact sync adapter."""

    name = "telegram_contacts"

    def __init__(self, tg_client: Any, *, daily_limit: int = 100) -> None:
        self.tg_client = tg_client
        self.daily_limit = max(1, int(daily_limit))
        self.sent_today = 0

    async def sync_profile_async(
        self, profile: UnifiedClientProfile, *, dry_run: bool = True
    ) -> str:
        if not profile.phone or not (profile.telegram_id or profile.telegram_username):
            return "skipped"
        if self.sent_today >= self.daily_limit:
            return "deferred_daily_limit"
        if dry_run:
            return "would_upsert"
        from telethon import functions

        entity = await self.tg_client.get_input_entity(
            profile.telegram_username or profile.telegram_id
        )
        await self.tg_client(
            functions.contacts.AddContactRequest(
                id=entity,
                first_name=profile.first_name or profile.full_name,
                last_name=profile.last_name,
                phone=profile.phone,
                add_phone_privacy_exception=False,
            )
        )
        self.sent_today += 1
        return "updated"


class SecondBrainUnifiedAdapter:
    """Writes one clean named Markdown file per client in 20-CLIENTS/ (never _lead.md)."""

    name = "second_brain"

    def __init__(self, vault_paths: List[Path]) -> None:
        self.vault_paths = [Path(p) for p in vault_paths if Path(p).exists()]

    def render_markdown(self, profile: UnifiedClientProfile) -> str:
        tags_yaml = "\n".join(f"  - {t}" for t in (profile.tags or ["mijoz"]))
        tg_line = f"@{profile.telegram_username}" if profile.telegram_username else "—"
        amo_line = (
            f"https://jonbranding.amocrm.ru/leads/detail/{profile.amocrm_lead_id}"
            if profile.amocrm_lead_id
            else "—"
        )
        lines = [
            "---",
            f"title: \"{profile.full_name}\"",
            "type: mijoz-profili",
            f"telefon: \"{profile.phone}\"",
            f"telegram: \"{tg_line}\"",
            f"kompaniya: \"{profile.company}\"",
            f"soha: \"{profile.activity}\"",
            f"hudud: \"{profile.region}\"",
            f"bosqich: \"{profile.stage}\"",
            f"amocrm_contact_id: {profile.amocrm_contact_id or 'null'}",
            f"amocrm_lead_id: {profile.amocrm_lead_id or 'null'}",
            f"airtable_id: \"{profile.airtable_record_id}\"",
            f"updated: \"{profile.updated_at}\"",
            "tags:",
            tags_yaml,
            "---",
            "",
            f"# {profile.full_name}",
            "",
            "## Yagona aloqa kartasi",
            f"- **Telefon:** `{profile.phone}`",
            f"- **Telegram:** {tg_line}",
            f"- **Kompaniya / Brend:** {profile.company or '—'}",
            f"- **Soha:** {profile.activity or '—'}",
            f"- **Hudud:** {profile.region or '—'}",
            f"- **Holat / Bosqich:** {profile.stage or '—'}",
            f"- **amoCRM:** {amo_line}",
            f"- **Airtable ID:** `{profile.airtable_record_id or '—'}`",
            "",
        ]
        if profile.notes:
            lines.extend(["## Izohlar", "", profile.notes, ""])
        return "\n".join(lines)

    def sync_profile(self, profile: UnifiedClientProfile, *, dry_run: bool = True) -> str:
        if not self.vault_paths or not profile.full_name:
            return "skipped"
        if dry_run:
            return "would_write"
        filename = f"{_safe_filename(profile.full_name)}.md"
        content = self.render_markdown(profile)
        for vault in self.vault_paths:
            clients_dir = vault / "20-CLIENTS"
            clients_dir.mkdir(parents=True, exist_ok=True)
            (clients_dir / filename).write_text(content, encoding="utf-8")
        return "updated"
