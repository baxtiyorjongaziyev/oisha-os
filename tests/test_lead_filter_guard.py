"""
Tests for LeadFilterGuard — Zero Hallucination and Team/Provider Role Guards.
"""
import pytest
from src.services.core.leads.lead_filter_guard import (
    EntityRole,
    resolve_entity_role,
    is_team_member,
    is_excluded_contact,
    validate_lead_qualification,
    sanitize_outreach_message,
)


def test_team_member_role_resolution():
    # Mumtozmaxal Jon Branding -> TEAM_MEMBER
    role, detail = resolve_entity_role(name="Mumtozmaxal Jon Branding")
    assert role == EntityRole.TEAM_MEMBER
    assert "jamoa_azosi" in detail

    # Username @MumtozmaxalJonbranding -> TEAM_MEMBER
    role, detail = resolve_entity_role(username="@MumtozmaxalJonbranding")
    assert role == EntityRole.TEAM_MEMBER
    assert "jamoa_azosi" in detail

    # Shahnoza -> TEAM_MEMBER
    role, detail = resolve_entity_role(name="Shahnoza Abdijabborova")
    assert role == EntityRole.TEAM_MEMBER

    # Baxtiyorjon Gaziyev -> TEAM_MEMBER
    role, detail = resolve_entity_role(name="Baxtiyorjon Gaziyev")
    assert role == EntityRole.TEAM_MEMBER

    # Helper is_team_member
    assert is_team_member(name="Mumtozmaxal Jon Branding") is True
    assert is_team_member(username="@MumtozmaxalJonbranding") is True
    assert is_team_member(name="Akmal Fayzulloyev") is False


def test_service_provider_role_resolution():
    # Dilnoza Uztelecom -> SERVICE_PROVIDER
    role, detail = resolve_entity_role(name="Dilnoza Uztelecom")
    assert role == EntityRole.SERVICE_PROVIDER
    assert "service_provider:uztelecom" in detail

    # Ifora Menejer -> SERVICE_PROVIDER
    role, detail = resolve_entity_role(name="Ifora Menejer")
    assert role == EntityRole.SERVICE_PROVIDER

    # amoBot -> SERVICE_PROVIDER
    role, detail = resolve_entity_role(name="amoBot")
    assert role == EntityRole.SERVICE_PROVIDER


def test_dummy_lead_exclusion():
    # Missed call / unreached
    exc, reason = is_excluded_contact(name="Звонок на +998911180633 (Не дозвонился)")
    assert exc is True
    assert "dummy_deal_marker" in reason

    exc, reason = is_excluded_contact(name="Звонок от +998999579942 (Пропущен)")
    assert exc is True
    assert "dummy_deal_marker" in reason

    exc, reason = is_excluded_contact(name="Test lead for amoCRM")
    assert exc is True
    assert "dummy_deal_marker" in reason


def test_real_clients_allowed():
    # Real prospects should NOT be excluded, their role is CLIENT
    role, _ = resolve_entity_role(name="Akmal Fayzulloyev", phone="+998901234567")
    assert role == EntityRole.CLIENT

    exc, reason = is_excluded_contact(name="Akmal Fayzulloyev", phone="+998901234567")
    assert exc is False
    assert reason == ""

    exc, reason = is_excluded_contact(name="Shohrux Mirzo", username="shohrux_biz")
    assert exc is False
    assert reason == ""


def test_zero_hallucination_qualification():
    # Without evidence, cannot default to 'Tadbirkorlik / Ishlab chiqarish' or 'LPR'
    qual = validate_lead_qualification(
        raw_industry="Tadbirkorlik / Ishlab chiqarish",
        raw_role="Qaror qabul qiluvchi (LPR)",
        raw_budget="O'rtacha (Business)",
        evidence="",
    )
    assert qual["industry"] == "Noma'lum"
    assert qual["role"] == "Tekshirilmagan"
    assert qual["budget"] == "Tekshirilmagan"

    # With grounded evidence
    qual2 = validate_lead_qualification(
        evidence="Biz mebel ishlab chiqarish bilan shug'ullanamiz, korxona direktori Akmalman.",
    )
    assert qual2["industry"] == "Ishlab chiqarish"
    assert qual2["role"] == "Rahbar / Asoschi"


def test_sanitize_outreach_message():
    bad_msg = (
        "Assalomu alaykum, Mumtozmaxal! Kecha aytgan loyihangiz boʻyicha "
        "jamoamiz bilan oʻxshash muvaffaqiyatli keysimizni koʻrib chiqdik."
    )
    cleaned = sanitize_outreach_message(bad_msg, contact_name="Akmal aka", has_recent_conversation=False)
    assert "kecha aytgan" not in cleaned.lower()
    assert "Akmal aka" in cleaned
    assert "Jon Branding" in cleaned

    # If recent conversation was verified, preserve text
    allowed = sanitize_outreach_message(bad_msg, contact_name="Akmal aka", has_recent_conversation=True)
    assert allowed == bad_msg
