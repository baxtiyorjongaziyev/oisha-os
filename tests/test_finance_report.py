import os

import pytest


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_TESTS") != "1",
    reason="Live finance report reads real CRM/Airtable data; set RUN_LIVE_TESTS=1 to run intentionally.",
)


async def test_finance_report_live():
    from src.database import Database
    from src.services.core.crm_service import CRMService
    from src.services.core.enterprise_reporter import EnterpriseReporter
    from src.services.core.airtable_sync import AirtableSync

    reporter = EnterpriseReporter(Database(), CRMService(), AirtableSync())
    report = await reporter.get_team_efficiency_report()

    assert isinstance(report, str)
    assert report.strip()
