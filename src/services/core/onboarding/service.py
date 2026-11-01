"""Oisha oʻz-oʻzini tanitish (Self-Onboarding) xizmati.

Ushbu servis Jon Branding kompaniyasining ichki tuzilishi, jamoa rollari va
operatsion yoʻriqnomalarini tizimga singdiradi hamda agentlarning xatolikka
yoʻl qoʻymasligini taʼminlaydi.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from src.services.core.onboarding.knowledge_source import (
    get_core_team,
    get_core_workflows,
    get_official_services,
)
from src.services.core.onboarding.models import (
    CompanyServicePackage,
    SelfOnboardingProfile,
    TeamMember,
    WorkflowPlaybook,
)

logger = logging.getLogger(__name__)

DEFAULT_CACHE_PATH = Path("data/self_onboarding_profile.json")


class SelfOnboardingService:
    """Oishaning avtonom onboarding boshqaruvchisi."""

    def __init__(self, cache_path: Optional[Path] = None):
        self._cache_path = cache_path or DEFAULT_CACHE_PATH
        self._profile: Optional[SelfOnboardingProfile] = None

    def _validate_profile(self, profile: SelfOnboardingProfile) -> bool:
        """Profilning toʻliqligi va haqiqiyligini tekshiradi."""
        if not profile.company_name or len(profile.team) < 4:
            return False
        if "baxtiyorjon" not in profile.team or "dilbar" not in profile.team:
            return False
        if "moliya" not in profile.workflows:
            return False
        return True

    def _save_to_cache(self, profile: SelfOnboardingProfile) -> None:
        """Profilni kesh fayliga saqlaydi."""
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._cache_path.write_text(
                json.dumps(profile.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.info("[ONBOARDING] Profil keshga saqlandi: %s", self._cache_path)
        except Exception as exc:
            logger.warning("[ONBOARDING] Keshga yozishda xato: %s", exc)

    def _load_from_cache(self) -> Optional[SelfOnboardingProfile]:
        """Keshdan mavjud profilni tiklaydi."""
        if not self._cache_path.exists():
            return None
        try:
            raw = json.loads(self._cache_path.read_text(encoding="utf-8"))
            team = {k: TeamMember(**v) for k, v in raw.get("team", {}).items()}
            workflows = {
                k: WorkflowPlaybook(**v) for k, v in raw.get("workflows", {}).items()
            }
            services = [
                CompanyServicePackage(**s) for s in raw.get("services", [])
            ]
            profile = SelfOnboardingProfile(
                company_name=raw.get("company_name", "Jon Branding"),
                tagline=raw.get("tagline", ""),
                version=raw.get("version", "2026.1"),
                onboarded_at=raw.get("onboarded_at", ""),
                team=team,
                workflows=workflows,
                services=services,
                is_validated=raw.get("is_validated", False),
            )
            if self._validate_profile(profile):
                return profile
        except Exception as exc:
            logger.warning("[ONBOARDING] Keshdan oʻqishda xato: %s", exc)
        return None

    def run_self_onboarding(self, force: bool = False) -> SelfOnboardingProfile:
        """Oʻz-oʻzini tanitish (onboarding) jarayonini ishga tushiradi."""
        if not force:
            cached = self._load_from_cache()
            if cached is not None:
                self._profile = cached
                return cached

        team = get_core_team()
        workflows = get_core_workflows()
        services = get_official_services()

        profile = SelfOnboardingProfile(
            company_name="Jon Branding",
            tagline="Maʼno va strategiyaga asoslangan premium brendlar",
            version="2026.1",
            onboarded_at=datetime.now(timezone.utc).isoformat(),
            team=team,
            workflows=workflows,
            services=services,
            is_validated=False,
        )

        profile.is_validated = self._validate_profile(profile)
        self._save_to_cache(profile)
        self._profile = profile
        logger.info(
            "[ONBOARDING] Oisha oʻz-oʻzini onboarding qildi. Aʼzolar soni: %d, Yoʻriqnomalar: %d",
            len(profile.team),
            len(profile.workflows),
        )
        return profile

    def get_profile(self) -> SelfOnboardingProfile:
        """Joriy faol profilni qaytaradi."""
        if self._profile is None:
            return self.run_self_onboarding()
        return self._profile

    def lookup_member(self, query: str) -> Optional[TeamMember]:
        """Telegram username yoki ism orqali jamoa aʼzosini topadi."""
        if not query:
            return None
        cleaned = query.strip().lower().lstrip("@")
        profile = self.get_profile()

        for member_id, member in profile.team.items():
            if cleaned == member_id:
                return member
            if member.telegram and cleaned == member.telegram.lower().lstrip("@"):
                return member
            if cleaned in member.name.lower():
                return member
            if member.email and cleaned == member.email.lower():
                return member
        return None

    def resolve_workflow(self, query: str) -> Optional[WorkflowPlaybook]:
        """Mavzu boʻyicha mos operatsion yoʻriqnomani topadi."""
        if not query:
            return None
        q = query.lower()
        profile = self.get_profile()

        if any(w in q for w in ["balans", "kassa", "moliya", "tushum", "xarajat"]):
            return profile.workflows.get("moliya")
        if any(w in q for w in ["sotuv", "amocrm", "lid", "lead", "qoʻngʻiroq"]):
            return profile.workflows.get("sales_discipline")
        if any(w in q for w in ["ritm", "ertalab", "start", "yakun", "retro", "tinchlik"]):
            return profile.workflows.get("jamoa_ritmi")
        return None

    def should_suppress_clarify_question(self, query: str) -> bool:
        """Maʼlum standart operatsiyalar boʻyicha ortiqcha soʻroqni toʻxtatadi."""
        q = query.lower()
        if any(w in q for w in ["balans", "kunlik balans", "kassa"]):
            return True
        if any(w in q for w in ["davomat", "start", "yakun"]):
            return True
        return False

    def get_system_context(self) -> str:
        """LLM tizim promptlari uchun ixcham va mazmunli kontekst matnini yaratadi."""
        profile = self.get_profile()
        members_lines = []
        for m in profile.team.values():
            tg = f" ({m.telegram})" if m.telegram else ""
            members_lines.append(f"- {m.name}{tg}: {m.role}")

        workflows_lines = []
        for w in profile.workflows.values():
            rules_str = " ".join(w.key_rules[:2])
            workflows_lines.append(f"• {w.title} ({w.responsible_role}): {rules_str}")

        return (
            "[OISHA OʻZ-OʻZINI ONBOARDING BILIMLARI]\n"
            f"Kompaniya: {profile.company_name} — {profile.tagline}\n"
            "Jamoa tarkibi va masʼuliyatlar:\n"
            f"{chr(10).join(members_lines)}\n\n"
            "Operatsion yoʻriqnomalar va qatʼiy qoidalar:\n"
            f"{chr(10).join(workflows_lines)}\n\n"
            "Asosiy taqiqlar:\n"
            "- Dilbar opadan yoki jamoadan 'Kunlik balansni qayerdan olasiz?' deb soʻroq qilish qatʼiyan man etiladi.\n"
            "- Guruhda 'siz' bilan, doʻstona, qisqa (2–4 qator) muloqot qil. Bahslashma va oʻzingni oqlama.\n"
            "- Tizim xatoliklarini ([The tool failed...], [NO TOOL CALL...]) guruhga chiqarish taqiqlanadi."
        )


_instance: Optional[SelfOnboardingService] = None


def get_self_onboarding() -> SelfOnboardingService:
    """SelfOnboardingService ning yagona nusxasini (singleton) qaytaradi."""
    global _instance
    if _instance is None:
        _instance = SelfOnboardingService()
    return _instance
