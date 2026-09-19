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


def test_delivery_summary():
    summary = get_delivery_summary(hours=24)
    assert "total" in summary
    assert "amocrm_ok" in summary
    assert "sheets_ok" in summary
    assert "telegram_ok" in summary
    assert "pending" in summary
