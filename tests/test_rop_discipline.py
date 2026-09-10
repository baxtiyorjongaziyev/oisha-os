# tests/test_rop_discipline.py
from datetime import datetime, timezone
from src.services.core.rop.config import DEFAULTS
from src.services.core.rop.discipline import find, Finding

CFG = dict(DEFAULTS)
NOW = datetime(2026, 9, 10, 15, 0, tzinfo=timezone.utc)
E = int(NOW.timestamp())

def _types(findings, name):
    return sorted(f.type for f in findings if f.lead_name == name)

def test_no_next_task_and_stagnant():
    leads = [{"id": 1, "name": "ABC", "status_id": 111,
              "responsible_user_id": 101, "updated_at": E - 5 * 86400}]
    out = find(leads, {1: []}, {1: []}, CFG, NOW)
    assert _types(out, "ABC") == ["NO_NEXT_TASK", "STAGNANT"]

def test_overdue_task_detail():
    leads = [{"id": 2, "name": "XYZ", "status_id": 111,
              "responsible_user_id": 101, "updated_at": E - 100}]
    tasks = {2: [{"is_completed": False, "complete_till": E - 3600, "text": "Qo'ng'iroq qilish"}]}
    out = find(leads, tasks, {2: []}, CFG, NOW)
    od = [f for f in out if f.type == "OVERDUE_TASK"]
    assert od and od[0].detail == "Qo'ng'iroq qilish"

def test_no_owner_reported():
    leads = [{"id": 3, "name": "Sport Life", "status_id": 111,
              "responsible_user_id": None, "updated_at": E - 100}]
    out = find(leads, {3: [{"is_completed": False, "complete_till": E + 3600}]}, {3: []}, CFG, NOW)
    assert any(f.type == "NO_OWNER" and f.lead_name == "Sport Life" for f in out)

def test_wrong_stage_won_with_open_task():
    leads = [{"id": 4, "name": "Done Co", "status_id": 142,
              "responsible_user_id": 101, "updated_at": E - 100}]
    out = find(leads, {4: [{"is_completed": False, "complete_till": E + 3600}]}, {4: []}, CFG, NOW)
    assert any(f.type == "WRONG_STAGE" for f in out)

def test_important_no_note():
    leads = [{"id": 5, "name": "CallCo", "status_id": 111,
              "responsible_user_id": 101, "updated_at": E - 100}]
    tasks = {5: [
        {"is_completed": True, "task_type_id": 1, "complete_till": E - 1800},   # call done 30m ago
        {"is_completed": False, "complete_till": E + 3600},
    ]}
    out = find(leads, tasks, {5: []}, CFG, NOW)
    assert any(f.type == "IMPORTANT_NO_NOTE" for f in out)
    # with a fresh note, it disappears
    out2 = find(leads, tasks, {5: [{"created_at": E - 600, "params": {"text": "gaplashdim"}}]}, CFG, NOW)
    assert not any(f.type == "IMPORTANT_NO_NOTE" for f in out2)
