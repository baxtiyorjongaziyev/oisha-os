"""LinkedIn Scraper - Real implementation for Uzbek entrepreneurs."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import httpx

from src.services.core.uzbek_entrepreneurs_scraper import (
    ScrapedEntrepreneur,
    UzbekEntrepreneurScraper,
)

logger = logging.getLogger(__name__)


@dataclass
class LinkedInProfile:
    id: str
    name: str
    headline: str
    location: str
    company: Optional[str]
    industry: Optional[str]
    profile_url: str
    phone: Optional[str]
    email: Optional[str]


class LinkedInScraperReal(UzbekEntrepreneurScraper):
    """Real LinkedIn scraper using LinkedIn API or browser automation."""

    def __init__(self, db=None, api_key: Optional[str] = None):
        super().__init__(db)
        self.api_key = api_key
        self._client = httpx.AsyncClient(
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            },
            timeout=30.0,
        )

    async def search_by_keyword(
        self, keyword: str, country: str = "US", limit: int = 50
    ) -> int:
        """Search LinkedIn for Uzbek entrepreneurs by keyword."""
        queue_id = await self.log_scraping_queue(
            "linkedin", keyword, country, status="processing"
        )

        try:
            # Method 1: LinkedIn Sales Navigator API (if API key provided)
            if self.api_key:
                profiles = await self._search_via_sales_nav_api(keyword, country, limit)
            else:
                # Method 2: Public LinkedIn search (limited)
                profiles = await self._search_via_public_api(keyword, country, limit)

            # Filter for Uzbek names
            uzbek_profiles = [
                p for p in profiles if self.is_uzbek_name(p.name) or self.has_uzbek_connection(p.headline)
            ]

            # Save to database
            saved_count = 0
            for profile in uzbek_profiles:
                entrepreneur = ScrapedEntrepreneur(
                    full_name=profile.name,
                    first_name=profile.name.split()[0] if profile.name else "",
                    last_name=" ".join(profile.name.split()[1:]) if len(profile.name.split()) > 1 else "",
                    phone=profile.phone,
                    email=profile.email,
                    company=profile.company,
                    industry=profile.industry,
                    country=country,
                    city=profile.location,
                    linkedin_url=profile.profile_url,
                    instagram_url=None,
                    telegram_username=None,
                    facebook_url=None,
                    scraping_source="linkedin",
                    source_url=profile.profile_url,
                    lead_score=self.calculate_lead_score(
                        has_phone=bool(profile.phone),
                        has_email=bool(profile.email),
                        has_company=bool(profile.company),
                        is_ceo_level=self._is_ceo_level(profile.headline),
                    ),
                )

                if await self.save_entrepreneur(entrepreneur):
                    saved_count += 1

            await self.update_scraping_queue(queue_id, "completed", found_count=saved_count)
            logger.info(
                "[LINKEDIN] Scraping completed: %d profiles saved", saved_count
            )
            return saved_count

        except Exception as e:
            logger.error("[LINKEDIN] Scraping failed: %s", e)
            await self.update_scraping_queue(queue_id, "failed", error_message=str(e))
            raise

    async def _search_via_sales_nav_api(
        self, keyword: str, country: str, limit: int
    ) -> list[LinkedInProfile]:
        """Search using LinkedIn Sales Navigator API."""
        try:
            # Sales Navigator API endpoint
            url = "https://api.linkedin.com/v2/search"

            params = {
                "keywords": keyword,
                "facetGeoRegion": f"urn:li:country:{country}",
                "count": limit,
            }

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "X-Restli-Protocol-Version": "2.0.0",
            }

            response = await self._client.get(url, params=params, headers=headers)

            if response.status_code != 200:
                logger.error("[LINKEDIN] API error: %s", response.text)
                return []

            data = response.json()
            profiles = []

            for element in data.get("elements", []):
                # Parse LinkedIn profile data
                # This is simplified - actual response structure is more complex
                profile = self._parse_linkedin_element(element)
                if profile:
                    profiles.append(profile)

            return profiles

        except Exception as e:
            logger.error("[LINKEDIN] Sales Navigator API failed: %s", e)
            return []

    async def _search_via_public_api(
        self, keyword: str, country: str, limit: int
    ) -> list[LinkedInProfile]:
        """Search using public LinkedIn (limited)."""
        try:
            # Public LinkedIn search (Google dork approach)
            search_query = f'site:linkedin.com/in "{keyword}" "{country}"'

            # This would use Google Custom Search API or similar
            # For now, return empty list as this requires additional setup
            logger.warning(
                "[LINKEDIN] Public search requires Google Custom Search API, skipping"
            )
            return []

        except Exception as e:
            logger.error("[LINKEDIN] Public search failed: %s", e)
            return []

    def _parse_linkedin_element(self, element: dict) -> Optional[LinkedInProfile]:
        """Parse LinkedIn API response element."""
        try:
            # Extract basic profile info
            # This is a simplified parser - actual structure varies
            profile_data = element.get("element", {})

            name = (
                profile_data.get("name", {})
                .get("localized", {})
                .get("en_US", "")
            )
            headline = (
                profile_data.get("headline", {})
                .get("localized", {})
                .get("en_US", "")
            )
            location = (
                profile_data.get("location", {})
                .get("country", "")
            )

            profile_url = f"https://linkedin.com/in/{profile_data.get('publicIdentifier', '')}"

            return LinkedInProfile(
                id=profile_data.get("entityUrn", ""),
                name=name,
                headline=headline,
                location=location,
                company=None,  # Would need additional parsing
                industry=None,  # Would need additional parsing
                profile_url=profile_url,
                phone=None,  # LinkedIn doesn't expose phone
                email=None,  # LinkedIn doesn't expose email
            )

        except Exception as e:
            logger.error("[LINKEDIN] Failed to parse element: %s", e)
            return None

    def _is_ceo_level(self, headline: str) -> bool:
        """Check if headline indicates CEO/founder level."""
        if not headline:
            return False

        ceo_keywords = [
            "ceo",
            "founder",
            "co-founder",
            "owner",
            "president",
            "director",
            "principal",
            "partner",
        ]

        headline_lower = headline.lower()
        return any(keyword in headline_lower for keyword in ceo_keywords)

    async def close(self) -> None:
        """Close HTTP client."""
        await self._client.aclose()


# Alternative: Browser automation with Playwright
class LinkedInScraperBrowser(UzbekEntrepreneurScraper):
    """LinkedIn scraper using Playwright browser automation."""

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
            logger.info("[LINKEDIN] Browser initialized")

        except ImportError:
            logger.error("[LINKEDIN] Playwright not installed")
            raise
        except Exception as e:
            logger.error("[LINKEDIN] Browser init failed: %s", e)
            raise

    async def search_by_keyword(
        self, keyword: str, country: str = "US", limit: int = 50
    ) -> int:
        """Search LinkedIn using browser automation."""
        queue_id = await self.log_scraping_queue(
            "linkedin", keyword, country, status="processing"
        )

        try:
            await self._init_browser()

            # Navigate to LinkedIn search
            search_url = f"https://www.linkedin.com/search/results/people/?keywords={keyword}&origin=FACETED_SEARCH"
            await self._page.goto(search_url)

            # Wait for results to load
            await self._page.wait_for_selector(".search-results__list")

            # Extract profiles
            profiles = []
            profile_elements = await self._page.query_selector_all(".search-result")

            for element in profile_elements[:limit]:
                try:
                    profile = await self._extract_profile_from_element(element)
                    if profile and (self.is_uzbek_name(profile.name) or self.has_uzbek_connection(profile.headline)):
                        profiles.append(profile)
                except Exception as e:
                    logger.warning("[LINKEDIN] Failed to extract profile: %s", e)
                    continue

            # Save to database
            saved_count = 0
            for profile in profiles:
                entrepreneur = ScrapedEntrepreneur(
                    full_name=profile.name,
                    first_name=profile.name.split()[0] if profile.name else "",
                    last_name=" ".join(profile.name.split()[1:]) if len(profile.name.split()) > 1 else "",
                    phone=profile.phone,
                    email=profile.email,
                    company=profile.company,
                    industry=profile.industry,
                    country=country,
                    city=profile.location,
                    linkedin_url=profile.profile_url,
                    instagram_url=None,
                    telegram_username=None,
                    facebook_url=None,
                    scraping_source="linkedin",
                    source_url=profile.profile_url,
                    lead_score=self.calculate_lead_score(
                        has_phone=bool(profile.phone),
                        has_email=bool(profile.email),
                        has_company=bool(profile.company),
                        is_ceo_level=self._is_ceo_level(profile.headline),
                    ),
                )

                if await self.save_entrepreneur(entrepreneur):
                    saved_count += 1

            await self.update_scraping_queue(queue_id, "completed", found_count=saved_count)
            logger.info("[LINKEDIN] Browser scraping completed: %d profiles", saved_count)
            return saved_count

        except Exception as e:
            logger.error("[LINKEDIN] Browser scraping failed: %s", e)
            await self.update_scraping_queue(queue_id, "failed", error_message=str(e))
            raise
        finally:
            await self._close_browser()

    async def _extract_profile_from_element(self, element) -> Optional[LinkedInProfile]:
        """Extract profile data from LinkedIn search result element."""
        try:
            name = await element.query_selector(".name")
            name_text = await name.inner_text() if name else ""

            headline = await element.query_selector(".headline")
            headline_text = await headline.inner_text() if headline else ""

            location = await element.query_selector(".location")
            location_text = await location.inner_text() if location else ""

            link = await element.query_selector("a")
            profile_url = await link.get_attribute("href") if link else ""

            return LinkedInProfile(
                id="",
                name=name_text,
                headline=headline_text,
                location=location_text,
                company=None,
                industry=None,
                profile_url=profile_url,
                phone=None,
                email=None,
            )

        except Exception as e:
            logger.error("[LINKEDIN] Profile extraction failed: %s", e)
            return None

    def _is_ceo_level(self, headline: str) -> bool:
        """Check if headline indicates CEO/founder level."""
        if not headline:
            return False

        ceo_keywords = [
            "ceo",
            "founder",
            "co-founder",
            "owner",
            "president",
            "director",
        ]

        headline_lower = headline.lower()
        return any(keyword in headline_lower for keyword in ceo_keywords)

    async def _close_browser(self) -> None:
        """Close browser."""
        if self._page:
            await self._page.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("[LINKEDIN] Browser closed")
