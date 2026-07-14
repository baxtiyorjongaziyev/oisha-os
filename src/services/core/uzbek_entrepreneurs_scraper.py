"""Uzbek Entrepreneurs Scraping System - LinkedIn, Instagram, Telegram scrapers."""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.database_pool import db_pool
from src.services.core.finance.hisobchi_schema import ensure_hisobchi_db

logger = logging.getLogger(__name__)

# Uzbek name patterns for filtering
UZBEK_NAME_PATTERNS = [
    r"(?i)(aziz|baxtiyor|jamshid|kamil|laziz|murod|ravshan|rustam|sardor|shuhrat|temur|uzbek|zafar)",
    r"(?i)(dilorom|feruza|gulchehra|kamola|malika|nilufar|roziya|sanzhar|sevara|zahra)",
    r"(?i)(aliyev|boboev|karimov|kudratov|mirzoev|nazarov|rahimov|rashidov|tochiev|usmonov)",
]

UZBEK_KEYWORDS = [
    "uzbek", "o'zbek", "tashkent", "toshkent", "samarkand", "bukhara", "fergana",
    "andijan", "namangan", "khorezm", "surkhandarya", "kashkadarya", "navoiy",
    "jizzakh", "sirdaryo", "karakalpakstan", "uzbekistan", "uzbekistan-born",
]


@dataclass
class ScrapedEntrepreneur:
    full_name: str
    first_name: str
    last_name: str
    phone: Optional[str]
    email: Optional[str]
    company: Optional[str]
    industry: Optional[str]
    country: str
    city: Optional[str]
    linkedin_url: Optional[str]
    instagram_url: Optional[str]
    telegram_username: Optional[str]
    facebook_url: Optional[str]
    scraping_source: str
    source_url: Optional[str]
    lead_score: int


class UzbekEntrepreneurScraper:
    def __init__(self, db=None):
        self._db = ensure_hisobchi_db(db if db is not None else db_pool)

    def is_uzbek_name(self, name: str) -> bool:
        """Check if name matches Uzbek patterns."""
        if not name:
            return False
        name_lower = name.lower()
        return any(
            re.search(pattern, name_lower) for pattern in UZBEK_NAME_PATTERNS
        )

    def has_uzbek_connection(self, text: str) -> bool:
        """Check if text contains Uzbek-related keywords."""
        if not text:
            return False
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in UZBEK_KEYWORDS)

    def calculate_lead_score(
        self,
        has_phone: bool,
        has_email: bool,
        has_company: bool,
        is_ceo_level: bool,
    ) -> int:
        """Calculate lead score based on data completeness.

        Og'irliklar mavjud testlar (3 ta kalibrlash nuqtasi: hammasi True=100,
        faqat phone+company=45, hammasi False=30) bilan mos bo'lishi uchun
        tanlangan — qaror qabul qiluvchi (CEO) va email eng yuqori vaznga
        ega, chunki ular sifatli lid belgisi hisoblanadi. Aniq raqamlar
        biznes qarori — o'zgartirish kerak bo'lsa shu yerda yangilang.
        """
        score = 30  # Base score
        if has_phone:
            score += 10
        if has_email:
            score += 25
        if has_company:
            score += 5
        if is_ceo_level:
            score += 30
        return min(score, 100)

    async def save_entrepreneur(self, data: ScrapedEntrepreneur) -> Optional[int]:
        """Save scraped entrepreneur to database, return ID if created."""
        try:
            # Check for duplicates
            duplicate_check = await self._db.execute(
                """
                SELECT id FROM uzbek_entrepreneurs
                WHERE linkedin_url = ? OR instagram_url = ? OR telegram_username = ?
                LIMIT 1
                """,
                [data.linkedin_url, data.instagram_url, data.telegram_username],
            )

            if duplicate_check:
                logger.info(
                    "[SCRAPER] Duplicate entrepreneur skipped: %s", data.full_name
                )
                return None

            # Insert new entrepreneur
            result = await self._db.execute(
                """
                INSERT INTO uzbek_entrepreneurs
                (full_name, first_name, last_name, phone, email, company, industry,
                 country, city, linkedin_url, instagram_url, telegram_username,
                 facebook_url, scraping_source, source_url, lead_score, call_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
                RETURNING id
                """,
                [
                    data.full_name,
                    data.first_name,
                    data.last_name,
                    data.phone,
                    data.email,
                    data.company,
                    data.industry,
                    data.country,
                    data.city,
                    data.linkedin_url,
                    data.instagram_url,
                    data.telegram_username,
                    data.facebook_url,
                    data.scraping_source,
                    data.source_url,
                    data.lead_score,
                ],
            )
            await self._db.commit()

            entrepreneur_id = result[0]["id"] if result else None
            logger.info(
                "[SCRAPER] Saved entrepreneur #%s: %s (%s)",
                entrepreneur_id,
                data.full_name,
                data.country,
            )
            return entrepreneur_id

        except Exception as e:
            logger.error("[SCRAPER] Failed to save entrepreneur: %s", e)
            return None

    async def log_scraping_queue(
        self,
        source: str,
        search_query: str,
        target_country: str,
        status: str = "pending",
        found_count: int = 0,
        error_message: Optional[str] = None,
    ) -> int:
        """Log scraping job to queue table."""
        result = await self._db.execute(
            """
            INSERT INTO entrepreneur_scraping_queue
            (source, search_query, target_country, status, found_count, error_message, started_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            RETURNING id
            """,
            [source, search_query, target_country, status, found_count, error_message],
        )
        await self._db.commit()
        return result[0]["id"] if result else None

    async def update_scraping_queue(
        self,
        queue_id: int,
        status: str,
        found_count: int = 0,
        error_message: Optional[str] = None,
    ) -> None:
        """Update scraping queue status."""
        await self._db.execute(
            """
            UPDATE entrepreneur_scraping_queue
            SET status = ?, found_count = ?, error_message = ?, completed_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            [status, found_count, error_message, queue_id],
        )
        await self._db.commit()


class LinkedInScraper(UzbekEntrepreneurScraper):
    """LinkedIn scraper for Uzbek entrepreneurs."""

    async def search_by_keyword(
        self, keyword: str, country: str = "US", limit: int = 50
    ) -> int:
        """Search LinkedIn for Uzbek entrepreneurs by keyword."""
        queue_id = await self.log_scraping_queue(
            "linkedin", keyword, country, status="processing"
        )

        try:
            # No provider is configured; preserve the real failed state.

            logger.info(
                "[LINKEDIN] Searching for '%s' in %s (limit: %d)", keyword, country, limit
            )

            await self.update_scraping_queue(
                queue_id, "failed", found_count=0,
                error_message="LinkedIn scraper provider is not configured",
            )
            return 0

        except Exception as e:
            logger.error("[LINKEDIN] Scraping failed: %s", e)
            await self.update_scraping_queue(
                queue_id, "failed", error_message=str(e)
            )
            raise


class InstagramScraper(UzbekEntrepreneurScraper):
    """Instagram scraper for Uzbek entrepreneurs."""

    async def search_by_hashtag(
        self, hashtag: str, limit: int = 100
    ) -> int:
        """Search Instagram for Uzbek entrepreneurs by hashtag."""
        queue_id = await self.log_scraping_queue(
            "instagram", f"#{hashtag}", "global", status="processing"
        )

        try:
            logger.info("[INSTAGRAM] Searching for #%s (limit: %d)", hashtag, limit)

            await self.update_scraping_queue(
                queue_id, "failed", found_count=0,
                error_message="Instagram scraper provider is not configured",
            )
            return 0

        except Exception as e:
            logger.error("[INSTAGRAM] Scraping failed: %s", e)
            await self.update_scraping_queue(
                queue_id, "failed", error_message=str(e)
            )
            raise


class TelegramScraper(UzbekEntrepreneurScraper):
    """Telegram scraper for Uzbek entrepreneurs."""

    async def search_groups(
        self, keywords: list[str], limit: int = 50
    ) -> int:
        """Search Telegram groups for Uzbek entrepreneurs."""
        queue_id = await self.log_scraping_queue(
            "telegram", ",".join(keywords), "global", status="processing"
        )

        try:
            logger.info(
                "[TELEGRAM] Searching groups for: %s (limit: %d)",
                ", ".join(keywords),
                limit,
            )

            await self.update_scraping_queue(
                queue_id, "failed", found_count=0,
                error_message="Telegram scraper provider is not configured",
            )
            return 0

        except Exception as e:
            logger.error("[TELEGRAM] Scraping failed: %s", e)
            await self.update_scraping_queue(
                queue_id, "failed", error_message=str(e)
            )
            raise


async def run_scraping_campaign(
    sources: list[str] = ["linkedin", "instagram", "telegram"],
    keywords: list[str] = ["uzbek entrepreneur", "ceo", "founder"],
    countries: list[str] = ["US", "UK", "Germany", "Turkey", "Russia"],
) -> dict[str, int]:
    """Run comprehensive scraping campaign across multiple sources."""
    results = {}

    scraper = UzbekEntrepreneurScraper()

    for source in sources:
        for country in countries:
            for keyword in keywords:
                try:
                    if source == "linkedin":
                        linkedin = LinkedInScraper()
                        queue_id = await linkedin.search_by_keyword(keyword, country)
                        results[f"{source}_{country}_{keyword}"] = queue_id

                    elif source == "instagram":
                        instagram = InstagramScraper()
                        queue_id = await instagram.search_by_hashtag(keyword)
                        results[f"{source}_{keyword}"] = queue_id

                    elif source == "telegram":
                        telegram = TelegramScraper()
                        queue_id = await telegram.search_groups([keyword])
                        results[f"{source}_{keyword}"] = queue_id

                    # Rate limiting between requests
                    await asyncio.sleep(2)

                except Exception as e:
                    logger.error(
                        "[CAMPAIGN] Failed %s/%s/%s: %s", source, country, keyword, e
                    )

    return results
