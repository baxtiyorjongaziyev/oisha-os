from src.schedulers.unowned_lead_alert import (
    BOT_RESPONSIBLE_USER_ID,
    INHOUSE_TAG,
    _alerted,
    build_alert_text,
    find_unowned_inhouse_leads,
)

NOW = 1_800_000_000


def _lead(lead_id, minutes_ago, owner=BOT_RESPONSIBLE_USER_ID, tag=INHOUSE_TAG, status=87609514):
    return {
        "id": lead_id,
        "name": "Test <lead>",
        "status_id": status,
        "responsible_user_id": owner,
        "created_at": NOW - minutes_ago * 60,
        "_embedded": {"tags": [{"name": tag}]},
    }


def test_only_old_unowned_inhouse_leads_are_flagged():
    _alerted.clear()
    leads = [
        _lead(1, 45),                              # flagged
        _lead(2, 10),                              # too fresh
        _lead(3, 45, owner=8128012),               # already has a manager
        _lead(4, 45, tag="taqsimot:utc_outsource"),  # UTC, not inhouse
        _lead(5, 45, status=143),                  # closed
        _lead(6, 60 * 30),                         # older than 24h backlog
    ]
    assert [l["id"] for l in find_unowned_inhouse_leads(leads, NOW)] == [1]


def test_already_alerted_lead_is_skipped():
    _alerted.clear()
    _alerted.add(1)
    assert find_unowned_inhouse_leads([_lead(1, 45)], NOW) == []
    _alerted.clear()


def test_alert_text_escapes_name_and_shows_minutes():
    text = build_alert_text(_lead(1, 45), NOW)
    assert "Test &lt;lead&gt;" in text
    assert "45 daqiqa" in text
