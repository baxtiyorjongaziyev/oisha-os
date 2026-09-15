"""Tests for the AmoCRM webhook duplicate-note guard."""
import importlib

import pytest


@pytest.fixture(autouse=True)
def _reset_dedup_state():
    """Each test gets a clean in-memory dedup table."""
    module = importlib.import_module("src.services.core.crm.amocrm_webhook_dedup")
    module._recent_lead_events.clear()
    yield
    module._recent_lead_events.clear()


def test_same_lead_same_status_within_window_is_duplicate():
    from src.services.core.crm.amocrm_webhook_dedup import is_duplicate_lead_event

    assert is_duplicate_lead_event(123, now=1000.0, status_id=142) is False
    assert is_duplicate_lead_event(123, now=1005.0, status_id=142) is True


def test_same_lead_same_status_after_window_is_not_duplicate():
    from src.services.core.crm.amocrm_webhook_dedup import is_duplicate_lead_event

    assert is_duplicate_lead_event(123, now=1000.0, status_id=142) is False
    assert is_duplicate_lead_event(123, now=1031.0, status_id=142) is False


def test_won_transition_after_plain_status_change_is_not_swallowed():
    """A status update followed quickly by a Won transition for the same lead
    must each run their own side effects — the dedup key must include the
    status, not just the lead_id."""
    from src.services.core.crm.amocrm_webhook_dedup import is_duplicate_lead_event

    # Plain status change for lead 123
    assert is_duplicate_lead_event(123, now=1000.0, status_id=100) is False
    # Won transition for the same lead, 2s later — must NOT be treated as a
    # duplicate of the earlier, different status transition.
    assert is_duplicate_lead_event(123, now=1002.0, status_id=142) is False


def test_different_leads_do_not_share_dedup_window():
    from src.services.core.crm.amocrm_webhook_dedup import is_duplicate_lead_event

    assert is_duplicate_lead_event(123, now=1000.0, status_id=142) is False
    assert is_duplicate_lead_event(456, now=1000.0, status_id=142) is False


def test_missing_status_id_uses_no_status_bucket():
    from src.services.core.crm.amocrm_webhook_dedup import is_duplicate_lead_event

    assert is_duplicate_lead_event(123, now=1000.0) is False
    assert is_duplicate_lead_event(123, now=1005.0) is True
