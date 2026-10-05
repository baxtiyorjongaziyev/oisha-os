import json
from pathlib import Path

import pytest

from src.services.core.crm.task_notifier import formatter
from src.services.core.crm.task_notifier.formatter import format_task_notification

SNAPSHOT = Path(__file__).parent / "fixtures" / "snapshots" / "task_notifications.json"

LEAD = {
    "name": "Logo <Brend>", "pipeline_id": 11162698, "status_id": 88871062, "price": "12500000",
    "custom_fields_values": [
        {"field_id": 1034671, "values": [{"value": "Logo & Brandbook"}]},
        {"field_id": 1034663, "values": ["Instagram"]},
        {"field_id": 1037937, "values": [{"value": " @jon_client "}]},
    ],
}
CONTACT = {
    "name": "Aziz", "phone": "+998901234567",
    "custom_fields_values": [{"field_id": 1340887, "values": [{"value": "aziz_tg"}]}],
}

CASES = {
    "lead_full_due": dict(
        task={"entity_type": "leads", "entity_id": 555, "task_type_id": 2,
              "text": "  Uchrashuv <b>KP</b> ", "complete_till": 1790000000},
        lead_or_contact=LEAD, contact_details=CONTACT, responsible_name="Ali & Co",
    ),
    "lead_overdue_unknown_ids": dict(
        task={"entity_type": 2, "element_id": 9, "task_type": 999},
        lead_or_contact={"name": "X", "pipeline_id": 1, "status_id": 2, "price": 0},
        alert_type="overdue", subdomain="demo",
    ),
    "lead_status_only_bad_price": dict(
        task={"entity_id": 3, "text": ""},
        lead_or_contact={"name": "Aziz", "status_id": 142, "price": "abc"},
        contact_details={"name": "Aziz"}, phone="+1 <2>",
    ),
    "contact_new": dict(
        task={"entity_type": "contacts", "entity_id": 77, "task_type_id": 1},
        lead_or_contact=CONTACT, alert_type="new",
    ),
    "lead_missing_no_entity": dict(task={"entity_type": "leads"}),
    "other_entity_type": dict(
        task={"entity_type": "companies", "entity_id": 4}, lead_or_contact={"name": "Co"},
    ),
}


@pytest.fixture(autouse=True)
def _fixed_timestamp(monkeypatch):
    monkeypatch.setattr(formatter, "_format_timestamp", lambda ts: f"TS({ts})")


def render(name):
    msg, buttons = format_task_notification(**CASES[name])
    return {"msg": msg, "buttons": buttons}


@pytest.mark.parametrize("name", sorted(CASES))
def test_format_task_notification_matches_snapshot(name):
    expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert render(name) == expected[name]
