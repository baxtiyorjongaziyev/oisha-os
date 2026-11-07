import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.schedulers.moliya.soliq import build_soliq_eslatma, run_soliq_eslatma


def test_texts_by_day():
    assert "11101_20" in build_soliq_eslatma(datetime(2026, 12, 1))
    assert "101" in build_soliq_eslatma(datetime(2026, 12, 1))
    assert "10104_36" in build_soliq_eslatma(datetime(2026, 12, 5))
    t = build_soliq_eslatma(datetime(2026, 12, 12))
    assert "11101_20" in t and "10104_36" in t


def test_other_days_none():
    assert build_soliq_eslatma(datetime(2026, 12, 2)) is None


def test_send_once():
    bot = MagicMock()
    bot.send_message = AsyncMock()
    with patch("src.settings.settings") as s, patch("telegram.Bot", return_value=bot), \
            patch.dict("os.environ", {"BOT_TOKEN": "x"}):
        s.OWNER_ID = 1
        assert asyncio.run(run_soliq_eslatma(datetime(2026, 12, 1))) is True
    bot.send_message.assert_awaited_once()


def test_no_owner_false():
    with patch("src.settings.settings") as s, patch.dict("os.environ", {"BOT_TOKEN": "x"}):
        s.OWNER_ID = None
        assert asyncio.run(run_soliq_eslatma(datetime(2026, 12, 1))) is False
