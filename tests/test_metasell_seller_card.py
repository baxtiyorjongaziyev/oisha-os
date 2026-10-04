import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.services.core.metasell.cards import build_seller_card
from src.services.core.metasell.models import SellerDiagnosis

SNAPSHOT = Path(__file__).parent / "fixtures" / "snapshots" / "metasell_seller_cards.json"


def _vol(total, answer_rate, missed=3):
    return SimpleNamespace(total=total, answer_rate=answer_rate, missed=missed, avg_duration_label="2:15")


def _diag(**kw):
    base = dict(manager_name="Ali", total_calls=24, converted_calls=9, conversion_rate=37.5, avg_score=71.4)
    base.update(kw)
    return SellerDiagnosis(**base)


CASES = {
    "full_low_answer": (
        _diag(growth_stage="ehtiyojlar", projected_lift=12.4, reason="Ehtiyoj so'ralmayapti",
              top_weaknesses=["savol kam", "monolog"], top_objections=["qimmat", "vaqt yo'q"],
              revenue_won=15_000_000, revenue_at_risk=8_000_000, deals_won=2, deals_lost=1),
        _vol(40, 62.5),
    ),
    "good_answer_no_risk": (
        _diag(growth_stage="qiymat", projected_lift=1.0, reason="Qiymat zaif", deals_won=1,
              revenue_won=3_000_000),
        _vol(10, 90.0, missed=1),
    ),
    "unknown_stage_small_lift": (
        _diag(growth_stage="noma_lum", projected_lift=0.9, reason="r", top_objections=["x"]),
        _vol(0, 0.0),
    ),
    "no_diagnosis_with_deals": (
        _diag(reason="Kam ma'lumot", deals_lost=1, revenue_at_risk=1_000_000),
        None,
    ),
    "no_diagnosis_minimal": (_diag(total_calls=2, reason="Kam qo'ng'iroq"), _vol(5, 50.0)),
}


def render(name):
    diagnosis, volume = CASES[name]
    return build_seller_card(diagnosis, volume)


@pytest.mark.parametrize("name", sorted(CASES))
def test_build_seller_card_matches_snapshot(name):
    expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert render(name) == expected[name]
