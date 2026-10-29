"""Tests for Moizvonki Multi-Account Real-Time Caller ID."""
import pytest
from src.services.core.crm.caller_id_service import CallerIdHub, resolve_rep
from src.services.core.crm.dialer_store import DialerStore


@pytest.fixture
def store(tmp_path):
    db_file = str(tmp_path / "test_caller_id.db")
    st = DialerStore(db_path=db_file)
    st.create_or_update_lead({
        "id": 991122,
        "name": "Muzaffar Aka Qurilish",
        "contact_name": "Muzaffar Aka",
        "company_name": "Qurilish Servis MCHJ",
        "phone": "+998901234567",
        "price": 25000000,
        "status_slug": "uchrashuv",
        "responsible_name": "Rayxona",
    })
    return st


def test_resolve_rep():
    assert resolve_rep("shahnoza@jonbranding.uz")["slug"] == "shahnoza"
    assert resolve_rep("rayxona@jonbranding.uz")["slug"] == "rayxona"
    assert resolve_rep("farangiz@jonbranding.uz")["slug"] == "unknown"
    assert resolve_rep("mumtozmaxal@jonbranding.uz")["slug"] == "mumtozmaxal"


def test_caller_id_ring_and_match(store):
    hub = CallerIdHub(store=store)
    event = hub.process_incoming_ring("+998901234567", account="rayxona@jonbranding.uz")
    assert event["type"] == "ring"
    assert event["target_rep_slug"] == "rayxona"
    assert event["lead"] is not None
    assert event["lead"]["id"] == 991122
    assert event["lead"]["contact_name"] == "Muzaffar Aka"

    # Only Rayxona sees it
    assert hub.get_active_ring("rayxona") is not None
    assert hub.get_active_ring("shahnoza") is None

    # Dismiss
    hub.dismiss_ring("rayxona")
    assert hub.get_active_ring("rayxona") is None


def test_caller_id_new_number(store):
    hub = CallerIdHub(store=store)
    event = hub.process_incoming_ring("+998979998877", account="shahnoza@jonbranding.uz")
    assert event["lead"] is None
    assert event["phone"] == "+998979998877"
    assert hub.get_active_ring("shahnoza")["lead"] is None
