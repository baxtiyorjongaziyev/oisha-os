# tests/test_rop_scoring.py
from datetime import datetime, timezone
import pytest
from src.services.core.rop.config import DEFAULTS
from src.services.core.rop.scoring import score_lead, ScoreResult, DISCLAIMER

CFG = dict(DEFAULTS)
NOW = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)

def feats(**over):
    base = dict(
        stage_weight=0.15, last_interaction_hours=1.0, has_open_next_task=True,
        task_overdue=False, proposal_sent=False, meeting_held=False,
        objection_open=False, payment_promised=False, days_in_stage=3.0,
    )
    base.update(over)
    return base

def test_hot_deal_scores_high_and_bands_hot():
    r = score_lead(feats(stage_weight=0.85, proposal_sent=True, meeting_held=True,
                         payment_promised=True, last_interaction_hours=2.0,
                         days_in_stage=4.0), CFG)
    assert isinstance(r, ScoreResult)
    assert r.score >= 70
    assert r.band == "HOT"
    assert any("to'lov" in x.lower() for x in r.reasons)

def test_cold_deal_bands_cold():
    r = score_lead(feats(stage_weight=0.1, has_open_next_task=False,
                         task_overdue=True, objection_open=True,
                         last_interaction_hours=120.0, days_in_stage=40.0), CFG)
    assert r.score < 40
    assert r.band == "COLD"

def test_warm_middle_band():
    r = score_lead(feats(stage_weight=0.55, proposal_sent=True,
                         last_interaction_hours=30.0, days_in_stage=10.0), CFG)
    assert 40 <= r.score < 70
    assert r.band == "WARM"

def test_score_clamped_0_100():
    lo = score_lead(feats(stage_weight=0.0, has_open_next_task=False,
                          task_overdue=True, objection_open=True,
                          last_interaction_hours=300.0, days_in_stage=99.0), CFG)
    hi = score_lead(feats(stage_weight=1.0, has_open_next_task=True,
                          proposal_sent=True, meeting_held=True,
                          payment_promised=True, last_interaction_hours=1.0,
                          days_in_stage=1.0), CFG)
    assert 0 <= lo.score <= 100 and 0 <= hi.score <= 100

def test_disclaimer_constant():
    assert DISCLAIMER == "AI bahosi (taxminiy), fakt emas."

from src.services.core.rop.scoring import derive_features

def test_derive_features_from_raw_amocrm_shapes():
    lead = {"status_id": 111, "created_at": int(NOW.timestamp()) - 10 * 86400}
    tasks = [
        {"is_completed": True, "task_type_id": 2, "complete_till": int(NOW.timestamp()) - 3600},
        {"is_completed": False, "task_type_id": 1, "complete_till": int(NOW.timestamp()) - 7200},
    ]
    notes = [
        {"created_at": int(NOW.timestamp()) - 5000, "params": {"text": "Mijoz narx qimmat dedi"}},
        {"created_at": int(NOW.timestamp()) - 1000, "params": {"text": "To'lov kuni kelishildi"}},
    ]
    events = [{"type": "lead_status_changed", "created_at": int(NOW.timestamp()) - 2 * 86400}]
    cfg = dict(DEFAULTS)
    cfg["score.stage_weights"] = {"111": 0.55}
    f = derive_features(lead, tasks, notes, events, cfg, NOW)
    assert f["stage_weight"] == 0.55
    assert f["meeting_held"] is True
    assert f["task_overdue"] is True
    assert f["payment_promised"] is True
    assert f["objection_open"] is False   # "kelishildi" resolves it
    assert 1.9 < f["days_in_stage"] < 2.1
    assert f["last_interaction_hours"] < 1.0
