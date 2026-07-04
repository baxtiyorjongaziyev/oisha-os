"""Channel Lead Extractor — Extract and process leads from Telegram channels → AmoCRM."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional, Any

logger = logging.getLogger(__name__)


class ChannelLeadExtractor:
    """Extract leads from channel messages and push to AmoCRM."""

    def __init__(self, amocrm_adapter: Optional[Any] = None, db=None):
        self.amocrm = amocrm_adapter
        self.db = db
        self.extracted_leads = []

    async def process_lead(
        self,
        username: str,
        user_id: int,
        first_name: str,
        last_name: str,
        source_channel: str,
        message_preview: str,
        category: str = "Business Trainer",
    ) -> dict:
        """Process a single lead and push to AmoCRM."""
        lead_data = {
            "name": f"{first_name} {last_name}".strip() or username,
            "phone": None,  # Extract from message if available
            "custom_fields": {
                "telegram_username": username,
                "telegram_id": user_id,
                "source_channel": source_channel,
                "message_preview": message_preview,
                "category": category,
                "discovered_at": datetime.now().isoformat(),
                "status": "discovered",
            },
        }

        # Try to extract phone from message
        phone = await self._extract_phone(message_preview)
        if phone:
            lead_data["phone"] = phone

        # Push to AmoCRM if available
        if self.amocrm:
            try:
                crm_lead = await self.amocrm.create_lead(
                    name=lead_data["name"],
                    phone=lead_data["phone"],
                    status="new",
                    tags=[category, source_channel, "telegram_discovered"],
                    custom_fields=lead_data["custom_fields"],
                )
                lead_data["crm_id"] = crm_lead.get("id")
                logger.info(f"[LEAD-EXTRACTOR] Lead created in AmoCRM: {lead_data['name']}")
            except Exception as exc:
                logger.error(f"[LEAD-EXTRACTOR] AmoCRM push failed: {exc}")

        # Save to local tracking
        if self.db:
            try:
                await self._save_to_db(lead_data)
            except Exception as exc:
                logger.warning(f"[LEAD-EXTRACTOR] DB save failed: {exc}")

        self.extracted_leads.append(lead_data)
        return lead_data

    async def batch_process_leads(self, leads: list) -> list:
        """Process multiple leads."""
        results = []
        for lead in leads:
            result = await self.process_lead(
                username=lead.get("username", ""),
                user_id=lead.get("user_id", 0),
                first_name=lead.get("first_name", ""),
                last_name=lead.get("last_name", ""),
                source_channel=lead.get("source_channel", ""),
                message_preview=lead.get("message_preview", ""),
            )
            results.append(result)
        return results

    @staticmethod
    async def _extract_phone(text: str) -> Optional[str]:
        """Extract phone number from text."""
        import re

        patterns = [
            r"\+998[0-9]{9}",  # +998XXXXXXXXX
            r"0[0-9]{9}",  # 0XXXXXXXXX
            r"\+\d{1,3}\s?\d{6,14}",  # International format
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group()
        return None

    async def _save_to_db(self, lead_data: dict) -> None:
        """Save lead to local database for tracking."""
        if not self.db:
            return

        try:
            # Create leads table if not exists
            await self.db.execute(
                """
                CREATE TABLE IF NOT EXISTS channel_discovered_leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    crm_id INTEGER,
                    name TEXT NOT NULL,
                    telegram_username TEXT UNIQUE,
                    telegram_id INTEGER,
                    phone TEXT,
                    source_channel TEXT,
                    message_preview TEXT,
                    category TEXT,
                    discovered_at TEXT,
                    status TEXT DEFAULT 'discovered',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            # Insert lead
            await self.db.execute(
                """
                INSERT INTO channel_discovered_leads
                (crm_id, name, telegram_username, telegram_id, phone,
                 source_channel, message_preview, category, discovered_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    lead_data.get("crm_id"),
                    lead_data.get("name"),
                    lead_data.get("custom_fields", {}).get("telegram_username"),
                    lead_data.get("custom_fields", {}).get("telegram_id"),
                    lead_data.get("phone"),
                    lead_data.get("custom_fields", {}).get("source_channel"),
                    lead_data.get("custom_fields", {}).get("message_preview"),
                    lead_data.get("custom_fields", {}).get("category"),
                    lead_data.get("custom_fields", {}).get("discovered_at"),
                    "discovered",
                ],
            )
            await self.db.commit()
        except Exception as exc:
            logger.error(f"[LEAD-EXTRACTOR] DB error: {exc}")

    async def get_recent_leads(self, limit: int = 20) -> list:
        """Get recently discovered leads."""
        if not self.db:
            return self.extracted_leads[:limit]

        try:
            rows = await self.db.execute(
                "SELECT * FROM channel_discovered_leads ORDER BY created_at DESC LIMIT ?",
                [limit],
            )
            return [dict(row) for row in rows] if rows else []
        except Exception as exc:
            logger.warning(f"[LEAD-EXTRACTOR] Query failed: {exc}")
            return self.extracted_leads[:limit]

    def report(self) -> str:
        """Generate extraction report."""
        lines = [
            "=" * 60,
            "👥 CHANNEL LEAD EXTRACTION REPORT",
            "=" * 60,
            f"Total extracted: {len(self.extracted_leads)}",
            "",
        ]

        for i, lead in enumerate(self.extracted_leads[:10], 1):
            lines.append(f"{i}. {lead.get('name', '?')}")
            lines.append(f"   @{lead.get('custom_fields', {}).get('telegram_username', '?')}")
            lines.append(f"   Source: {lead.get('custom_fields', {}).get('source_channel', '?')}")
            lines.append(f"   Status: {lead.get('custom_fields', {}).get('status', '?')}")
            lines.append("")

        return "\n".join(lines)
