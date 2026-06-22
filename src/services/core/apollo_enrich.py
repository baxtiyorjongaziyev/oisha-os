"""
Apollo.io Lead Enrichment
Telefon raqam yoki email → to'liq profil (ism, lavozim, kompaniya, LinkedIn, sanoat).

⚠️ settings.py YANGILANMAYDI (Coordinator owns) — env varlar getattr bilan o'qiladi.
Coordinator qo'shishi kerak: APOLLO_ENABLED, APOLLO_API_KEY.

Eslatma: O'zbekistonda email kam — Apollo asosan email/domain bo'yicha kuchli,
telefon-match cheklangan. [[uz-email-not-used]]
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

from src.settings import settings

logger = logging.getLogger("ApolloEnrich")

_APOLLO_BASE = "https://api.apollo.io/v1"


def _cfg(name: str, default):
    return getattr(settings, name, default)


class ApolloEnrich:
    def __init__(self):
        self.api_key = str(_cfg("APOLLO_API_KEY", ""))
        self.enabled = bool(_cfg("APOLLO_ENABLED", False)) and bool(self.api_key)
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=_APOLLO_BASE,
                headers={
                    "Content-Type": "application/json",
                    "Cache-Control": "no-cache",
                    "X-Api-Key": self.api_key,
                },
                timeout=15.0,
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def enrich(
        self, email: str = "", phone: str = "", name: str = "", domain: str = ""
    ) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None
        if not (email or phone or name):
            return None

        payload: Dict[str, Any] = {"reveal_personal_emails": False}
        if email:
            payload["email"] = email
        if name:
            payload["name"] = name
        if domain:
            payload["domain"] = domain
        if phone and not (email or name):
            payload["q_keywords"] = phone

        try:
            resp = await self.client.post("/people/match", json=payload)
            resp.raise_for_status()
            data = resp.json()
            person = data.get("person")
            if not person:
                return None
            return self._normalize(person)
        except Exception as e:
            logger.warning(f"[Apollo] enrich failed: {e}")
            return None

    def _normalize(self, p: Dict[str, Any]) -> Dict[str, Any]:
        org = p.get("organization") or {}
        return {
            "name": p.get("name"),
            "first_name": p.get("first_name"),
            "last_name": p.get("last_name"),
            "title": p.get("title"),
            "seniority": p.get("seniority"),
            "email": p.get("email"),
            "linkedin_url": p.get("linkedin_url"),
            "city": p.get("city"),
            "country": p.get("country"),
            "company": org.get("name"),
            "company_domain": org.get("primary_domain"),
            "company_website": org.get("website_url"),
            "industry": org.get("industry"),
            "company_size": org.get("estimated_num_employees"),
            "raw": p,
        }

    def to_amo_note(self, profile: Dict[str, Any]) -> str:
        if not profile:
            return ""
        parts = []
        if profile.get("title"):
            parts.append(f"Lavozim: {profile['title']}")
        if profile.get("company"):
            parts.append(f"Kompaniya: {profile['company']}")
        if profile.get("industry"):
            parts.append(f"Sanoat: {profile['industry']}")
        if profile.get("company_size"):
            parts.append(f"Hodimlar: {profile['company_size']}")
        if profile.get("linkedin_url"):
            parts.append(f"LinkedIn: {profile['linkedin_url']}")
        return " | ".join(parts)


_instance: Optional[ApolloEnrich] = None


def get_apollo() -> ApolloEnrich:
    global _instance
    if _instance is None:
        _instance = ApolloEnrich()
    return _instance
