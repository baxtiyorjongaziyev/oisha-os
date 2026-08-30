"""
API-based Instagram scraper for Uzbek entrepreneurs.
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from src.services.core.instagram.models import InstagramProfile
from src.services.core.uzbek_entrepreneurs_scraper import (
    ScrapedEntrepreneur,
    UzbekEntrepreneurScraper,
)

logger = logging.getLogger(__name__)


class InstagramScraperReal(UzbekEntrepreneurScraper):
    """Real Instagram scraper using Instagram Graph API or public endpoints."""

    def __init__(self, db=None, access_token: Optional[str] = None):
        super().__init__(db)
        self.access_token = access_token
        self._client = httpx.AsyncClient(timeout=30.0)

    async def search_by_hashtag(
        self, hashtag: str, limit: int = 100
    ) -> int:
        """Search Instagram for Uzbek entrepreneurs by hashtag."""
        queue_id = await self.log_scraping_queue(
            "instagram", f"#{hashtag}", "global", status="processing"
        )

        try:
            if self.access_token:
                profiles = await self._search_via_graph_api(hashtag, limit)
            else:
                profiles = await self._search_via_public_api(hashtag, limit)

            uzbek_profiles = [
                p for p in profiles
                if self.is_uzbek_name(p.full_name) or self.has_uzbek_connection(p.bio)
            ]

            saved_count = 0
            for profile in uzbek_profiles:
                entrepreneur = ScrapedEntrepreneur(
                    full_name=profile.full_name,
                    first_name=profile.full_name.split()[0] if profile.full_name else "",
                    last_name=" ".join(profile.full_name.split()[1:]) if len(profile.full_name.split()) > 1 else "",
                    phone=profile.phone,
                    email=profile.email,
                    company=None,
                    industry=profile.category,
                    country="unknown",
                    city=None,
                    linkedin_url=None,
                    instagram_url=profile.profile_url,
                    telegram_username=None,
                    facebook_url=None,
                    scraping_source="instagram",
                    source_url=profile.profile_url,
                    lead_score=self.calculate_lead_score(
                        has_phone=bool(profile.phone),
                        has_email=bool(profile.email),
                        has_company=False,
                        is_ceo_level=self._is_business_account(profile),
                    ),
                )

                if await self.save_entrepreneur(entrepreneur):
                    saved_count += 1

            await self.update_scraping_queue(queue_id, "completed", found_count=saved_count)
            logger.info(
                "[INSTAGRAM] Scraping completed: %d profiles saved", saved_count
            )
            return saved_count

        except Exception as e:
            logger.error("[INSTAGRAM] Scraping failed: %s", e)
            await self.update_scraping_queue(queue_id, "failed", error_message=str(e))
            raise

    async def _search_via_graph_api(
        self, hashtag: str, limit: int
    ) -> list[InstagramProfile]:
        """Search using Instagram Graph API."""
        try:
            hashtag_id = await self._get_hashtag_id(hashtag)
            if not hashtag_id:
                logger.error("[INSTAGRAM] Could not get hashtag ID for: %s", hashtag)
                return []

            url = f"https://graph.facebook.com/v19.0/{hashtag_id}/recent_media"

            params = {
                "user_id": "me",
                "fields": "id,caption,media_type,permalink,like_count,comments_count",
                "limit": limit,
                "access_token": self.access_token,
            }

            response = await self._client.get(url, params=params)

            if response.status_code != 200:
                logger.error("[INSTAGRAM] API error: %s", response.text)
                return []

            data = response.json()
            profiles = []

            for media in data.get("data", []):
                user_id = media.get("id", "").split("_")[0]
                profile = await self._get_user_profile(user_id)
                if profile:
                    profiles.append(profile)

            return profiles

        except Exception as e:
            logger.error("[INSTAGRAM] Graph API failed: %s", e)
            return []

    async def _get_hashtag_id(self, hashtag: str) -> Optional[str]:
        """Get Instagram hashtag ID from hashtag name."""
        try:
            url = "https://graph.facebook.com/v19.0/ig_hashtag_search"

            params = {
                "user_id": "me",
                "q": hashtag,
                "access_token": self.access_token,
            }

            response = await self._client.get(url, params=params)

            if response.status_code != 200:
                return None

            data = response.json()
            results = data.get("data", [])
            if results:
                return results[0].get("id")

            return None

        except Exception as e:
            logger.error("[INSTAGRAM] Hashtag ID lookup failed: %s", e)
            return None

    async def _get_user_profile(self, user_id: str) -> Optional[InstagramProfile]:
        """Get Instagram user profile by ID."""
        try:
            url = f"https://graph.facebook.com/v19.0/{user_id}"

            params = {
                "fields": "username,biography,followers_count,follows_count,media_count,profile_picture_url,is_business_account,category,phone,email",
                "access_token": self.access_token,
            }

            response = await self._client.get(url, params=params)

            if response.status_code != 200:
                return None

            data = response.json()

            return InstagramProfile(
                username=data.get("username", ""),
                full_name=data.get("username", ""),
                bio=data.get("biography", ""),
                followers_count=data.get("followers_count", 0),
                following_count=data.get("follows_count", 0),
                posts_count=data.get("media_count", 0),
                profile_url=f"https://instagram.com/{data.get('username', '')}",
                is_business=data.get("is_business_account", False),
                category=data.get("category"),
                phone=data.get("phone"),
                email=data.get("email"),
            )

        except Exception as e:
            logger.error("[INSTAGRAM] User profile fetch failed: %s", e)
            return None

    async def _search_via_public_api(
        self, hashtag: str, limit: int
    ) -> list[InstagramProfile]:
        """Search using public Instagram (limited)."""
        try:
            url = f"https://www.instagram.com/explore/tags/{hashtag}/"

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }

            response = await self._client.get(url, headers=headers)

            if response.status_code != 200:
                logger.warning("[INSTAGRAM] Public access requires authentication")
                return []

            logger.warning(
                "[INSTAGRAM] Public scraping requires Playwright for JS rendering"
            )
            return []

        except Exception as e:
            logger.error("[INSTAGRAM] Public search failed: %s", e)
            return []

    def _is_business_account(self, profile: InstagramProfile) -> bool:
        """Check if profile is a business account."""
        return profile.is_business or profile.category is not None

    async def close(self) -> None:
        """Close HTTP client."""
        await self._client.aclose()
