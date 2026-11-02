"""Unit tests for AI Voice Exam and Simulation Engine."""
from src.services.ai.voice_exam import (
    VoiceExamEngine,
    VoiceExamSession,
)


def test_get_scenarios_and_start_exam():
    engine = VoiceExamEngine()
    scenarios = engine.get_scenarios()
    assert len(scenarios) >= 2
    sc = scenarios[0]

    session = engine.start_exam(manager_id="mgr_kamola", scenario_id=sc.scenario_id)
    assert session.manager_id == "mgr_kamola"
    assert session.status == "active"
    assert len(session.turns) == 1
    assert session.turns[0].speaker == "client"


def test_process_turns_and_finalize_passing():
    engine = VoiceExamEngine()
    session = engine.start_exam(manager_id="mgr_kamola", scenario_id="pre_sale_1")

    # Manager speaks greeting and discovery
    t1 = engine.process_turn(session, "Assalomu alaykum Bobur aka! Sizda savdo jarayonlari qanday ketyapti va asosiy maqsad nima?")
    assert "muammo" in t1["client_response"]

    # Manager presents solution and handles objection
    t2 = engine.process_turn(session, "Bizning yechim savdoni oshirishga yordam beradi. Narx boʻyicha bu investitsiya 1 oyda oʻzini oqlaydi.")
    assert "narx" in t2["client_response"].lower() or "kafolat" in t2["client_response"].lower()

    # Manager closes next step
    t3 = engine.process_turn(session, "Ertaga soat 15:00 da Zoom orqali uchrashuv belgilab, shartnomani kelishsak boʻladimi?")
    assert "Zoom" in t3["client_response"] or "15:00" in t3["client_response"]

    final_session = engine.finalize_exam(session)
    assert final_session.status == "completed"
    assert final_session.overall_score >= 70
    assert final_session.passed is True
    assert final_session.certificate_id is not None
    assert "CERT-GS" in final_session.certificate_id
