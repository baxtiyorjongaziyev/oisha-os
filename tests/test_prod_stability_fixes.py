"""Regression tests for production stability fixes."""
import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.core.gcontacts import GoogleContactsSync
from src.services.core.instagram import leadgen_delivery, leadgen_watchdog
from src.services.core.leads.lead_operating_system import LeadOperatingSystem
from src.services.core.telegram.aiogram_telethon_compat import _parse_mode
from src.services.core.telegram.bot_runtime import AiogramBotRuntime


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


@pytest.mark.asyncio
async def test_readyz_runs_probes_concurrently(monkeypatch):
    from src.api.routes import amocrm_integration, health
    from src.api.routes.state import api_state
    from src.services.core import agent_runtime

    async def slow_get_connection():
        await asyncio.sleep(0.15)
        return SimpleNamespace(execute=lambda _: None)

    async def slow_userbot():
        await asyncio.sleep(0.15)
        return True

    async def slow_amocrm():
        await asyncio.sleep(0.15)
        return True

    monkeypatch.setattr(
        "src.services.core.instagram.config_guard.check_meta_config",
        lambda: {"configured": True, "missing_keys": []},
    )
    monkeypatch.setattr(api_state, "db_instance", SimpleNamespace(get_connection=slow_get_connection))
    monkeypatch.setattr(api_state, "user_client", SimpleNamespace(is_user_authorized=slow_userbot))
    monkeypatch.setattr(
        amocrm_integration,
        "_get_amocrm_instance",
        lambda: SimpleNamespace(check_connection=slow_amocrm, last_error=None),
    )
    monkeypatch.setattr(
        agent_runtime,
        "get_runtime_context",
        lambda: {"runtime_source": "cloud_run", "scheduler_mode": "persistent"},
    )

    t0 = time.monotonic()
    resp = await health.production_readiness_probe()
    elapsed = time.monotonic() - t0
    assert resp.status_code == 200
    assert elapsed < 0.30, f"expected parallel probes (<0.30s), got {elapsed:.3f}s"


@pytest.mark.asyncio
async def test_aiogram_parse_mode_maps_md_to_markdown():
    bot = SimpleNamespace(send_message=AsyncMock(return_value=SimpleNamespace(message_id=1)))
    runtime = AiogramBotRuntime(bot)
    await runtime.send_message(123, "*hi*", parse_mode="md")
    assert bot.send_message.call_args.kwargs["parse_mode"] == "Markdown"
    assert _parse_mode("md") == "Markdown"
    assert _parse_mode("html") == "HTML"


def test_gsheets_client_metadata_uses_gspread_classes(tmp_path):
    import gspread
    from src.services.core.finance.gsheets.client import GsheetClientMixin

    creds_file = tmp_path / "sa.json"
    creds_file.write_text("{}", encoding="utf-8")
    obj = GsheetClientMixin.__new__(GsheetClientMixin)
    obj.spreadsheet_id = "sheet-123"
    obj.credentials_path = str(creds_file)
    obj.client = None
    obj.spreadsheet = None
    obj._worksheets = {}

    http_client = MagicMock(spec=gspread.http_client.HTTPClient)
    http_client.fetch_sheet_metadata.return_value = {
        "properties": {"title": "TestBook"},
        "sheets": [{"properties": {"title": "Pul oqimi", "sheetId": 0}}],
    }
    fake_client = SimpleNamespace(http_client=http_client)
    with patch("src.services.core.finance.gsheets.client.Credentials") as mock_creds, \
         patch("src.services.core.finance.gsheets.client.gspread.authorize", return_value=fake_client):
        mock_creds.from_service_account_file.return_value = MagicMock()
        obj._authenticate()
    assert obj.spreadsheet is not None
    assert "Pul oqimi" in obj._worksheets


def test_database_pool_resets_idle_hrana_transaction_error():
    from src.database_pool import _is_resettable_connection_error

    err = ValueError(
        'Hrana: `stream error: Error { message: "SQLite error: interactive transaction was rolled back because the stream was idle for too long; retry the transaction", code: "SQLITE_BUSY" }`'
    )
    assert _is_resettable_connection_error(err) is True


def test_gsheets_client_sets_http_timeout(tmp_path):
    import gspread
    from src.services.core.finance.gsheets.client import GsheetClientMixin

    creds_file = tmp_path / "sa.json"
    creds_file.write_text("{}", encoding="utf-8")
    obj = GsheetClientMixin.__new__(GsheetClientMixin)
    obj.spreadsheet_id = "sheet-123"
    obj.credentials_path = str(creds_file)
    obj.client = None
    obj.spreadsheet = None
    obj._worksheets = {}

    http_client = MagicMock(spec=gspread.http_client.HTTPClient)
    http_client.fetch_sheet_metadata.return_value = {"properties": {"title": "Book"}, "sheets": []}
    fake_client = MagicMock()
    fake_client.http_client = http_client
    with patch("src.services.core.finance.gsheets.client.Credentials") as mock_creds, \
         patch("src.services.core.finance.gsheets.client.gspread.authorize", return_value=fake_client):
        mock_creds.from_service_account_file.return_value = MagicMock()
        obj._authenticate()
    fake_client.set_timeout.assert_called_once_with(15)


@pytest.mark.asyncio
async def test_init_core_services_does_not_block_on_slow_gsheets_cache(monkeypatch):
    from src.bootstrap.orchestration import core_services
    from src.api.routes.state import api_state

    slow_done = asyncio.Event()

    class _SlowStore:
        def __init__(self, gs_id, creds):
            self._worksheets = {}

        async def init(self):
            await asyncio.sleep(5.0)
            slow_done.set()

    fake_db = MagicMock()
    fake_db.init_instance = AsyncMock()
    monkeypatch.setattr(core_services, "Database", lambda: fake_db)
    monkeypatch.setattr(core_services, "MessageController", lambda **kw: MagicMock())
    monkeypatch.setattr(core_services.settings, "HISOBCHI_GSHEET_ID", "sheet-123")
    monkeypatch.setattr(core_services.settings, "HISOBCHI_GSHEET_CREDS_FILE", "sa.json")
    monkeypatch.setattr(core_services, "init_core_services", core_services.init_core_services)
    monkeypatch.setattr("src.services.core.hisobchi_gsheets.HisobchiGsheetStore", _SlowStore)

    t0 = time.monotonic()
    _, _, store, _ = await core_services.init_core_services()
    elapsed = time.monotonic() - t0
    assert elapsed < 0.5, f"boot blocked on slow gsheets init: {elapsed:.2f}s"
    assert store is not None
    assert api_state.finance_source is not None
    for task in asyncio.all_tasks():
        if task.get_name() == "hisobchi_gs_cache_warmup":
            task.cancel()
