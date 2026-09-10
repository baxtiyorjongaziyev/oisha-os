# tests/test_crm_period_commands.py
import pytest

from src.services.core.crm.daily_report.models import PeriodType, PeriodMetrics, ReportResult
from src.commands import dashboard as dash


class _Event:
    def __init__(self):
        self.responses = []

    async def respond(self, text):
        self.responses.append(text)


class _Rep:
    def __init__(self, *a, **k):
        pass

    async def build(self, ptype):
        m = PeriodMetrics(period_type=ptype,
                          period_start=__import__("datetime").date(2026, 9, 1),
                          period_end=__import__("datetime").date(2026, 9, 30))
        return ReportResult(ptype, m.period_start, m.period_end, m, None, {},
                            f"BODY-{ptype.value}", True)


@pytest.fixture(autouse=True)
def _patch(monkeypatch):
    monkeypatch.setattr(dash, "CRMPeriodReporter", _Rep, raising=False)


@pytest.mark.asyncio
async def test_cmd_report_month(monkeypatch):
    ev = _Event()
    await dash.cmd_report_month(ev, msg_controller=None,
                                get_surgical_integration=lambda: type("S", (), {"amocrm": object()}))
    assert any("BODY-monthly" in r for r in ev.responses)


@pytest.mark.asyncio
async def test_cmd_report_week(monkeypatch):
    ev = _Event()
    await dash.cmd_report_week(ev, msg_controller=None,
                              get_surgical_integration=lambda: type("S", (), {"amocrm": object()}))
    assert any("BODY-weekly" in r for r in ev.responses)
