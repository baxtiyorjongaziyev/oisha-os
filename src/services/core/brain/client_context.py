"""Unified client context aggregator.

Gathers everything Oisha knows about one client — AmoCRM lead + Telegram
history (via OmnichannelContextFetcher), matching Airtable project records,
and the connected Instagram business profile — into a single structure that
both the Obsidian sync (`cross_channel_sync.py`) and the client Q&A layer
(`client_qa.py`) can consume.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.services.call_analytics.omnichannel_context import (
    OmnichannelContext,
    OmnichannelContextFetcher,
)

logger = logging.getLogger(__name__)


@dataclass
class ClientContext:
    """All known data about one client, aggregated across every channel."""

    lead_id: Optional[int] = None
    omnichannel: Optional[OmnichannelContext] = None
    airtable_projects: List[Dict[str, Any]] = field(default_factory=list)
    instagram_profile: Optional[Dict[str, Any]] = None

    @property
    def display_name(self) -> str:
        if self.omnichannel and (self.omnichannel.contact_name or self.omnichannel.lead_name):
            return self.omnichannel.contact_name or self.omnichannel.lead_name
        if self.airtable_projects:
            return str(self.airtable_projects[0].get("fields", {}).get("Name") or "")
        return "Noma'lum mijoz"

    def format_prompt_block(self) -> str:
        """Render every gathered source as Uzbek text blocks for an LLM prompt."""
        sections: List[str] = []

        if self.omnichannel:
            sections.append("## AmoCRM va Telegram ma'lumotlari\n" + self.omnichannel.format_crm_prompt_block())
            sections.append("## Telegram yozishmalari\n" + self.omnichannel.format_telegram_prompt_block())
        else:
            sections.append("## AmoCRM va Telegram ma'lumotlari\nTopilmadi.")

        if self.airtable_projects:
            lines = []
            for p in self.airtable_projects[:5]:
                fields = p.get("fields", {}) if isinstance(p, dict) else {}
                name = fields.get("Name") or fields.get("Loyiha nomi") or p.get("id", "")
                stage = fields.get("Stage") or fields.get("Bosqich") or ""
                deadline = fields.get("Deadline") or fields.get("Muddat") or ""
                lines.append(f"- {name} | Bosqich: {stage or 'N/A'} | Muddat: {deadline or 'N/A'}")
            sections.append("## Airtable loyihalari\n" + "\n".join(lines))
        else:
            sections.append("## Airtable loyihalari\nMos loyiha topilmadi.")

        if self.instagram_profile and self.instagram_profile.get("ok"):
            p = self.instagram_profile
            sections.append(
                "## Instagram (kompaniya akkaunti)\n"
                f"- Username: @{p.get('username', '')}\n"
                f"- Followers: {p.get('followers_count', 'N/A')}\n"
                "- Eslatma: Instagram DM tarixi bo'yicha alohida mijoz darajasidagi arxiv "
                "hozircha saqlanmaydi; faqat kompaniya akkaunt profili ko'rsatilgan."
            )

        return "\n\n".join(sections)


class ClientContextAggregator:
    """Fetches and combines AmoCRM, Telegram, Airtable, and Instagram data for one client."""

    def __init__(self, amocrm: Any, db: Any = None, tg_client: Any = None, airtable: Any = None) -> None:
        self.amocrm = amocrm
        self.db = db
        self.tg_client = tg_client
        self._airtable = airtable

    def _get_airtable(self) -> Optional[Any]:
        if self._airtable is not None:
            return self._airtable
        try:
            from src.services.core.airtable_sync import AirtableSync

            self._airtable = AirtableSync()
        except Exception as exc:
            logger.debug("[CLIENT_CONTEXT] AirtableSync unavailable: %s", exc)
            self._airtable = None
        return self._airtable

    async def _resolve_lead_id(self, lead_id: Optional[int], name: str, phone: str) -> Optional[int]:
        if lead_id:
            return lead_id
        if not self.amocrm:
            return None
        query = phone or name
        if not query:
            return None
        searcher = getattr(self.amocrm, "search_leads", None)
        if not callable(searcher):
            return None
        try:
            results = await searcher(query, limit=5)
        except Exception as exc:
            logger.warning("[CLIENT_CONTEXT] search_leads failed for %r: %s", query, exc)
            return None
        if not results:
            return None
        return results[0].get("id")

    async def _fetch_airtable_matches(self, name: str, phone: str) -> List[Dict[str, Any]]:
        airtable = self._get_airtable()
        if not airtable or not (name or phone):
            return []
        try:
            projects = await asyncio.to_thread(airtable.get_projects)
        except Exception as exc:
            logger.debug("[CLIENT_CONTEXT] Airtable get_projects failed: %s", exc)
            return []

        needles = [n.strip().lower() for n in (name, phone) if n and n.strip()]
        if not needles:
            return []

        matches: List[Dict[str, Any]] = []
        for record in projects or []:
            fields = record.get("fields", {}) if isinstance(record, dict) else {}
            haystack = " ".join(str(v) for v in fields.values() if isinstance(v, (str, int, float))).lower()
            if any(needle in haystack for needle in needles):
                matches.append(record)
        return matches

    def _fetch_instagram_profile(self) -> Optional[Dict[str, Any]]:
        try:
            from src.services.core.instagram.graph_client import InstagramGraphClient

            client = InstagramGraphClient()
            if not client.configured:
                return None
            return client.get_profile()
        except Exception as exc:
            logger.debug("[CLIENT_CONTEXT] Instagram profile fetch failed: %s", exc)
            return None

    async def gather(
        self,
        lead_id: Optional[int] = None,
        name: str = "",
        phone: str = "",
    ) -> ClientContext:
        """Resolve the client across every channel and return a unified context."""
        resolved_lead_id = await self._resolve_lead_id(lead_id, name, phone)

        omnichannel: Optional[OmnichannelContext] = None
        if resolved_lead_id and self.amocrm:
            fetcher = OmnichannelContextFetcher(amocrm=self.amocrm, tg_client=self.tg_client, db=self.db)
            try:
                omnichannel = await fetcher.fetch_lead_omnichannel_context(
                    lead_id=resolved_lead_id, caller_phone=phone
                )
            except Exception as exc:
                logger.warning("[CLIENT_CONTEXT] omnichannel fetch failed for lead %s: %s", resolved_lead_id, exc)

        airtable_projects = await self._fetch_airtable_matches(
            name or (omnichannel.contact_name if omnichannel else "") or (omnichannel.lead_name if omnichannel else ""),
            phone or (omnichannel.contact_phone if omnichannel else ""),
        )

        instagram_profile = await asyncio.to_thread(self._fetch_instagram_profile)

        return ClientContext(
            lead_id=resolved_lead_id,
            omnichannel=omnichannel,
            airtable_projects=airtable_projects,
            instagram_profile=instagram_profile,
        )
