# tests/test_rop_messages.py
from datetime import datetime, timezone
from src.services.core.rop.targets import SellerTarget
from src.services.core.rop.scoring import DISCLAIMER
from src.services.core.rop.daily import (
    SellerMorningPlan, SellerMiddayCheck, SellerEveningResult,
    CeoMorning, CeoMidday, CeoDashboard, LeadScore, ExpectedItem,
)
from src.services.core.rop.discipline import Finding
from src.services.core.rop.weekly import WeeklyProgress
from src.services.core.rop.rop_messages import (
    render_seller_morning, render_seller_midday, render_seller_evening,
    render_ceo_morning, render_ceo_midday, render_ceo_dashboard,
    render_empty_roster_notice, progress_bar, fmt_sum,
)

SELLER = SellerTarget(101, "Oydin", 555, 1, 10, 20, 2, 0, 1, 0)
LS = LeadScore(1, "ABC & Co", 12_000_000, 82, "HOT", ["KP yuborilgan"], "bugun qo'ng'iroq")
WK = WeeklyProgress(6, 60_000_000, 10, 100_000_000, 60.0, 60.0)

def test_fmt_sum_spaces():
    assert fmt_sum(12000000) == "12 000 000"

def test_progress_bar_shape():
    b = progress_bar(60.0)
    assert len(b) == 10 and b.count("█") == 6

def test_seller_morning_has_disclaimer_and_escapes():
    plan = SellerMorningPlan(SELLER, [LS], 3, [("ABC & Co", "Qo'ng'iroq")],
                             ["ABC & Co"], [ExpectedItem("ABC & Co", 9_800_000, 82)],
                             9_800_000, [Finding("ABC & Co", "NO_NEXT_TASK", "")])
    html = render_seller_morning(plan)
    assert DISCLAIMER in html
    assert "ABC &amp; Co" in html and "ABC & Co" not in html.replace("ABC &amp; Co", "")

def test_seller_midday_renders():
    c = SellerMiddayCheck(SELLER, 1, 0, 3, 7, 1, ["ABC & Co"], [LS], False)
    html = render_seller_midday(c)
    assert "7/20" in html or "7 / 20" in html

def test_seller_evening_renders():
    r = SellerEveningResult(SELLER, 1, 12_500_000, 9, 18, 2, 0, [LS])
    html = render_seller_evening(r)
    assert "1/1" in html or "1 / 1" in html

def test_ceo_morning_renders():
    m = CeoMorning(2, 17_000_000, 3, 4, ["Dilnoza"], ["NoOwnerLead"], WK)
    html = render_ceo_morning(m)
    assert "Dilnoza" in html

def test_ceo_midday_renders():
    html = render_ceo_midday(CeoMidday([("Oydin", "sur'at past")], True))
    assert "Oydin" in html

def test_ceo_dashboard_renders_lights_and_weekly():
    d = CeoDashboard(2, 2, 25_000_000, 18_000_000, 0, WK,
                     [("Oydin", "🟢", []), ("Dilnoza", "🔴", ["3 ish kuni natijasiz"])], 0)
    html = render_ceo_dashboard(d)
    assert "🔴" in html and "3 ish kuni natijasiz" in html
    assert "6" in html  # weekly won count

def test_empty_roster_notice():
    assert "sozlanmagan" in render_empty_roster_notice()
