"""
Oisha-OS: Telegram xabarlarida kelgan havolalarni (linklarni) tahlil qilish moduli.

Mijoz yuborgan havolalarni (vebsayt, Instagram, Behance, Google Drive, Telegram kanal)
avtomatik aniqlab, soha, referens uslubi va kompaniya maʼlumotlarini ajratib oladi.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from urllib.parse import urlparse

import httpx

logger = logging.getLogger("LinkAnalyzer")

_URL_PATTERN = re.compile(
    r"(?:https?://|www\.|(?:\b[\w-]+\.(?:uz|com|ru|org|net|io|me)\b))[^\s<>\"']*",
    re.IGNORECASE,
)


@dataclass
class AnalyzedLink:
    """Tahlil qilingan havola maʼlumotlari."""
    url: str
    category: str  # "website", "instagram", "telegram", "design_ref", "drive", "other"
    domain: str
    title: str = ""
    description: str = ""
    sales_insight: str = ""


class LinkAnalyzer:
    """Xabarlardagi havolalarni ajratuvchi va boyituvchi xizmat."""

    def __init__(self, timeout_seconds: float = 3.0) -> None:
        self.timeout = timeout_seconds

    def extract_urls(self, text: str) -> List[str]:
        """Matndan barcha havolalarni ajratib olish."""
        if not text:
            return []
        matches = _URL_PATTERN.findall(text)
        cleaned = []
        for u in matches:
            u_clean = u.rstrip(".,;!?:)")
            if not u_clean.startswith(("http://", "https://")):
                u_clean = f"https://{u_clean}"
            cleaned.append(u_clean)
        return list(dict.fromkeys(cleaned))

    @staticmethod
    def _host_matches(domain: str, host: str) -> bool:
        return domain == host or domain.endswith(f".{host}")

    def categorize_url(self, url: str) -> str:
        """Havola turini aniqlash."""
        domain = (urlparse(url).hostname or "").lower()
        if self._host_matches(domain, "instagram.com"):
            return "instagram"
        if self._host_matches(domain, "t.me") or self._host_matches(domain, "telegram.me"):
            return "telegram"
        if any(self._host_matches(domain, d) for d in ("behance.net", "pinterest.com", "dribbble.com")):
            return "design_ref"
        if any(self._host_matches(domain, d) for d in ("drive.google.com", "dropbox.com", "disk.yandex.ru", "disk.yandex.com")):
            return "drive"
        return "website"

    async def fetch_meta_preview(self, url: str) -> tuple[str, str]:
        """Vebsahifaning sarlavhasi (title) va taʼrifini (description) oʻqish."""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code != 200:
                    return "", ""
                html = resp.text[:15000]

                # Title izlash
                title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
                title = title_match.group(1).strip() if title_match else ""

                # Description izlash
                desc_match = re.search(
                    r'<meta\s+[^>]*?(?:name|property)=["\'](?:description|og:description)["\'][^>]*?content=["\'](.*?)["\']',
                    html,
                    re.IGNORECASE | re.DOTALL,
                )
                description = desc_match.group(1).strip() if desc_match else ""
                return title[:120], description[:250]
        except Exception as exc:
            logger.debug("[LINK] %s havolasini oʻqishda cheklov: %s", url, exc)
            return "", ""

    async def analyze_url(self, url: str) -> AnalyzedLink:
        """Bitta havolani toʻliq tahlil qilish."""
        domain = urlparse(url).netloc.lower()
        category = self.categorize_url(url)
        title, description = "", ""

        # Ommaviy vebsaytlar uchun sarlavhani olish
        if category in ("website", "design_ref"):
            title, description = await self.fetch_meta_preview(url)

        insight = self._generate_sales_insight(category, domain, title)

        return AnalyzedLink(
            url=url,
            category=category,
            domain=domain,
            title=title,
            description=description,
            sales_insight=insight,
        )

    def _generate_sales_insight(self, category: str, domain: str, title: str) -> str:
        """Sotuvchi uchun havoladan kelib chiqadigan maslahat."""
        if category == "instagram":
            return "Mijoz oʻz ijtimoiy sahifasi yoki yoqtirgan uslubini koʻrsatmoqda. Vizual lentadagi kamchiliklarni koʻrib chiqing."
        if category == "design_ref":
            return "Mijoz dizayn yoʻnalishi (referens) boʻyicha aniq didga ega. Behance/Pinterest uslubiga mos portfolio taqdim eting."
        if category == "drive":
            return "Mijoz tayyor brif yoki logotip materiallarini tashlagan. Texnik talablar va hajmni baholash osonlashadi."
        if category == "telegram":
            return "Mijozning Telegram kanali yoki faoliyati. Auditoriyasi va qamrovini baholash mumkin."
        if title:
            return f"Mijozning joriy biznes sayti ({title}). Hozirgi brending holatini baholash uchun ayni muddao."
        return f"Mijoz {domain} saytini yuborgan. Faoliyat sohasi bilan tanishib chiqing."

    async def analyze_text_links(self, text: str) -> List[AnalyzedLink]:
        """Matndagi barcha havolalarni tahlil qilish."""
        urls = self.extract_urls(text)
        results = []
        for u in urls[:5]:  # Koʻpi bilan 5 ta havola
            link_info = await self.analyze_url(u)
            results.append(link_info)
        return results

    def format_links_summary(self, links: List[AnalyzedLink]) -> str:
        """Transkript va AI konteksti uchun xulosa matni."""
        if not links:
            return ""
        lines = ["🔗 MIJOZ YUBORGAN HAVOLALAR TAHLILI:"]
        for l in links:
            title_part = f" — \"{l.title}\"" if l.title else ""
            lines.append(f"• [{l.category.upper()}] {l.url}{title_part}")
            lines.append(f"  💡 Maslahat: {l.sales_insight}")
        return "\n".join(lines)
