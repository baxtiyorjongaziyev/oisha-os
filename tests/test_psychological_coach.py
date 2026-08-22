import pytest
from src.services.core.psychological_coach import (
    PsychologicalCoach,
    PsychologicalRole,
    FearCategory,
)
from src.agents.persona_router import PersonaRouter
from src.services.core.admin_command_router import (
    build_psychological_coach_response,
    build_sparring_response,
)


def test_psychological_coach_detects_call_reluctance():
    cat, role = PsychologicalCoach.detect_category("mijozga telefon qilmoqchi lekin qilolmayapti")
    assert cat == FearCategory.CALL_RELUCTANCE
    assert role == PsychologicalRole.SALES


def test_psychological_coach_detects_rejection_fear():
    cat, role = PsychologicalCoach.detect_category("hozir telefon qilsam rad etsa-chi yo'q desa nima qilaman")
    assert cat == FearCategory.REJECTION_FEAR
    assert role == PsychologicalRole.SALES


def test_psychological_coach_detects_price_anxiety():
    cat, role = PsychologicalCoach.detect_category("narx aytishga qo'rqyapman 3000$ desam qimmat desa nima qilaman")
    assert cat == FearCategory.PRICE_ANXIETY
    assert role == PsychologicalRole.SALES


def test_psychological_coach_detects_pm_delay_fear():
    cat, role = PsychologicalCoach.detect_category("dizaynerlar ulgurmayapti kechikishni mijozga qanday aytaman")
    assert cat == FearCategory.BAD_NEWS_DELAY
    assert role == PsychologicalRole.PM


def test_psychological_coach_detects_pm_scope_creep():
    cat, role = PsychologicalCoach.detect_category("mijoz yana yangi narsa qo'shdi lekin qo'shimcha pul so'rashga uyalyapman")
    assert cat == FearCategory.SCOPE_CREEP_BILLING
    assert role == PsychologicalRole.PM


def test_psychological_coach_detects_pm_angry_client():
    cat, role = PsychologicalCoach.detect_category("mijoz juda asabiy jahli chiqqan gaplashishga qo'rqyapman")
    assert cat == FearCategory.ANGRY_CLIENT_AVOIDANCE
    assert role == PsychologicalRole.PM


def test_deconstruct_fear_provides_complete_5_step_breakthrough():
    breakthrough = PsychologicalCoach.deconstruct_fear(
        "mijozga telefon qilmoqchi lekin qilolmayapti menejerga hozir telefon qilsang nima bo'ladi?",
        role="sales",
        client_name="Aziz aka",
        context={"deal_value": "$3,500"},
    )
    
    assert breakthrough.category == FearCategory.CALL_RELUCTANCE
    assert "Aziz aka" in breakthrough.worst_case_analysis
    assert "Hozir" in breakthrough.worst_case_analysis
    assert "inaction_cost" in breakthrough.__dict__
    assert len(breakthrough.micro_script) > 10
    assert len(breakthrough.action_challenge) > 10

    formatted = PsychologicalCoach.format_telegram_breakthrough(breakthrough)
    assert "OISHA PSIXOLOGIK KOUCHING" in formatted
    assert "ENG YOMON STSENARIY" in formatted
    assert "QILMASLIKNING HAQIQIY NARXI" in formatted


def test_roleplay_sparring_simulation():
    # 1. Start sparring
    prompt = PsychologicalCoach.roleplay_sparring(role="sales", scenario="Qimmat e'tirozi")
    assert "OISHA SPARRING PARTNER" in prompt
    assert "narxingiz juda qimmat" in prompt

    # 2. Feedback on reply
    feedback = PsychologicalCoach.roleplay_sparring(
        role="sales",
        scenario="Qimmat",
        user_reply="To'g'ri, narx arzon emas, chunki biz to'liq brending qilamiz",
    )
    assert "SPARRING TAHLILI VA FEEDBACK" in feedback
    assert "Kuchli tomoni" in feedback


def test_persona_router_integrates_psychological_coaches():
    res_sales = PersonaRouter.route("telefon qilishga qo'rqyapman rad etsa nima bo'ladi")
    assert "[AGENCY PERSONA: sales-psychology-coach]" in res_sales

    res_pm = PersonaRouter.route("kechikishni aytishga qo'rqyapman asabiy mijoz")
    assert "[AGENCY PERSONA: pm-mindset-coach]" in res_pm


def test_admin_command_router_psychological_builders():
    resp_coach = build_psychological_coach_response("telefon qilolmayapman", role="sales", client_name="Bobur")
    assert resp_coach.parse_mode == "markdown"
    assert "OISHA PSIXOLOGIK KOUCHING" in resp_coach.text
    assert "Bobur" in resp_coach.text

    resp_sparring = build_sparring_response("Qimmat", role="sales")
    assert resp_sparring.parse_mode == "markdown"
    assert "SPARRING" in resp_sparring.text
