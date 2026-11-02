"""Tests for AI Sales Practice Simulator Engine."""

from src.services.ai.sales_simulator import (
    SimulationScenario,
    SimulationTurn,
    SalesSimulatorEngine,
)


def test_built_in_scenarios_exist():
    engine = SalesSimulatorEngine()
    scenarios = engine.get_scenarios()
    assert len(scenarios) >= 5
    ids = [s.scenario_id for s in scenarios]
    assert "first_30_seconds" in ids
    assert "too_expensive" in ids
    assert "think_about_it" in ids


def test_hidden_facts_revelation():
    engine = SalesSimulatorEngine()
    scenario = SimulationScenario(
        scenario_id="custom_1",
        title="Kurs narxi eʼtirozi",
        goal="Sinov darsiga yozish",
        situation="Mijoz boshqa kurs arzonroq deydi",
        client_name="Dilnoza",
        client_gender="female",
        mood="shubhada",
        what_convinces="Kafolatlangan amaliyot va natija",
        hidden_facts=[
            "Uyi yaqinidagi markazda sifat pastligini oʻzi ham biladi",
            "Aslida farzandiga natija kerak",
        ],
    )

    # Manager asks about price directly -> hidden facts NOT revealed
    turn1_eval = engine.process_manager_message(
        scenario=scenario,
        history=[],
        manager_message="Bizda kurs 1 million soʻm turadi.",
    )
    assert len(turn1_eval.revealed_facts) == 0

    # Manager asks about child's goals and past experience -> triggers discovery
    turn2_eval = engine.process_manager_message(
        scenario=scenario,
        history=[
            SimulationTurn(role="client", content="Nega buncha qimmat sizlarda?"),
        ],
        manager_message="Farzandingiz oldin qayerda oʻqigan va qanday natijaga erishmoqchisiz?",
    )
    assert len(turn2_eval.revealed_facts) >= 1
    assert "natija" in turn2_eval.client_response.lower() or "markaz" in turn2_eval.client_response.lower()


def test_session_evaluation():
    engine = SalesSimulatorEngine()
    history = [
        SimulationTurn(role="manager", content="Assalomu alaykum Kamola opa, Oisha-OS kompaniyasidanman."),
        SimulationTurn(role="client", content="Vaalaykum assalom, hozir band edim."),
        SimulationTurn(role="manager", content="Sizni tushunaman, atigi 1 daqiqa vaqtingizni olaman, kechagi arizangiz boʻyicha bogʻlangandim."),
        SimulationTurn(role="client", content="Ha, qiziqishim bor edi."),
        SimulationTurn(role="manager", content="Ehtiyojingizni toʻliq tushunish uchun qachon qulay vaqtda batafsil gaplashsak boʻladi?"),
        SimulationTurn(role="client", content="Ertaga soat 15:00 da qoʻngʻiroq qiling."),
        SimulationTurn(role="manager", content="Ajoyib, ertaga 15:00 ga belgiladim. Rahmat!"),
    ]

    evaluation = engine.evaluate_session("first_30_seconds", history)
    assert evaluation.overall_score >= 70
    assert evaluation.active_listening >= 60
    assert evaluation.next_step_agreement is True
    assert len(evaluation.strengths) > 0
    assert evaluation.coaching_feedback != ""
