# tests/test_rop_daily.py
from datetime import datetime, timezone
from src.services.core.rop.config import DEFAULTS
from src.services.core.rop.targets import SellerTarget
from src.services.core.rop.daily import (
    score_seller_leads, build_morning, build_midday, build_evening,
    build_ceo_dashboard, pick_action, LeadScore,
)
from src.services.core.rop.traffic_light import TrafficResult

CFG = dict(DEFAULTS)
CFG["score.stage_weights"] = {"200": 0.85, "100": 0.15}
NOW = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
E = int(NOW.timestamp())
SELLER = SellerTarget(101, "Oydin", 555, 1, 10, 20, 2, 0, 1, 0)


def _leads():
    return [
        {"id": 1, "name": "ABC", "status_id": 200, "price": 12_000_000,
         "responsible_user_id": 101, "updated_at": E - 3600, "created_at": E - 5 * 86400},
        {"id": 2, "name": "XYZ", "status_id": 100, "price": 4_000_000,
         "responsible_user_id": 101, "updated_at": E - 200 * 3600, "created_at": E - 40 * 86400},
    ]


def test_score_seller_leads_sorted_desc():
    scored = score_seller_leads(_leads(), {1: [], 2: []}, {1: [], 2: []}, {1: [], 2: []}, CFG, NOW)
    assert [s.name for s in scored] == ["ABC", "XYZ"]
    assert scored[0].score > scored[1].score
    assert isinstance(scored[0], LeadScore)


def test_build_morning_expected_and_top():
    scored = score_seller_leads(_leads(), {1: [], 2: []}, {1: [], 2: []}, {1: [], 2: []}, CFG, NOW)
    mp = build_morning(SELLER, scored, {1: [], 2: []}, [], CFG, NOW)
    assert mp.top_closings[0].name == "ABC"
    assert mp.expected_revenue_total >= 1
    assert any(e.name == "ABC" for e in mp.expected)


def test_build_midday_on_track_suppression_logic():
    scored = score_seller_leads(_leads(), {1: [], 2: []}, {1: [], 2: []}, {1: [], 2: []}, CFG, NOW)
    good = build_midday(SELLER, scored, dict(calls=5, follow_ups=8, meetings=1, won=0), {1, 2}, CFG)
    assert good.on_track is True
    bad = build_midday(SELLER, scored, dict(calls=1, follow_ups=1, meetings=0, won=0), set(), CFG)
    assert bad.on_track is False
    assert "ABC" in bad.hot_not_touched


def test_build_evening_fields():
    scored = score_seller_leads(_leads(), {1: [], 2: []}, {1: [], 2: []}, {1: [], 2: []}, CFG, NOW)
    ev = build_evening(SELLER, scored, dict(calls=9, follow_ups=18, meetings=2, won=1, won_revenue=12_000_000), overdue_count=0)
    assert ev.sales_done == 1 and ev.calls_done == 9
    assert len(ev.tomorrow_closings) >= 1


def test_pick_action_maps_reason():
    assert pick_action(["To'lov va'da qilingan"]) in {"bugun qo'ng'iroq", "follow-up"}
    assert pick_action(["Ochiq e'tiroz bor"]) == "narx objection yop"
    assert pick_action(["72 soatdan beri aloqa yo'q"]) == "follow-up"
    assert pick_action([]) == "follow-up"


def test_build_ceo_dashboard_aggregates():
    scored = score_seller_leads(_leads(), {1: [], 2: []}, {1: [], 2: []}, {1: [], 2: []}, CFG, NOW)
    ev = build_evening(SELLER, scored, dict(calls=9, follow_ups=18, meetings=2, won=1, won_revenue=12_000_000), 0)
    from src.services.core.rop.weekly import progress
    wk = progress([{"status_id": 142, "price": 12_000_000}], CFG)
    dash = build_ceo_dashboard([ev], {101: TrafficResult("GREEN", [])}, wk, expected_tomorrow=5_000_000, skipped=0)
    assert dash.team_fakt == 1
    assert dash.team_revenue == 12_000_000
