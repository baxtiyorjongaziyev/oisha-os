import json
from pathlib import Path
from src.schedulers.unowned_lead_alert import (
    BOT_RESPONSIBLE_USER_ID,
    INHOUSE_TAG,
    _alerted,
    build_alert_text,
    find_unowned_inhouse_leads,
    format_duration,
    get_known_manager_names,
    is_claimed_by_manager,
    is_lead_alerted,
    mark_lead_alerted,
)
import src.schedulers.unowned_lead_alert as alert_module

NOW = 1_800_000_000


def _lead(lead_id, minutes_ago, owner=BOT_RESPONSIBLE_USER_ID, tag=INHOUSE_TAG, status=87609514, extra_tags=None):
    tags = [{"name": tag}]
    if extra_tags:
        for t in extra_tags:
            tags.append({"name": t})
    return {
        "id": lead_id,
        "name": "Test <lead>",
        "status_id": status,
        "responsible_user_id": owner,
        "created_at": NOW - minutes_ago * 60,
        "_embedded": {"tags": tags},
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


def test_lead_with_manager_tag_is_skipped():
    _alerted.clear()
    leads = [
        _lead(10, 45, extra_tags=["Shahnoza"]),          # claimed by Shahnoza tag
        _lead(11, 45, extra_tags=["Rayxon"]),            # claimed by Rayxon tag
        _lead(12, 45, extra_tags=["menejer:Farangiz"]),   # claimed by prefix
        _lead(13, 45, extra_tags=["mas'ul:Aziz"]),       # claimed by prefix
        _lead(14, 45, extra_tags=["reklama:brending"]),   # system tag, NOT claimed
    ]
    flagged = find_unowned_inhouse_leads(leads, NOW)
    assert [l["id"] for l in flagged] == [14]


def test_is_claimed_by_manager():
    assert is_claimed_by_manager(["Shahnoza"]) is True
    assert is_claimed_by_manager(["rayxon"]) is True
    assert is_claimed_by_manager(["FARANGIZ"]) is True
    assert is_claimed_by_manager(["menejer: Dilshod"]) is True
    assert is_claimed_by_manager(["mas'ul: Shahnoza"]) is True
    assert is_claimed_by_manager(["taqsimot:inhouse", "Facebook Lead Ads", "Target"]) is False
    assert is_claimed_by_manager([]) is False


def test_moizvonki_rep_names_in_manager_tags(monkeypatch):
    monkeypatch.setenv("MOIZVONKI_REP_NAMES", "botir@jonbranding.uz:Botir,zarina@jonbranding.uz:Zarina")
    names = get_known_manager_names()
    assert "botir" in names
    assert "zarina" in names
    assert is_claimed_by_manager(["Botir"]) is True


def test_persistent_dedup_survives_restart(tmp_path, monkeypatch):
    test_file = tmp_path / "alerted_unowned_leads.json"
    monkeypatch.setattr(alert_module, "_DEDUP_FILE", test_file)
    monkeypatch.setattr(alert_module, "_INITIALIZED", True)
    _alerted.clear()

    # Mark lead 101 as alerted
    mark_lead_alerted(101, NOW)
    assert 101 in _alerted
    assert test_file.exists()

    # Simulate full restart / redeploy: clear RAM state and uninitialize
    _alerted.clear()
    monkeypatch.setattr(alert_module, "_INITIALIZED", False)

    # Lead should still be recognized as alerted from disk
    assert is_lead_alerted(101) is True
    assert 101 in _alerted

    # find_unowned_inhouse_leads must skip it even after restart
    lead = _lead(101, 45)
    assert find_unowned_inhouse_leads([lead], NOW) == []


def test_persistent_dedup_prunes_old_records(tmp_path, monkeypatch):
    test_file = tmp_path / "alerted_unowned_leads.json"
    monkeypatch.setattr(alert_module, "_DEDUP_FILE", test_file)
    monkeypatch.setattr(alert_module, "_INITIALIZED", True)
    _alerted.clear()

    # Seed an old record (20 days ago)
    old_time = NOW - 20 * 86400
    with open(test_file, "w", encoding="utf-8") as f:
        json.dump({"999": old_time}, f)

    # Mark a new lead
    mark_lead_alerted(202, NOW)

    with open(test_file, "r", encoding="utf-8") as f:
        saved = json.load(f)

    assert "202" in saved
    assert "999" not in saved  # pruned


def test_alert_text_escapes_name_and_shows_minutes():
    text = build_alert_text(_lead(1, 45), NOW)
    assert "Test &lt;lead&gt;" in text
    assert "45 daqiqa" in text


def test_format_duration_boundaries():
    assert format_duration(45) == "45 daqiqa"
    assert format_duration(60) == "1 soat"
    assert format_duration(1392) == "23 soat 12 daqiqa"
    assert format_duration(1439) == "23 soat 59 daqiqa"
    assert format_duration(1440) == "1 kun"
    assert format_duration(1500) == "1 kun 1 soat"
    assert format_duration(4 * 1440 + 125) == "4 kun 2 soat"


def test_alert_text_uses_hours_after_60_minutes():
    now = 10_000_000
    text = build_alert_text({"name": "Lobar", "created_at": now - 1392 * 60}, now)
    assert "23 soat 12 daqiqadan beri" in text
