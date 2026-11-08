"""
Tests for DealActivator service.
"""
import pytest
from src.services.ai.deal_activator import DealActivator, ReEngagementPlan


@pytest.mark.asyncio
async def test_fallback_plan():
    activator = DealActivator(gemini_client=None)
    plan = await activator.generate_activation_plan(
        transcript="Menejer: Narx 1000 dollar.\nMijoz: O'ylab ko'ramiz.",
        client_name="Jamshid",
        idle_hours=12.0,
        last_speaker="seller",
    )
    assert isinstance(plan, ReEngagementPlan)
    assert plan.client_name == "Jamshid"
    assert "Jamshid" in plan.ready_to_send_script
    assert len(plan.exact_action) > 10
    card = plan.format_card()
    assert "AYNAN NIMA DEYISH KERAK" in card
    assert "AYNAN NIMA QILISH KERAK" in card


def test_parse_plan_json():
    activator = DealActivator(gemini_client=None)
    raw_json = """
    {
        "stagnation_reason": "Mijoz narx qimmat deb o'ylamoqda",
        "exact_action": "Ovozli xabar bilan keys yuboring",
        "ready_to_send_script": "Jamshid aka, sizga o'xshash loyihamiz bor...",
        "prohibited_action": "Nima bo'ldi deb siqmang",
        "recommended_deadline_hours": 3
    }
    """
    plan = activator._parse_plan_json(raw_json, "Jamshid", "seller")
    assert plan.stagnation_reason == "Mijoz narx qimmat deb o'ylamoqda"
    assert "Jamshid aka" in plan.ready_to_send_script
    assert plan.recommended_deadline_hours == 3
