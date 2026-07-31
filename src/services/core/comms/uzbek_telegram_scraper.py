"""Telegram Scraper - Real implementation for Uzbek entrepreneurs."""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Optional

from telethon import TelegramClient
from telethon.tl.types import Channel, User

from src.services.core.uzbek_entrepreneurs_scraper import (
    ScrapedEntrepreneur,
    UzbekEntrepreneurScraper,
)

logger = logging.getLogger(__name__)


@dataclass
class TelegramProfile:
    id: int
    username: Optional[str]
    first_name: str
    last_name: str
    phone: Optional[str]
    bio: Optional[str]
    is_bot: bool
    is_verified: bool
    profile_url: str


class TelegramScraperReal(UzbekEntrepreneurScraper):
    """Real Telegram scraper using Telethon."""

    def __init__(self, db=None, client: Optional[TelegramClient] = None):
        super().__init__(db)
        self.client = client

    async def search_groups(
        self, keywords: list[str], limit: int = 50
    ) -> int:
        """Search Telegram groups for Uzbek entrepreneurs."""
        queue_id = await self.log_scraping_queue(
            "telegram", ",".join(keywords), "global", status="processing"
        )

        try:
            if not self.client:
                logger.error("[TELEGRAM] Telegram client not provided")
                await self.update_scraping_queue(queue_id, "failed", error_message="No client")
                return 0

            # Search for groups by keywords
            all_profiles = []

            for keyword in keywords:
                logger.info("[TELEGRAM] Searching for: %s", keyword)

                # Search for dialogs/channels
                async for dialog in self.client.iter_dialogs(search=keyword, limit=limit):
                    if isinstance(dialog.entity, Channel):
                        # Get members from the channel
                        profiles = await self._extract_channel_members(dialog.entity, limit=20)
                        all_profiles.extend(profiles)

                    elif isinstance(dialog.entity, User):
                        # Direct user match
                        profile = self._user_to_profile(dialog.entity)
                        if profile:
                            all_profiles.append(profile)

                # Rate limiting
                await asyncio.sleep(2)

            # Filter for Uzbek profiles
            uzbek_profiles = [
                p for p in all_profiles
                if self.is_uzbek_name(f"{p.first_name} {p.last_name}") or self.has_uzbek_connection(p.bio or "")
            ]

            # Save to database
            saved_count = 0
            for profile in uzbek_profiles:
                entrepreneur = ScrapedEntrepreneur(
                    full_name=f"{profile.first_name} {profile.last_name}".strip(),
                    first_name=profile.first_name,
                    last_name=profile.last_name,
                    phone=profile.phone,
                    email=None,  # Telegram doesn't expose email
                    company=None,
                    industry=None,
                    country="unknown",  # Telegram doesn't expose country
                    city=None,
                    linkedin_url=None,
                    instagram_url=None,
                    telegram_username=profile.username,
                    facebook_url=None,
                    scraping_source="telegram",
                    source_url=profile.profile_url,
                    lead_score=self.calculate_lead_score(
                        has_phone=bool(profile.phone),
                        has_email=False,
                        has_company=False,
                        is_ceo_level=profile.is_verified,
                    ),
                )

                if await self.save_entrepreneur(entrepreneur):
                    saved_count += 1

            await self.update_scraping_queue(queue_id, "completed", found_count=saved_count)
            logger.info(
                "[TELEGRAM] Scraping completed: %d profiles saved", saved_count
            )
            return saved_count

        except Exception as e:
            logger.error("[TELEGRAM] Scraping failed: %s", e)
            await self.update_scraping_queue(queue_id, "failed", error_message=str(e))
            raise

    async def _extract_channel_members(
        self, channel: Channel, limit: int
    ) -> list[TelegramProfile]:
        """Extract member profiles from a Telegram channel's commenters (engaged users)."""
        try:
            profiles = []
            seen_users = set()

            # Get recent messages (posts)
            messages = await self.client.get_messages(channel, limit=limit)

            for msg in messages:
                # GET COMMENTS ON THIS MESSAGE
                try:
                    comments = await self.client.get_messages(
                        channel,
                        reply_to=msg.id,  # ← Get replies to this message
                        limit=10
                    )

                    # Extract COMMENTERS as profiles
                    for comment in comments:
                        if comment.sender and isinstance(comment.sender, User) and not comment.sender.bot:
                            if comment.sender.id in seen_users:
                                continue
                            seen_users.add(comment.sender.id)
                            profile = self._user_to_profile(comment.sender)
                            if profile:
                                if comment.text:
                                    profile.bio = (profile.bio or "") + f" [Comment: {comment.text[:100]}]"
                                profiles.append(profile)
                except Exception as e:
                    logger.debug("Failed to get comments for message %s: %s", msg.id, e)

            return profiles

        except Exception as e:
            logger.error("[TELEGRAM] Failed to extract channel members: %s", e)
            return []

    async def extract_leads_from_channel(self, channel_name: str, limit: int = 20):
        """Extract commenters (actual customers) from channel posts."""
        leads = []
        try:
            entity = await self.client.get_entity(channel_name)
            
            # Get recent messages (posts)
            messages = await self.client.get_messages(entity, limit=limit)
            
            for msg in messages:
                # GET COMMENTS ON THIS MESSAGE
                try:
                    comments = await self.client.get_messages(
                        entity, 
                        reply_to=msg.id,  # ← Get replies to this message
                        limit=10
                    )
                    
                    # Extract COMMENTERS as leads
                    for comment in comments:
                        if comment.sender and getattr(comment.sender, "username", None):
                            lead = {
                                "source_channel": channel_name,
                                "username": comment.sender.username,        # @azizjon_gapparov
                                "user_id": comment.sender.id,
                                "first_name": getattr(comment.sender, "first_name", "") or "",
                                "last_name": getattr(comment.sender, "last_name", "") or "",
                                "message_preview": (comment.text or "")[:100],  # Comment content
                                "is_bot": getattr(comment.sender, "bot", False),
                            }
                            leads.append(lead)
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"[TELEGRAM] Failed to extract leads from channel {channel_name}: {e}")
            
        return leads

    def _user_to_profile(self, user: User) -> Optional[TelegramProfile]:
        """Convert Telethon User to TelegramProfile."""
        try:
            return TelegramProfile(
                id=user.id,
                username=user.username,
                first_name=user.first_name or "",
                last_name=user.last_name or "",
                phone=user.phone,
                bio=getattr(user, "about", None),
                is_bot=user.bot,
                is_verified=getattr(user, "verified", False),
                profile_url=f"https://t.me/{user.username}" if user.username else "",
            )

        except Exception as e:
            logger.error("[TELEGRAM] Failed to convert user: %s", e)
            return None

    async def search_by_username(
        self, username: str
    ) -> Optional[TelegramProfile]:
        """Search for a specific Telegram user by username."""
        try:
            if not self.client:
                logger.error("[TELEGRAM] Telegram client not provided")
                return None

            entity = await self.client.get_entity(username)

            if isinstance(entity, User):
                return self._user_to_profile(entity)

            return None

        except Exception as e:
            logger.error("[TELEGRAM] Username search failed: %s", e)
            return None

    async def search_uzbiz_diaspora_groups(self, limit: int = 100) -> int:
        """Search specifically for Uzbek diaspora groups."""
        # Common Uzbek diaspora group keywords
        uzbek_keywords = [
            "uzbek",
            "o'zbek",
            "tashkent",
            "samarkand",
            "bukhara",
            "uzbekistan",
            "uzbek diaspora",
            "o'zbekiston",
            "o'zbeklar",
        ]

        return await self.search_groups(uzbek_keywords, limit)


class TelegramGroupScraper(UzbekEntrepreneurScraper):
    """Scraper that focuses on specific Uzbek diaspora groups."""

    def __init__(self, db=None, client: Optional[TelegramClient] = None):
        super().__init__(db)
        self.client = client

    # Known Uzbek diaspora groups (usernames)
    UZBEK_GROUPS = [
        "uzbekistan_news",
        "tashkent_today",
        "ozbekiston_official",
        # Add more known groups
    ]

    async def scrape_known_groups(self, limit_per_group: int = 50) -> int:
        """Scrape known Uzbek diaspora groups."""
        queue_id = await self.log_scraping_queue(
            "telegram", "known_groups", "global", status="processing"
        )

        try:
            if not self.client:
                logger.error("[TELEGRAM] Telegram client not provided")
                await self.update_scraping_queue(queue_id, "failed", error_message="No client")
                return 0

            all_profiles = []

            for group_username in self.UZBEK_GROUPS:
                try:
                    logger.info("[TELEGRAM] Scraping group: @%s", group_username)

                    group = await self.client.get_entity(group_username)

                    if isinstance(group, Channel):
                        profiles = await self._extract_group_members(group, limit_per_group)
                        all_profiles.extend(profiles)

                    # Rate limiting
                    await asyncio.sleep(3)

                except Exception as e:
                    logger.warning(
                        "[TELEGRAM] Failed to scrape group @%s: %s", group_username, e
                    )
                    continue

            # Filter and save
            uzbek_profiles = [
                p for p in all_profiles
                if self.is_uzbek_name(f"{p.first_name} {p.last_name}")
            ]

            saved_count = 0
            for profile in uzbek_profiles:
                entrepreneur = ScrapedEntrepreneur(
                    full_name=f"{profile.first_name} {profile.last_name}".strip(),
                    first_name=profile.first_name,
                    last_name=profile.last_name,
                    phone=profile.phone,
                    email=None,
                    company=None,
                    industry=None,
                    country="unknown",
                    city=None,
                    linkedin_url=None,
                    instagram_url=None,
                    telegram_username=profile.username,
                    facebook_url=None,
                    scraping_source="telegram",
                    source_url=profile.profile_url,
                    lead_score=self.calculate_lead_score(
                        has_phone=bool(profile.phone),
                        has_email=False,
                        has_company=False,
                        is_ceo_level=profile.is_verified,
                    ),
                )

                if await self.save_entrepreneur(entrepreneur):
                    saved_count += 1

            await self.update_scraping_queue(queue_id, "completed", found_count=saved_count)
            logger.info(
                "[TELEGRAM] Known groups scraping completed: %d profiles saved",
                saved_count,
            )
            return saved_count

        except Exception as e:
            logger.error("[TELEGRAM] Known groups scraping failed: %s", e)
            await self.update_scraping_queue(queue_id, "failed", error_message=str(e))
            raise

    async def _extract_group_members(
        self, channel: Channel, limit: int
    ) -> list[TelegramProfile]:
        """Extract member profiles from a channel."""
        try:
            profiles = []

            async for member in self.client.iter_participants(channel, limit=limit):
                if isinstance(member, User) and not member.bot:
                    profile = self._user_to_profile(member)
                    if profile:
                        profiles.append(profile)

            return profiles

        except Exception as e:
            logger.error("[TELEGRAM] Failed to extract group members: %s", e)
            return []

    def _user_to_profile(self, user: User) -> Optional[TelegramProfile]:
        """Convert Telethon User to TelegramProfile."""
        try:
            return TelegramProfile(
                id=user.id,
                username=user.username,
                first_name=user.first_name or "",
                last_name=user.last_name or "",
                phone=user.phone,
                bio=getattr(user, "about", None),
                is_bot=user.bot,
                is_verified=getattr(user, "verified", False),
                profile_url=f"https://t.me/{user.username}" if user.username else "",
            )

        except Exception as e:
            logger.error("[TELEGRAM] Failed to convert user: %s", e)
            return None
