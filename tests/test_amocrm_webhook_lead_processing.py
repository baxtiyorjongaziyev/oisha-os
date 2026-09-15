"""AmoCRM webhook lid ishlov berish testlari.

NIMA UCHUN: `_process_amocrm_event` oxirida
`agent.process_new_lead(lead_id=..., lead_data=...)` chaqirilardi, lekin
`AutonomousSalesAgent` (src/agents/closer/agent.py) da bunday metod YO'Q edi
(faqat process_task/handle_incoming/generate_response/assess_lead/
follow_up_stale_leads bor). Har bir webhook chaqiruvi AttributeError
tashlardi, u atrofdagi `except Exception` ichida indistinguishable tarzda
yutilardi — production'da butunlay ko'rinmas xato edi. Lid lifecycle allaqachon
Vilgood pipeline enforcement + Sanity publisher (status/Won) + enrichment +
call analysis orqali to'liq qoplangan, shuning uchun o'lik chaqiruv olib
tashlandi. Quyidagi test bu xato qaytmasligini ta'minlaydi.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.routes.amocrm_integration import _process_amocrm_event


@pytest.mark.asyncio
async def test_webhook_lead_event_does_not_raise_or_log_unhandled_exception():
    data = {"leads[update][0][id]": "555"}

    amocrm = MagicMock()
    amocrm.get_lead = AsyncMock(return_value={"id": 555, "name": "Test lead"})
    amocrm.get_lead_phone = MagicMock(return_value="+998900000000")

    db = MagicMock()

    with patch(
        "src.api.routes.amocrm_integration._get_amocrm_instance", return_value=amocrm
    ), patch(
        "src.api.routes.amocrm_integration._get_db_instance", AsyncMock(return_value=db)
    ), patch(
        "src.services.core.crm.amocrm_webhook_dedup.is_duplicate_lead_event",
        return_value=False,
    ), patch(
        "src.settings.settings.ENABLE_AMOCRM_LEAD_ENRICHMENT", False
    ), patch(
        "src.settings.settings.ENABLE_AMOCRM_CALL_ANALYSIS", False
    ), patch(
        "src.api.routes.amocrm_integration.logger"
    ) as mock_logger:
        from src.api.routes.state import api_state

        api_state.db_instance = db
        api_state.amocrm_instance = amocrm

        await _process_amocrm_event(data)

    error_calls = [c for c in mock_logger.error.call_args_list]
    assert not error_calls, f"_process_amocrm_event logged unexpected errors: {error_calls}"


@pytest.mark.asyncio
async def test_webhook_no_longer_calls_nonexistent_agent_method():
    """process_new_lead chaqiruvi olib tashlangan — AutonomousSalesAgent bu yerda import qilinmaydi."""
    import src.api.routes.amocrm_integration as mod
    import inspect

    source = inspect.getsource(mod._process_amocrm_event)
    assert "process_new_lead" not in source
    assert "AutonomousSalesAgent" not in source
