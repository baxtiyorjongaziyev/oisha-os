"""
Tests for LeadFilterGuard — Zero Hallucination and Team/Provider Exclusion Guards.
"""
import pytest
from src.services.core.leads.lead_filter_guard import (
    is_excluded_contact,
    validate_lead_qualification,
    sanitize_outreach_message,
)


def test_internal_team_member_exclusion():
    # Mumtozmaxal Jon Branding
    exc, reason = is_excluded_contact(name="Mumtozmaxal Jon Branding")
    assert exc is True
    assert "internal_team_member" in reason

    # Username @MumtozmaxalJonbranding
    exc, reason = is_excluded_contact(username="@MumtozmaxalJonbranding")
    assert exc is True
    assert "internal_team_member" in reason

    # Shahnoza
    exc, reason = is_excluded_contact(name="Shahnoza Abdijabborova")
    assert exc is True
    assert "internal_team_member" in reason

    # Baxtiyorjon Gaziyev
    exc, reason = is_excluded_contact(name="Baxtiyorjon Gaziyev")
    assert exc is True
    assert "internal_team_member" in reason


def test_service_provider_exclusion():
    # Dilnoza Uztelecom
    exc, reason = is_excluded_contact(name="Dilnoza Uztelecom")
    assert exc is True
    assert "service_provider" in reason

    # Ifora Menejer
    exc, reason = is_excluded_contact(name="Ifora Menejer")
    assert exc is True
    assert "service_provider" in reason

    # amoBot
    exc, reason = is_excluded_contact(name="amoBot")
    assert exc is True
    assert "service_provider" in reason


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
    # Real prospects should NOT be excluded
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
        raw_budget="Oʻrtacha (Business)",
        evidence="",
    )
    assert qual["industry"] == "Nomaʼlum"
    assert qual["role"] == "Tekshirilmagan"
    assert qual["budget"] == "Tekshirilmagan"

    # With grounded evidence
    qual2 = validate_lead_qualification(
        evidence="Biz mebel ishlab chiqarish bilan shugʻullanamiz, korxona direktori Akmalman.",
    )
    assert qual2["industry"] == "Ishlab chiqarish"
    assert qual2["role"] == "Rahbar / Asoschi"


def test_sanitize_outreach_message():
    bad_msg = (
        "Assalomu alaykum, Mumtozmaxal! Kecha aytgan loyihangiz bo'yicha "
        "jamoamiz bilan o'xshash muvaffaqiyatli keysimizni ko'rib chiqdik."
    )
    cleaned = sanitize_outreach_message(bad_msg, contact_name="Akmal aka", has_recent_conversation=False)
    assert "kecha aytgan" not in cleaned.lower()
    assert "Akmal aka" in cleaned
    assert "Jon Branding" in cleaned

    # If recent conversation was verified, preserve text
    allowed = sanitize_outreach_message(bad_msg, contact_name="Akmal aka", has_recent_conversation=True)
    assert allowed == bad_msg
