"""Synthetic evidence cases for context-specific quality and immutable reviews."""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.services.call_analytics.contextual_quality import evaluate_context
from src.services.call_analytics.scorecards import TYPES, evaluation_prompt, scorecard
from src.services.sales_quality.reviews import QualityReviews, ReviewConflict

TEXT = "Sotuvchi: Salom, sizga qanday yordam bera olaman?\nMijoz: Muammo va muddatni aniqlashtiraylik."
QUOTE = "sizga qanday yordam bera olaman?"


def raw_evaluation(kind="discovery"):
    return {"conversation_type": kind, "type_confidence": .9, "type_evidence": QUOTE,
            "qa_criteria": {c["id"]: {"status": "met", "quote": QUOTE, "reason": "Synthetic evidence"}
                            for c in scorecard(kind)["criteria"]}}


def test_different_purposes_have_different_requirements():
    assert len(TYPES) == 18
    networking = {c["id"] for c in scorecard("networking")["criteria"]}
    assert "relationship" in networking
    assert "terms" not in networking
    assert "candidate_fit" in {c["id"] for c in scorecard("recruiting")["criteria"]}
    assert "coordination" in {c["id"] for c in scorecard("internal")["criteria"]}
    assert "cold_outreach" in evaluation_prompt()


def test_na_does_not_lower_score_but_unmet_does():
    raw = raw_evaluation("negotiation")
    raw["qa_criteria"]["objection"] = {"status": "not_applicable", "reason": "E'tiroz bo'lmadi"}
    raw["qa_criteria"]["terms"]["status"] = "unmet"
    result = evaluate_context(raw, TEXT)
    assert result["score"] == 75
    assert result["coverage"] == 1
    assert result["review_ready"] is True
    assert result["kpi_eligible"] is False


def test_unknown_and_fabricated_evidence_are_not_scored_as_zero():
    raw = raw_evaluation()
    raw["qa_criteria"]["discovery"]["quote"] = "This quote is not in the recording"
    raw["qa_criteria"]["qualification"] = {"status": "unknown"}
    result = evaluate_context(raw, TEXT)
    assert result["score"] == 100
    assert result["coverage"] == .5
    assert result["review_ready"] is False
    assert [c["status"] for c in result["criteria"]].count("unknown") == 2


def test_required_criteria_cannot_be_evaded_with_na():
    raw = raw_evaluation()
    for item in raw["qa_criteria"].values():
        item.update(status="not_applicable", reason="Skipping a required step")
    result = evaluate_context(raw, TEXT)
    assert result["score"] is None
    assert result["coverage"] == 0


@pytest.mark.parametrize("kind", ["unknown", "personal", "family", "spam", "unanswered", "unusable_audio", "invented_type"])
def test_unscorable_calls_never_get_a_sales_score(kind):
    result = evaluate_context({"conversation_type": kind}, TEXT)
    assert result["score"] is None
    assert result["sales_quality"] is False
    assert result["review_ready"] is False


@pytest.mark.parametrize("confidence", [None, "nan", float("inf"), True, 1.1, .7])
def test_uncertain_classification_is_held_for_review(confidence):
    raw = {**raw_evaluation(), "type_confidence": confidence}
    assert evaluate_context(raw, TEXT)["review_ready"] is False


def test_review_appeal_and_source_changes_preserve_audit_but_reset_approval(tmp_path):
    store = QualityReviews(tmp_path / "reviews.sqlite3")
    result = evaluate_context(raw_evaluation(), TEXT)
    revision = store.save("call", 1, 7, result)
    approved = store.review("call", revision, "owner", "approved", "Reviewed synthetic source", 90)
    assert approved["quality_approved"] is True
    assert approved["kpi_eligible"] is False
    appealed = store.review("call", revision, "7", "appealed", "Transcript mismatch")
    assert appealed["quality_approved"] is False
    assert len(appealed["reviews"]) == 2
    new_revision = store.save("call", 1, 7, {**result, "score": 75})
    assert new_revision != revision
    assert store.get("call")["review_status"] == "pending"
    with pytest.raises(ReviewConflict):
        store.review("call", revision, "owner", "approved", "Stale view")


def test_insufficient_evidence_cannot_be_approved(tmp_path):
    store = QualityReviews(tmp_path / "reviews.sqlite3")
    revision = store.save("unknown", 1, 7, evaluate_context({}, TEXT))
    with pytest.raises(ValueError, match="insufficient_evidence"):
        store.review("unknown", revision, "owner", "approved", "Trying to bypass evidence gate")


@pytest.mark.asyncio
async def test_provider_contract_and_failure_are_safe(monkeypatch):
    from src.services.call_analytics.quality_hook import contextual_review

    monkeypatch.setenv("SKIP_LIVE", "0")
    provider = AsyncMock(return_value=SimpleNamespace(text=json.dumps(raw_evaluation())))
    analyzer = SimpleNamespace(_gemini_generate_content=provider)
    result = await contextual_review(analyzer, TEXT)
    assert result["call_type"] == "discovery"
    assert result["score"] == 100
    assert TEXT in provider.await_args.kwargs["contents"]
    provider.side_effect = RuntimeError("synthetic provider failure")
    assert (await contextual_review(analyzer, TEXT))["score"] is None
