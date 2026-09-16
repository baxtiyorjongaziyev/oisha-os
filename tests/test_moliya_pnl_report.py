from datetime import datetime

import pytest

from src.schedulers.moliya import pnl


@pytest.mark.asyncio
async def test_build_pnl_report_reads_uppercase_live_formula_fields(monkeypatch):
    async def fake_read_table(table_name: str) -> list[dict]:
        assert table_name == "Oylik P&L"
        return [
            {
                "fields": {
                    "Oy nomi": "2026-08 (Avgust 2026)",
                    "Jami Kirim (UZS)": 10_000_000,
                    "Jami Chiqim (UZS)": 12_500_000,
                    "SOLIQQACHA FOYDA (UZS)": -2_500_000,
                    "Soliq Xarajati (UZS)": 0,
                    "SOLIQDAN KEYINGI SOF FOYDA (UZS)": -2_500_000,
                    "Taqsimlangan Dividendlar (UZS)": 0,
                    "TAQSIMLANMAGAN FOYDA (UZS)": -2_500_000,
                    "Sof foyda marjasi (%)": -0.25,
                }
            }
        ]

    monkeypatch.setattr(pnl, "read_table", fake_read_table)

    report = await pnl.build_pnl_report(datetime(2026, 9, 1, 9, 0))

    assert "Soliqqacha foyda: <b>-2 500 000</b>" in report
    assert "🔴 Sof foyda: <b>-2 500 000</b>" in report
    assert "Sof foyda marjasi: <b>-25.0%</b>" in report
    assert "Taqsimlanmagan foyda: -2 500 000" in report
