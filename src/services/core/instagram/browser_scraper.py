"""
Playwright-based Instagram scraper.
"""
from __future__ import annotations

import logging
from typing import Optional

from src.services.core.instagram.models import InstagramProfile
from src.services.core.uzbek_entrepreneurs_scraper import (
    ScrapedEntrepreneur,
    UzbekEntrepreneurScraper,
)

logger = logging.getLogger(__name__)


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

            url = f"https://www.instagram.com/explore/tags/{hashtag}/"
            await self._page.goto(url)

            await self._page.wait_for_selector("article")

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
            username_elem = await post.query_selector("a[href*='/']")
            username = await username_elem.inner_text() if username_elem else ""

            profile_url = await username_elem.get_attribute("href") if username_elem else ""

            if profile_url:
                await self._page.goto(profile_url)
                await self._page.wait_for_selector("header")

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
        return profile.followers_count > 1000

    async def _close_browser(self) -> None:
        """Close browser."""
        if self._page:
            await self._page.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("[INSTAGRAM] Browser closed")
