from src.services.core.rop.config import DEFAULTS
from src.services.core.rop.traffic_light import evaluate, SellerMetrics, TrafficResult
from src.services.core.rop.discipline import Finding

CFG = dict(DEFAULTS)


def m(**over):
    base = dict(
        won_today=1, no_result_streak_days=0, overdue_count=0,
        calls_done=10, calls_target=10, follow_ups_done=20, follow_ups_target=20,
        meetings_done=2, meetings_target=2, biggest_stuck_deal_amount=0,
        biggest_stuck_deal_days=0.0, hot_lead_max_silent_hours=0.0, hot_band_dropped=False,
    )
    base.update(over)
    return SellerMetrics(**base)


def test_all_good_is_green():
    r = evaluate(m(), [], CFG)
    assert isinstance(r, TrafficResult) and r.level == "GREEN"


def test_no_result_streak_is_red():
    r = evaluate(m(won_today=0, no_result_streak_days=3), [], CFG)
    assert r.level == "RED"


def test_overdue_pile_is_red():
    assert evaluate(m(overdue_count=5), [], CFG).level == "RED"


def test_big_stuck_deal_is_red():
    r = evaluate(m(biggest_stuck_deal_amount=12_000_000, biggest_stuck_deal_days=15.0), [], CFG)
    assert r.level == "RED"


def test_discipline_pile_is_red():
    r = evaluate(m(), [Finding("L", "NO_NEXT_TASK", "")] * 8, CFG)
    assert r.level == "RED"


def test_low_pace_is_yellow():
    r = evaluate(m(calls_done=3, follow_ups_done=5, meetings_done=0), [], CFG)
    assert r.level == "YELLOW"


def test_silent_hot_lead_is_yellow():
    assert evaluate(m(hot_lead_max_silent_hours=50.0), [], CFG).level == "YELLOW"


def test_band_drop_is_yellow():
    assert evaluate(m(hot_band_dropped=True), [], CFG).level == "YELLOW"


def test_red_beats_yellow():
    r = evaluate(m(overdue_count=6, calls_done=0), [], CFG)
    assert r.level == "RED"
