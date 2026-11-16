"""Regression tests for production stability fixes."""
from unittest.mock import MagicMock, patch

import pytest

from src.services.core.gcontacts import GoogleContactsSync
from src.services.core.instagram import leadgen_delivery, leadgen_watchdog
from src.services.core.leads.lead_operating_system import LeadOperatingSystem


def test_lead_os_parse_dt_normalizes_naive_and_aware():
    naive = LeadOperatingSystem._parse_dt("2026-11-16T13:11:54.078608")
    aware = LeadOperatingSystem._parse_dt("2026-10-11T09:53:00.866690+05:00")
    assert naive is not None and naive.tzinfo is not None
    assert aware is not None and aware.tzinfo is not None
    assert aware < naive


def test_gcontacts_falls_back_to_data_service_account(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    sa = tmp_path / "data" / "service_account.json"
    sa.write_text("{}", encoding="utf-8")

    with patch("src.services.core.gcontacts.load_user_credentials", return_value=None), \
         patch("src.services.core.gcontacts.ServiceAccountCredentials") as sa_cls, \
         patch("src.services.core.gcontacts.build", return_value=MagicMock()):
        sa_cls.from_service_account_file.return_value = MagicMock()
        gc = GoogleContactsSync()
    assert gc.service is not None
    sa_cls.from_service_account_file.assert_called_once()


@pytest.mark.asyncio
async def test_watchdog_skips_synthetic_test_rows(tmp_path, monkeypatch):
    monkeypatch.setattr(leadgen_delivery, "_DB_PATH", tmp_path / "leadgen_delivery.db")
    leadgen_watchdog._SKIPPED_DEST_WARNED.clear()
    leadgen_delivery.record_delivery_status(
        leadgen_id="test_in_flight_1234",
        lead_id=101,
        amocrm_ok=True,
        sheets_ok=False,
        telegram_ok=False,
        destination="",
    )
    recovered = await leadgen_watchdog.retry_pending_leadgen_deliveries()
    assert recovered == 0
    assert "test_in_flight_1234" not in leadgen_watchdog._SKIPPED_DEST_WARNED
