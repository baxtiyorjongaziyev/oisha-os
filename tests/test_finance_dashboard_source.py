import asyncio
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from src.api.routes.finance_dashboard import finance_dashboard, finance_transactions
from src.api.routes.state import api_state


def test_finance_dashboard_fails_closed_when_real_source_is_not_configured():
    with patch.object(api_state, "db_instance", None):
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(finance_dashboard())

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == {
        "code": "finance_source_not_configured",
        "message": "Real finance data source is not configured",
    }


def test_finance_transactions_do_not_return_sample_records():
    with patch.object(api_state, "db_instance", None):
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(finance_transactions())

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["code"] == "finance_source_not_configured"
