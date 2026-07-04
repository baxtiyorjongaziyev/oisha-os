"""Oisha Channel Scout — Telegram business trainer channels analyzer."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# Target business trainer channels (UZBEK + RUSSIAN)
TARGET_CHANNELS = {
    # === UZBEK BUSINESS TRAINERS ===
    "business_uz": {"category": "General Business", "region": "UZ", "priority": 1},
    "entrepreneur_uz": {"category": "Entrepreneurship", "region": "UZ", "priority": 1},
    "startup_uz": {"category": "Startups", "region": "UZ", "priority": 2},
    "biznes_trener_uz": {"category": "Business Training", "region": "UZ", "priority": 1},
    "marketing_uz": {"category": "Marketing", "region": "UZ", "priority": 2},
    "sales_training_uz": {"category": "Sales Training", "region": "UZ", "priority": 1},

    # === RUSSIAN BUSINESS TRAINERS (CIS) ===
    "predprinimateli": {"category": "Entrepreneurs", "region": "RU", "priority": 2},
    "biznes_coach": {"category": "Business Coaching", "region": "RU", "priority": 2},
    "prodazhi_master": {"category": "Sales Mastery", "region": "RU", "priority": 2},
    "maркeting_bosс": {"category": "Marketing", "region": "RU", "priority": 2},

    # === ENGLISH GLOBAL ===
    "entrepreneurship": {"category": "Global Entrepreneurship", "region": "EN", "priority": 3},
    "business_growth": {"category": "Business Growth", "region": "EN", "priority": 3},
}

class ChannelScout:
    """Scan Telegram business trainer channels for leads."""

    def __init__(self, client=None):
        self.client = client
        self.channels = TARGET_CHANNELS
        self.leads = []
        self.scan_results = {}

    async def analyze_channel(self, channel_name: str) -> dict:
        """Get channel stats and activity."""
        if not self.client:
            logger.warning("[SCOUT] No Telethon client provided")
            return {}

        try:
            entity = await self.client.get_entity(channel_name)

            # Channel info
            info = {
                "name": entity.title,
                "username": entity.username or channel_name,
                "members": getattr(entity, "participants_count", 0),
                "description": getattr(entity, "about", ""),
                "verified": getattr(entity, "verified", False),
                "scanned_at": datetime.now().isoformat(),
            }

            # Get recent messages (last 50)
            try:
                messages = await self.client.get_messages(entity, limit=50)
                info["recent_posts"] = len(messages) if messages else 0
                info["avg_engagement"] = await self._calc_engagement(messages)
            except Exception as e:
                logger.warning(f"[SCOUT] Can't get messages from {channel_name}: {e}")
                info["recent_posts"] = 0

            return info
        except Exception as exc:
            logger.error(f"[SCOUT] Channel {channel_name} analysis failed: {exc}")
            return {}

    async def _calc_engagement(self, messages) -> float:
        """Calculate avg reactions/forwards."""
        if not messages:
            return 0.0
        total = 0
        for msg in messages:
            reactions = len(msg.reactions.results) if msg.reactions else 0
            forwards = msg.forwards or 0
            total += reactions + (forwards // 10)  # Weight forwards less
        return round(total / len(messages), 2)

    async def extract_leads_from_channel(self, channel_name: str, limit: int = 20) -> list:
        """Extract potential trainer profiles from channel messages."""
        if not self.client:
            return []

        leads = []
        try:
            entity = await self.client.get_entity(channel_name)
            messages = await self.client.get_messages(entity, limit=limit)

            for msg in messages:
                if msg.sender:
                    lead = {
                        "source_channel": channel_name,
                        "username": msg.sender.username or f"user_{msg.sender.id}",
                        "user_id": msg.sender.id,
                        "first_name": getattr(msg.sender, "first_name", ""),
                        "last_name": getattr(msg.sender, "last_name", ""),
                        "is_bot": getattr(msg.sender, "bot", False),
                        "message_preview": (msg.text or "")[:100],
                        "message_date": msg.date.isoformat(),
                        "extracted_at": datetime.now().isoformat(),
                    }
                    leads.append(lead)

            logger.info(f"[SCOUT] Extracted {len(leads)} potential leads from {channel_name}")
            return leads
        except Exception as exc:
            logger.error(f"[SCOUT] Lead extraction from {channel_name} failed: {exc}")
            return []

    async def scan_all_channels(self) -> dict:
        """Scan all target channels and prioritize."""
        results = {}
        for channel in self.channels:
            logger.info(f"[SCOUT] Scanning {channel}...")
            info = await self.analyze_channel(channel)
            if info:
                info["priority"] = self.channels[channel]["priority"]
                info["category"] = self.channels[channel]["category"]
                results[channel] = info

        # Sort by members (descending)
        ranked = dict(sorted(results.items(), key=lambda x: x[1].get("members", 0), reverse=True))
        self.scan_results = ranked
        return ranked

    def get_top_channels(self, limit: int = 5) -> list:
        """Get top N channels by activity/members."""
        if not self.scan_results:
            return []

        channels = list(self.scan_results.items())[:limit]
        top = [
            {
                "name": name,
                "members": data.get("members"),
                "posts": data.get("recent_posts"),
                "engagement": data.get("avg_engagement"),
                "priority": data.get("priority"),
                "category": data.get("category"),
            }
            for name, data in channels
        ]
        return top

    def report(self) -> str:
        """Generate scan report."""
        if not self.scan_results:
            return "[SCOUT] No channels scanned yet"

        lines = ["=" * 60, "📊 CHANNEL SCOUT REPORT", "=" * 60, ""]

        for i, (name, data) in enumerate(self.scan_results.items(), 1):
            lines.append(f"{i}. @{name}")
            lines.append(f"   Members: {data.get('members', '?')}")
            lines.append(f"   Recent posts: {data.get('recent_posts', '?')}")
            lines.append(f"   Engagement: {data.get('avg_engagement', '?')}")
            lines.append(f"   Category: {data.get('category', '?')}")
            lines.append("")

        return "\n".join(lines)
