from unittest.mock import MagicMock, patch
import pytest

from src.services.core.instagram.leadgen_delivery import (
    record_delivery_status,
    mark_channel_delivered,
    get_pending_deliveries,
    get_delivery_summary,
)
from src.services.core.instagram.leadgen_watchdog import (
    retry_pending_leadgen_deliveries,
    audit_leadgen_health,
)


def test_delivery_status_tracking():
    leadgen_id = "test_lead_9999"
    record_delivery_status(
        leadgen_id=leadgen_id,
        lead_id=12345,
        amocrm_ok=True,
        sheets_ok=False,
        telegram_ok=True,
        error="sheets timeout",
    )

    pending = get_pending_deliveries()
    matching = [p for p in pending if p["leadgen_id"] == leadgen_id]
    assert len(matching) == 1
    assert matching[0]["sheets_ok"] == 0
    assert matching[0]["amocrm_ok"] == 1
    assert matching[0]["telegram_ok"] == 1

    mark_channel_delivered(leadgen_id, "sheets")
    pending_after = get_pending_deliveries()
    matching_after = [p for p in pending_after if p["leadgen_id"] == leadgen_id]
    assert len(matching_after) == 0


def test_pending_skips_in_flight_rows():
    import uuid
    leadgen_id = f"test_in_flight_{uuid.uuid4().hex[:8]}"
    record_delivery_status(
        leadgen_id=leadgen_id, lead_id=555, amocrm_ok=True, sheets_ok=False, telegram_ok=False,
    )
    fresh = get_pending_deliveries(limit=1000, min_age_seconds=600)
    assert all(p["leadgen_id"] != leadgen_id for p in fresh)
    now = get_pending_deliveries(limit=1000, min_age_seconds=0)
    assert any(p["leadgen_id"] == leadgen_id for p in now)


def test_delivery_summary():
    summary = get_delivery_summary(hours=24)
    assert "total" in summary
    assert "amocrm_ok" in summary
    assert "sheets_ok" in summary
    assert "telegram_ok" in summary
    assert "pending" in summary


def test_channel_status_and_completion():
    from src.services.core.instagram.leadgen_delivery import (
        is_delivery_complete,
        get_delivery_channel_status,
    )
    from src.services.core.instagram.leadgen_dedup import is_leadgen_processed

    import uuid
    lead_id_str = f"test_lead_complete_{uuid.uuid4().hex[:8]}"
    assert is_delivery_complete(lead_id_str) is False
    status = get_delivery_channel_status(lead_id_str)
    assert status == {"amocrm": False, "sheets": False, "telegram": False}

    record_delivery_status(
        leadgen_id=lead_id_str,
        lead_id=98765,
        amocrm_ok=True,
        sheets_ok=True,
        telegram_ok=True,
    )
    assert is_delivery_complete(lead_id_str) is True
    assert is_leadgen_processed(lead_id_str) is True
    status = get_delivery_channel_status(lead_id_str)
    assert status == {"amocrm": True, "sheets": True, "telegram": True}

