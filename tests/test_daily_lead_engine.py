import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.schedulers.daily_lead_engine_scheduler import (
    _get_last_run_date,
    _set_last_run_date,
    execute_daily_lead_cycle,
)


@pytest.mark.asyncio
async def test_execute_daily_lead_cycle():
    with patch("src.schedulers.daily_lead_engine_scheduler.ColdLeadReactivator") as MockReactivator, \
         patch("src.schedulers.daily_lead_engine_scheduler.TelegramProspectImporter") as MockImporter:

        mock_reactivator_inst = MagicMock()
        mock_reactivator_inst.run_batch.return_value = {
            "created_count": 3,
            "leads": [{"original_id": 1, "new_id": 101, "name": "Test 1"}]
        }
        MockReactivator.return_value = mock_reactivator_inst

        mock_importer_inst = MagicMock()
        mock_importer_inst.import_pending_prospects = AsyncMock(return_value={
            "imported_count": 2,
            "leads": [{"candidate_key": "k1", "new_lead_id": 201, "service": "branding"}]
        })
        MockImporter.return_value = mock_importer_inst

        report = await execute_daily_lead_cycle(cold_batch_size=3, tg_batch_size=2)

        assert report["cold_leads_created"] == 3
        assert report["tg_leads_imported"] == 2
        assert len(report["cold_leads"]) == 1
        assert len(report["tg_leads"]) == 1
