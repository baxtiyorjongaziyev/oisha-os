"""Unit tests for Automated Telegram Daily Brief Service."""
from src.services.proactive.daily_brief import (
    DailyBriefService,
    ManagerDailyBrief,
)


def test_format_brief_uzbek_copy():
    service = DailyBriefService()
    text = service.format_brief(
        name="Kamola",
        month_label="Iyul",
        fact_mln=369.7,
        plan_pct=246,
        target_mln=396.0,
        sales_needed=114,
        kval_needed=679,
        leads_needed=1554,
        hot_deals_cnt=90,
        hot_deals_sum_mln=588.9,
        overdue_calls_cnt=120,
        overdue_tasks_cnt=25,
        weak_skill="Yakunlash va keyingi qadam",
        skill_score=50,
        level_num=4,
        level_title="Kuchli",
    )
    assert "Xayrli tong, Kamola!" in text
    assert "Iyul yakuni: 369.7 mln soʻm (rejaning 246%)." in text
    assert "Avgust maqsadi: 396 mln soʻm." in text
    assert "114 ta sotuv ← 679 ta sifatli lid ← 1554 ta lid." in text
    assert "90 ta issiq bitim yopilishni kutmoqda (588.9 mln soʻm)" in text
    assert "120 ta vaʼda qilingan qayta qoʻngʻiroq kechikkan" in text
    assert "Yakunlash va keyingi qadam (50 ball)" in text
    assert "Daraja: 4/5 — Kuchli." in text


def test_prepare_and_dispatch_briefs():
    service = DailyBriefService()
    managers = [
        {
            "id": "m1",
            "name": "Kamola",
            "has_telegram": True,
            "telegram_chat_id": "123456",
            "fact": 369_700_000,
            "target": 396_000_000,
            "plan_percent": 246,
            "sales_needed": 114,
            "kval_needed": 679,
            "leads_needed": 1554,
            "hot_deals_count": 90,
            "hot_deals_sum": 588_900_000,
            "overdue_calls": 120,
            "overdue_tasks": 25,
            "focus_skill": "Yakunlash va keyingi qadam",
            "skill_score": 50,
            "level": 4,
            "level_title": "Kuchli",
        },
        {
            "id": "m2",
            "name": "Jasur",
            "has_telegram": False,
            "telegram_chat_id": None,
            "fact": 0,
            "target": 5_500_000,
            "plan_percent": 0,
            "hot_deals_count": 0,
            "hot_deals_sum": 0,
            "overdue_calls": 5,
            "overdue_tasks": 2,
        },
    ]

    briefs = service.prepare_bulk_briefs(managers)
    assert len(briefs) == 2
    assert briefs[0].has_telegram is True
    assert briefs[1].has_telegram is False

    dispatched = []

    def mock_sender(chat_id: str, text: str) -> bool:
        dispatched.append((chat_id, text))
        return True

    res = service.dispatch_briefs(briefs, sender_fn=mock_sender)
    assert res["total"] == 2
    assert res["sent"] == 1
    assert res["skipped"] == 1
    assert len(dispatched) == 1
    assert dispatched[0][0] == "123456"
