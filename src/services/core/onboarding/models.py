"""Oisha self-onboarding modellarining maʼlumotlar tuzilmasi.

Barcha modellar Pydantic yoki dataclass asosida boʻlib, Jon Branding kompaniyasi
haqidagi bilimlarni qatʼiy va xavfsiz ifodalaydi.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TeamMember:
    """Jamoa aʼzosining profili va masʼuliyat doirasi."""

    id: str
    name: str
    role: str
    telegram: Optional[str] = None
    email: Optional[str] = None
    authority: str = "member"  # owner, pm_finance, sales, creative_tech
    responsibilities: List[str] = field(default_factory=list)
    tone_guidance: str = "hurmatli va doʻstona"


@dataclass
class WorkflowPlaybook:
    """Kompaniyaning operatsion yoʻriqnomasi va qatʼiy qoidalari."""

    id: str
    title: str
    responsible_role: str
    source_of_truth: str
    key_rules: List[str] = field(default_factory=list)
    prohibited_actions: List[str] = field(default_factory=list)


@dataclass
class CompanyServicePackage:
    """Jon Branding xizmat paketi va rasmiy narxi."""

    name: str
    price_usd: int
    deliverables: List[str] = field(default_factory=list)


@dataclass
class SelfOnboardingProfile:
    """Oishaning toʻliq oʻz-oʻzini tanitish (onboarding) profili."""

    company_name: str = "Jon Branding"
    tagline: str = "Maʼno va strategiyaga asoslangan premium brendlar"
    version: str = "2026.1"
    onboarded_at: str = ""
    team: Dict[str, TeamMember] = field(default_factory=dict)
    workflows: Dict[str, WorkflowPlaybook] = field(default_factory=dict)
    services: List[CompanyServicePackage] = field(default_factory=list)
    is_validated: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Profilni lugʻat koʻrinishida qaytaradi."""
        return asdict(self)
