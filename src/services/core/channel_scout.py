"""Oisha Channel Scout — Telegram business trainer channels analyzer."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# Target business trainer channels (REAL Uzbek B2B leads)
TARGET_CHANNELS = {
    # === TOP BUSINESS TRAINERS (UZBEKISTAN) ===
    "IbrahimGulyamov": {"category": "Business Coach", "region": "UZ", "priority": 1},
    "alisherisaev_blog": {"category": "Business Advisor", "region": "UZ", "priority": 1},
    "MFaktoruz": {"category": "Business Education", "region": "UZ", "priority": 1},
    "mylifeplanner_uz": {"category": "Personal Development", "region": "UZ", "priority": 1},
    "KozimkhonTorayev": {"category": "Business Mentor", "region": "UZ", "priority": 1},
    "TopBrains_uz": {"category": "Startup Hub", "region": "UZ", "priority": 1},
    "biz_masofadan": {"category": "Remote Business", "region": "UZ", "priority": 2},
    "UmidjoniUZ": {"category": "Business Training", "region": "UZ", "priority": 1},
    "MFaktor_school": {"category": "Business School", "region": "UZ", "priority": 1},
    "IkhtiyarDosmetov": {"category": "Life Coach", "region": "UZ", "priority": 2},
    "AlisherAvazov_blog": {"category": "Business Blog", "region": "UZ", "priority": 1},
    "mufeedmoliya": {"category": "Finance", "region": "UZ", "priority": 2},
    "MastersClubUZ": {"category": "Exclusive Club", "region": "UZ", "priority": 2},
    "najot_nur": {"category": "Tech Education", "region": "UZ", "priority": 2},
    "jahongir_polatov": {"category": "Advice Channel", "region": "UZ", "priority": 2},
    "boburmusa_official": {"category": "Business Coach", "region": "UZ", "priority": 1},
    "AzizAxtamov": {"category": "Entrepreneur", "region": "UZ", "priority": 2},
    "biznesrivoj": {"category": "Business Growth", "region": "UZ", "priority": 1},
    "sarvar_sales_blog": {"category": "Sales Training", "region": "UZ", "priority": 1},
    "hikmatkundi": {"category": "Wisdom Daily", "region": "UZ", "priority": 2},
    "sardor_valixanov": {"category": "Sales Coach", "region": "UZ", "priority": 1},
    "mehriniso_nur": {"category": "Finance Advisor", "region": "UZ", "priority": 2},
    "foydali_moliya": {"category": "Money Tips", "region": "UZ", "priority": 2},
    "SherzodMustafaev": {"category": "Business Coach", "region": "UZ", "priority": 1},
    "SherzodTursunov": {"category": "Business Strategy", "region": "UZ", "priority": 1},
    "alisher_avazov_blog": {"category": "Business Blog", "region": "UZ", "priority": 1},
    "azizjon_gapparov": {"category": "Entrepreneur", "region": "UZ", "priority": 2},
    "sanjar_maksudov": {"category": "Business Coach", "region": "UZ", "priority": 1},
    "akmal_nasridinov_sales": {"category": "Sales Trainer", "region": "UZ", "priority": 1},
    "zafar_khashimov": {"category": "Businessman", "region": "UZ", "priority": 2},
    "MountainBranding": {"category": "Marketing Agency", "region": "UZ", "priority": 2},
    "murod_nazarov": {"category": "Business Mentor", "region": "UZ", "priority": 2},
    "laziz_adhamov": {"category": "Coach", "region": "UZ", "priority": 2},
    "Perfect_Media_official": {"category": "Marketing", "region": "UZ", "priority": 2},
    "paiziev24": {"category": "Business", "region": "UZ", "priority": 2},
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
        """Extract engaged commenters as leads from channel posts."""
        if not self.client:
            return []

        leads = []
        try:
            entity = await self.client.get_entity(channel_name)
            messages = await self.client.get_messages(entity, limit=limit)

            for msg in messages:
                # Get replies/comments on this message
                try:
                    replies = await self.client.get_messages(entity, reply_to=msg.id, limit=5)

                    for reply in replies:
                        if reply.sender and reply.sender.username and not reply.sender.bot:
                            lead = {
                                "source_channel": channel_name,
                                "username": reply.sender.username,
                                "user_id": reply.sender.id,
                                "first_name": getattr(reply.sender, "first_name", ""),
                                "last_name": getattr(reply.sender, "last_name", ""),
                                "message_preview": (reply.text or "")[:100],
                                "engagement_type": "comment",
                                "post_date": msg.date.isoformat(),
                                "comment_date": reply.date.isoformat(),
                            }
                            leads.append(lead)
                except Exception as e:
                    logger.debug(f"[SCOUT] Could not get replies for {channel_name}: {e}")
                    continue

            logger.info(f"[SCOUT] Extracted {len(leads)} engaged commenters from {channel_name}")
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
