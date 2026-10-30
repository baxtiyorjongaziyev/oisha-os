"""Synthetic quoted evidence never becomes autonomous KPI credit."""
from src.services.call_analytics.funnel_evidence import EVQN, MEANINGFUL, evaluate_funnel
from src.services.call_analytics.contextual_quality import evaluate_context
from src.services.call_analytics.scorecards import evaluation_prompt

TRANSCRIPT = "Mijoz: Brendimizni yangilash kerak. Keyingi haftada gaplashamiz. Sherigim ham qaror qiladi. Narxni tushundim."


def raw():
    evidence = {"status": "met", "quote": "Brendimizni yangilash kerak", "reason": "synthetic"}
    return {"meaningful_criteria": {k: dict(evidence) for k in MEANINGFUL},
            "evqn_criteria": {k: dict(evidence) for k in EVQN}}


def test_supported_candidates_require_review_and_do_not_prove_outcomes():
    result = evaluate_funnel(raw(), TRANSCRIPT, True)
    assert result["meaningful"]["status"] == "evidence_candidate"
    assert result["evqn"]["status"] == "evidence_candidate"
    assert result["human_review_required"] is True
    for key in ("kpi_credited", "duration_verified", "meeting_held_verified", "sale_verified"):
        assert result[key] is False


def test_fabricated_quote_and_silence_are_unknown_not_unmet():
    supplied = raw()
    supplied["meaningful_criteria"]["need"]["quote"] = "invented evidence"
    supplied["evqn_criteria"].pop("price")
    result = evaluate_funnel(supplied, TRANSCRIPT, True)
    assert result["meaningful"]["status"] == "unknown"
    assert result["evqn"]["status"] == "unknown"
    assert result["meaningful"]["criteria"][0]["quote"] == ""


def test_explicit_failure_and_non_sales_exclusion():
    supplied = raw()
    supplied["evqn_criteria"]["price"]["status"] = "unmet"
    assert evaluate_funnel(supplied, TRANSCRIPT, True)["evqn"]["status"] == "not_met"
    assert evaluate_funnel(raw(), TRANSCRIPT, False)["meaningful"]["status"] == "excluded"


def test_analysis_path_requests_and_validates_additional_evidence():
    prompt = evaluation_prompt()
    assert "meaningful_criteria" in prompt and "evqn_criteria" in prompt
    result = evaluate_context({**raw(), "conversation_type": "discovery"}, TRANSCRIPT)
    assert result["funnel_evidence"]["meaningful"]["status"] == "evidence_candidate"
    assert result["kpi_eligible"] is False
