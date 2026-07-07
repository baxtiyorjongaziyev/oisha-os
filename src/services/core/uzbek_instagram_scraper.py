"""Instagram Scraper - Real implementation for Uzbek entrepreneurs."""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Optional

import httpx

from src.services.core.uzbek_entrepreneurs_scraper import (
    ScrapedEntrepreneur,
    UzbekEntrepreneurScraper,
)

logger = logging.getLogger(__name__)


@dataclass
class InstagramProfile:
    username: str
    full_name: str
    bio: str
    followers_count: int
    following_count: int
    posts_count: int
    profile_url: str
    is_business: bool
    category: Optional[str]
    phone: Optional[str]
    email: Optional[str]


class InstagramScraperReal(UzbekEntrepreneurScraper):
    """Real Instagram scraper using Instagram Graph API or browser automation."""

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
            # Method 1: Instagram Graph API (if access token provided)
            if self.access_token:
                profiles = await self._search_via_graph_api(hashtag, limit)
            else:
                # Method 2: Public Instagram scraping (limited)
                profiles = await self._search_via_public_api(hashtag, limit)

            # Filter for Uzbek profiles
            uzbek_profiles = [
                p for p in profiles
                if self.is_uzbek_name(p.full_name) or self.has_uzbek_connection(p.bio)
            ]

            # Save to database
            saved_count = 0
            for profile in uzbek_profiles:
                entrepreneur = ScrapedEntrepreneur(
                    full_name=profile.full_name,
                    first_name=profile.full_name.split()[0] if profile.full_name else "",
                    last_name=" ".join(profile.full_name.split()[1:]) if len(profile.full_name.split()) > 1 else "",
                    phone=profile.phone,
                    email=profile.email,
                    company=None,  # Instagram doesn't have company field
                    industry=profile.category,
                    country="unknown",  # Instagram doesn't expose country
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
            # Instagram Graph API endpoint for hashtag search
            hashtag_id = await self._get_hashtag_id(hashtag)
            if not hashtag_id:
                logger.error("[INSTAGRAM] Could not get hashtag ID for: %s", hashtag)
                return []

            url = f"https://graph.facebook.com/v19.0/{hashtag_id}/recent_media"

            params = {
                "user_id": "me",  # Replace with actual Instagram Business Account ID
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
                # Get user info from media
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
                "user_id": "me",  # Replace with actual Instagram Business Account ID
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
                full_name=data.get("username", ""),  # Instagram doesn't have separate full name
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
            # Public Instagram hashtag page (requires authentication)
            url = f"https://www.instagram.com/explore/tags/{hashtag}/"

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }

            response = await self._client.get(url, headers=headers)

            if response.status_code != 200:
                logger.warning("[INSTAGRAM] Public access requires authentication")
                return []

            # Parse HTML to extract profiles (Instagram uses React, requires JS rendering)
            # This is simplified - actual implementation would need Playwright/Selenium
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


# Alternative: Browser automation with Playwright
class InstagramScraperBrowser(UzbekEntrepreneurScraper):
    """Instagram scraper using Playwright browser automation."""

    def __init__(self, db=None):
        super().__init__(db)
        self._playwright = None
        self._browser = None
        self._page = None

    async def _init_browser(self) -> None:
        """Initialize Playwright browser."""
        try:
            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=True)
            self._page = await self._browser.new_page()
            logger.info("[INSTAGRAM] Browser initialized")

        except ImportError:
            logger.error("[INSTAGRAM] Playwright not installed")
            raise
        except Exception as e:
            logger.error("[INSTAGRAM] Browser init failed: %s", e)
            raise

    async def search_by_hashtag(
        self, hashtag: str, limit: int = 100
    ) -> int:
        """Search Instagram using browser automation."""
        queue_id = await self.log_scraping_queue(
            "instagram", f"#{hashtag}", "global", status="processing"
        )

        try:
            await self._init_browser()

            # Navigate to Instagram hashtag page
            url = f"https://www.instagram.com/explore/tags/{hashtag}/"
            await self._page.goto(url)

            # Wait for posts to load
            await self._page.wait_for_selector("article")

            # Extract profiles from posts
            profiles = []
            posts = await self._page.query_selector_all("article")

            for post in posts[:limit]:
                try:
                    profile = await self._extract_profile_from_post(post)
                    if profile and (self.is_uzbek_name(profile.full_name) or self.has_uzbek_connection(profile.bio)):
                        profiles.append(profile)
                except Exception as e:
                    logger.warning("[INSTAGRAM] Failed to extract profile: %s", e)
                    continue

            # Save to database
            saved_count = 0
            for profile in profiles:
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
            logger.info("[INSTAGRAM] Browser scraping completed: %d profiles", saved_count)
            return saved_count

        except Exception as e:
            logger.error("[INSTAGRAM] Browser scraping failed: %s", e)
            await self.update_scraping_queue(queue_id, "failed", error_message=str(e))
            raise
        finally:
            await self._close_browser()

    async def _extract_profile_from_post(self, post) -> Optional[InstagramProfile]:
        """Extract profile data from Instagram post."""
        try:
            # Get username from post
            username_elem = await post.query_selector("a[href*='/']")
            username = await username_elem.inner_text() if username_elem else ""

            # Get profile URL
            profile_url = await username_elem.get_attribute("href") if username_elem else ""

            # Navigate to profile page for more details
            if profile_url:
                await self._page.goto(profile_url)
                await self._page.wait_for_selector("header")

                # Extract profile details
                full_name_elem = await self._page.query_selector("h1")
                full_name = await full_name_elem.inner_text() if full_name_elem else username

                bio_elem = await self._page.query_selector("div.-vDIg")
                bio = await bio_elem.inner_text() if bio_elem else ""

                followers_elem = await self._page.query_selector("a[href*='/followers/']")
                followers_text = await followers_elem.inner_text() if followers_elem else "0"
                followers_count = int(followers_text.replace(",", "").replace(" followers", ""))

                return InstagramProfile(
                    username=username,
                    full_name=full_name,
                    bio=bio,
                    followers_count=followers_count,
                    following_count=0,
                    posts_count=0,
                    profile_url=profile_url,
                    is_business=False,
                    category=None,
                    phone=None,
                    email=None,
                )

            return None

        except Exception as e:
            logger.error("[INSTAGRAM] Profile extraction failed: %s", e)
            return None

    def _is_business_account(self, profile: InstagramProfile) -> bool:
        """Check if profile is a business account."""
        return profile.followers_count > 1000  # Simple heuristic

    async def _close_browser(self) -> None:
        """Close browser."""
        if self._page:
            await self._page.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("[INSTAGRAM] Browser closed")
