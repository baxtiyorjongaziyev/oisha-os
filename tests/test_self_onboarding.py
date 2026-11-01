"""Oisha Self-Onboarding moduli uchun birlik testlar."""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from src.services.core.onboarding.models import (
    CompanyServicePackage,
    SelfOnboardingProfile,
    TeamMember,
    WorkflowPlaybook,
)
from src.services.core.onboarding.service import (
    SelfOnboardingService,
    get_self_onboarding,
)
from src.services.core.jamoa_ritm.brain import HamrohBrain


def test_self_onboarding_run_and_validation(tmp_path: Path):
    """Onboarding profili toʻgʻri shakllanadi va tekshiruvdan oʻtadi."""
    cache_file = tmp_path / "test_profile.json"
    service = SelfOnboardingService(cache_path=cache_file)

    profile = service.run_self_onboarding(force=True)

    assert profile.is_validated is True
    assert profile.company_name == "Jon Branding"
    assert "baxtiyorjon" in profile.team
    assert "dilbar" in profile.team
    assert "rayxon" in profile.team
    assert "mumtozmaxal" in profile.team
    assert "shahnoza" in profile.team
    assert "ahrorbek" in profile.team

    assert "moliya" in profile.workflows
    assert "sales_discipline" in profile.workflows
    assert "jamoa_ritmi" in profile.workflows
    assert len(profile.services) >= 9

    # Fayl keshga yozilganini tekshirish
    assert cache_file.exists()
    saved_data = json.loads(cache_file.read_text(encoding="utf-8"))
    assert saved_data["company_name"] == "Jon Branding"
    assert saved_data["is_validated"] is True


def test_member_lookup(tmp_path: Path):
    """Jamoa aʼzolarini turli identifikatorlar orqali topish."""
    service = SelfOnboardingService(cache_path=tmp_path / "cache.json")
    service.run_self_onboarding(force=True)

    # Telegram handle orqali
    dilbar = service.lookup_member("@jonbranding_finansist")
    assert dilbar is not None
    assert dilbar.id == "dilbar"
    assert dilbar.authority == "pm_finance"

    # ID orqali
    owner = service.lookup_member("baxtiyorjon")
    assert owner is not None
    assert owner.authority == "owner"

    # Ism orqali
    rayxon = service.lookup_member("Rayxon")
    assert rayxon is not None
    assert rayxon.id == "rayxon"

    # Email orqali
    shahnoza = service.lookup_member("xayrullayevna006@gmail.com")
    assert shahnoza is not None
    assert shahnoza.id == "shahnoza"

    # Nomaʼlum
    unknown = service.lookup_member("random_stranger")
    assert unknown is None


def test_workflow_resolution_and_clarify_guard(tmp_path: Path):
    """Moliya yoʻriqnomasi va ortiqcha soʻroqni toʻxtatish tekshiruvi."""
    service = SelfOnboardingService(cache_path=tmp_path / "cache.json")
    service.run_self_onboarding(force=True)

    # Moliya yoʻriqnomasi
    wf = service.resolve_workflow("Bugungi kunlik balans va kassa qanday?")
    assert wf is not None
    assert wf.id == "moliya"
    assert "Airtable" in wf.source_of_truth
    assert any("Kunlik balansni qayerdan olasiz" in r for r in wf.prohibited_actions)

    # Ortiqcha soʻroqni toʻxtatish
    assert service.should_suppress_clarify_question("Kunlik balansni kiritdim") is True
    assert service.should_suppress_clarify_question("Kassa hisoboti") is True
    assert service.should_suppress_clarify_question("Ertalabki start vazifam") is True
    assert service.should_suppress_clarify_question("Brending narxi qancha?") is False


def test_system_context_content(tmp_path: Path):
    """Tizim prompti uchun kontekst matnida asosiy faktlar mavjudligi."""
    service = SelfOnboardingService(cache_path=tmp_path / "cache.json")
    service.run_self_onboarding(force=True)

    ctx = service.get_system_context()
    assert "[OISHA OʻZ-OʻZINI ONBOARDING BILIMLARI]" in ctx
    assert "Jon Branding" in ctx
    assert "Baxtiyorjon Gaziyev" in ctx
    assert "Dilbar Akbarovna" in ctx
    assert "Kunlik balansni qayerdan olasiz" in ctx


@pytest.mark.asyncio
async def test_hamroh_brain_asker_enrichment():
    """HamrohBrain javob tayyorlashda murojaat qiluvchi rolini promptga kiritadi."""
    captured_prompt = []

    async def fake_generate(prompt: str, *, system: str, max_tokens: int, temperature: float) -> str:
        captured_prompt.append(prompt)
        return "Albatta, Dilbar opa, yordam beraman."

    brain = HamrohBrain(generate=fake_generate)
    answer = await brain.answer(
        question="Bugungi loyihalar holati qanday?",
        context=[],
        asker="@jonbranding_finansist",
    )

    assert "Albatta, Dilbar opa" in answer
    assert len(captured_prompt) == 1
    assert "Dilbar Akbarovna" in captured_prompt[0]
    assert "PM & Finance" in captured_prompt[0]


def test_singleton_accessor():
    """get_self_onboarding yagona nusxa qaytaradi."""
    s1 = get_self_onboarding()
    s2 = get_self_onboarding()
    assert s1 is s2
