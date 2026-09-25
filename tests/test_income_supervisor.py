import asyncio
from unittest.mock import MagicMock

import pytest

from src.services.core.finance import income_supervisor as sup


@pytest.fixture(autouse=True)
def _isolate_state(tmp_path, monkeypatch):
    monkeypatch.setattr(sup, "_ALERTED_STATE_PATH", tmp_path / "alerted.json")
    monkeypatch.setattr(sup, "_ALERTED_RECORD_IDS", set())
    monkeypatch.setattr(sup, "_ALERTED_LOADED", False)
    sent = []
    monkeypatch.setattr(sup, "_dispatch_supervisor_alert", lambda text: sent.append(text) or True)
    return sent


def _at(records, update_ok=True):
    at = MagicMock()
    at.get_transactions.return_value = records
    at.update_project_fields.return_value = update_ok
    return at


def _crm(leads):
    crm = MagicMock()

    async def search_leads(term, limit=3):
        return leads

    crm.search_leads = search_leads
    return crm


REC = {"id": "recX", "fields": {"Turi": "Kirim", "Sana": "2026-09-20", "Tranzaksiya": "Kirim - Asl kids",
                                "Summa UZS": 8_000_000, "Izoh": "#kirim"}}


def test_unresolved_alert_survives_restart(_isolate_state):
    sent = _isolate_state
    asyncio.run(sup.supervise_recent_incomes(_at([REC]), _crm([])))
    assert len(sent) == 1
    # Simulate process restart: memory wiped, file stays.
    sup._ALERTED_RECORD_IDS.clear()
    sup._ALERTED_LOADED = False
    asyncio.run(sup.supervise_recent_incomes(_at([REC]), _crm([])))
    assert len(sent) == 1


def test_no_resolved_alert_when_airtable_update_fails(_isolate_state):
    sent = _isolate_state
    lead = {"id": 1, "name": "x", "responsible_user_id": 13021974}
    stats = asyncio.run(sup.supervise_recent_incomes(_at([REC], update_ok=False), _crm([lead])))
    assert sent == []
    assert stats["resolved"] == 0


def test_resolved_alert_when_update_ok(_isolate_state):
    sent = _isolate_state
    lead = {"id": 1, "name": "x", "responsible_user_id": 13021974}
    stats = asyncio.run(sup.supervise_recent_incomes(_at([REC]), _crm([lead])))
    assert stats["resolved"] == 1 and len(sent) == 1 and "Shahnoza" in sent[0]


def test_cancelled_income_is_skipped(_isolate_state):
    rec = {"id": "recC", "fields": dict(REC["fields"], Holat={"name": "Bekor qilingan"})}
    stats = asyncio.run(sup.supervise_recent_incomes(_at([rec]), _crm([])))
    assert stats["checked"] == 0 and _isolate_state == []


def test_failed_telegram_delivery_retries_next_cycle(_isolate_state, monkeypatch):
    calls = []
    monkeypatch.setattr(sup, "_dispatch_supervisor_alert", lambda text: calls.append(text) and False)
    asyncio.run(sup.supervise_recent_incomes(_at([REC]), _crm([])))
    asyncio.run(sup.supervise_recent_incomes(_at([REC]), _crm([])))
    assert len(calls) == 2 and "recX" not in sup._ALERTED_RECORD_IDS


def test_linked_project_seller_is_used(_isolate_state, monkeypatch):
    monkeypatch.setattr(sup, "_fetch_project_record", lambda rid: {"fields": {"Sotuvchi": ["recfj3ExodGmnN2VW"]}})
    rec = {"id": "recL", "fields": dict(REC["fields"], Loyiha=["recProj"])}
    res = asyncio.run(sup.resolve_seller_for_income(rec, airtable_sync=MagicMock(), amocrm_sync=None))
    assert res["seller_id"] == "recfj3ExodGmnN2VW" and res["source"] == "Loyiha kartasi"
