"""Airtable boʻsh maydonlarni bittama-bitta soʻrab toʻldirish testlari."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.handlers import airtable_gap_handler as handler
from src.services.core.finance import airtable_gap_filler as gf


class _FakeDb:
    def __init__(self):
        self.state = {}

    async def get_state(self, key, default=None):
        return self.state.get(key, default)

    async def set_state(self, key, value):
        self.state[key] = value


def test_find_next_gap_prioritizes_stale_hisob_then_transactions():
    hisoblar = [
        {"id": "recH1", "fields": {"Faol": True, "Hisob nomi": "Bank UZS", "Valyuta": "UZS", "Fakt saldo sanasi": "2026-10-10"}},
    ]
    txs = [
        {"id": "recT1", "fields": {"Tranzaksiya": "Sharq", "Sana": "2026-11-20", "Turi": "Kirim"}},
    ]
    assert gf.find_next_gap(txs, hisoblar, "2026-11-23").table == "Tranzaksiyalar"
    p1 = gf.find_next_gap(txs, hisoblar, "2026-11-23", ask_fakt_saldo=True)
    assert p1 is not None and p1.table == "Hisoblar" and p1.field == "Fakt saldo"

    p2 = gf.find_next_gap(txs, hisoblar, "2026-11-23", skipped={"recH1:Fakt saldo"}, ask_fakt_saldo=True)
    assert p2 is not None and p2.table == "Tranzaksiyalar" and p2.field == "Hisobot oyi"
    assert p2.quick_value == "2026-11"

    txs[0]["fields"]["Hisobot oyi"] = "2026-11"
    p3 = gf.find_next_gap(txs, hisoblar, "2026-11-23", skipped={"recH1:Fakt saldo"})
    assert p3 is not None and p3.table == "Tranzaksiyalar" and p3.field == "Loyiha"


@pytest.mark.asyncio
async def test_apply_answer_validates_and_patches_airtable(monkeypatch):
    patched = []

    class _Sync:
        def __init__(self, table_name):
            self.table_name = table_name

        def update_project_fields(self, rid, fields):
            patched.append((self.table_name, rid, fields))
            return True

    monkeypatch.setattr("src.services.core.airtable_sync.AirtableSync", _Sync)

    ok, msg = await gf.apply_answer(
        {"table": "Hisoblar", "record_id": "recH1", "title": "Bank UZS", "field": "Fakt saldo"},
        "not-a-number",
        actor_label="@dilbar",
        today_iso="2026-11-23",
    )
    assert ok is False and "Raqam" in msg

    ok2, msg2 = await gf.apply_answer(
        {"table": "Hisoblar", "record_id": "recH1", "title": "Bank UZS", "field": "Fakt saldo"},
        "9 000 000",
        actor_label="@dilbar",
        today_iso="2026-11-23",
    )
    assert ok2 is True and "saqlandi" in msg2
    assert patched == [(
        "Hisoblar",
        "recH1",
        {
            "Fakt saldo (hisob valyutasida)": 9000000.0,
            "Fakt saldo sanasi": "2026-11-23",
            "Fakt saldo manbasi": "Telegram /toldir (@dilbar)",
        },
    )]


@pytest.mark.asyncio
async def test_toldir_command_and_text_reply_flow(monkeypatch):
    db = _FakeDb()
    monkeypatch.setattr(gf, "is_authorized_filler", lambda uid: uid == 150074828)
    monkeypatch.setattr(handler, "is_authorized_filler", lambda uid: uid == 150074828)

    prompts = iter([
        gf.GapPrompt("Hisoblar", "recH1", "Bank UZS", "Fakt saldo", "Saldoni yozing:"),
        None,
    ])
    monkeypatch.setattr(handler, "next_gap_for_user", AsyncMock(side_effect=lambda *_: next(prompts)))
    monkeypatch.setattr(handler, "apply_answer", AsyncMock(return_value=(True, "✅ Saqlandi")))

    answers = []

    class _Msg:
        chat = SimpleNamespace(type="private")
        from_user = SimpleNamespace(id=150074828, username="baxti")
        text = "/toldir"

        async def answer(self, text, **kw):
            answers.append(text)

    await handler.handle_toldir_command(_Msg(), db=db)
    assert answers == ["Saldoni yozing:"]
    assert db.state[f"{gf.SESSION_KEY_PREFIX}150074828"]["record_id"] == "recH1"

    _Msg.text = "9000000"
    await handler.handle_gap_text_reply(_Msg(), db=db)
    assert answers == ["Saldoni yozing:", "✅ Saqlandi", "🎉 Barcha tekshirilgan boʻsh maydonlar toʻldirildi!"]


def test_toldir_is_owner_only(monkeypatch):
    from src.settings import settings

    monkeypatch.setattr(settings, "OWNER_ID", 150074828, raising=False)
    monkeypatch.setenv("MOLIYACHI_TELEGRAM_ID", "8611068511")
    assert gf.is_authorized_filler(150074828) is True
    assert gf.is_authorized_filler(8611068511) is False


def test_collect_errors_reasons_and_lookback():
    txs = [
        {"id": "recA", "fields": {"Tranzaksiya": "900$ kartaga tushirildi", "Sana": "2026-11-24",
                                  "Turi": "Chiqim", "Summa": 900, "Hisob": ["h"], "Nazorat holati": "FAIL"}},
        {"id": "recB", "fields": {"Tranzaksiya": "USD tolov", "Sana": "2026-11-23", "Turi": "Kirim",
                                  "Summa": 5, "Hisob": ["h"], "Valyuta": "USD", "Nazorat holati": "FAIL"}},
        {"id": "recC", "fields": {"Tranzaksiya": "Transfer", "Sana": "2026-11-25", "Turi": "Transfer",
                                  "Hisob": ["h"], "P&L — Hisob nazorati": "XATO: moliya maydoni"}},
        {"id": "recOld", "fields": {"Tranzaksiya": "Eski", "Sana": "2026-08-01", "Nazorat holati": "FAIL"}},
        {"id": "recOk", "fields": {"Tranzaksiya": "OK", "Sana": "2026-11-25", "Nazorat holati": "OK"}},
    ]
    errs = {e.record_id: e.detail for e in gf.collect_errors(txs, "2026-11-25")}
    assert set(errs) == {"recA", "recB", "recC"}
    assert "Transfer" in errs["recA"]
    assert "kurssiz" in errs["recB"]
    assert "Summa" in errs["recC"] and "qabul" in errs["recC"]


@pytest.mark.asyncio
async def test_group_digest_sends_once_and_skips_hisoblar(monkeypatch):
    from datetime import datetime

    txs = [
        {"id": "recT1", "fields": {"Tranzaksiya": "Sharq", "Sana": "2026-11-20", "Turi": "Kirim"}},
        {"id": "recT2", "fields": {"Tranzaksiya": "Done", "Sana": "2026-11-20", "Turi": "Chiqim",
                                   "Hisobot oyi": "2026-11"}},
    ]
    claimed: set = set()
    sent: list = []

    async def read():
        return txs, True

    async def send_group(text):
        sent.append(text)
        return True

    async def claim(key, day):
        if (key, day) in claimed:
            return False
        claimed.add((key, day))
        return True

    async def release(key, day):
        claimed.discard((key, day))

    now = datetime(2026, 11, 25, 10, 0)
    kw = dict(read_records=read, send_group=send_group, claim=claim, release=release)
    assert await gf.run_daily_group_digest(now, **kw) is True
    assert len(sent) == 1
    assert "Toʻldirilishi kerak" in sent[0] and "Hisobot oyi" in sent[0] and "Loyiha" in sent[0]
    assert "https://airtable.com/" in sent[0] and "recT1" in sent[0] and "recT2" not in sent[0]
    assert "Fakt saldo" not in sent[0]

    assert await gf.run_daily_group_digest(now, **kw) is True
    assert len(sent) == 1  # takror yuborilmaydi

    assert await gf.run_daily_group_digest(datetime(2026, 11, 25, 23, 30), **kw) is False


@pytest.mark.asyncio
async def test_group_digest_releases_claims_on_send_failure():
    from datetime import datetime

    claimed: set = set()

    async def read():
        return [{"id": "recT1", "fields": {"Tranzaksiya": "X", "Sana": "2026-11-20"}}], True

    async def send_group(text):
        return False

    async def claim(key, day):
        claimed.add(key)
        return True

    async def release(key, day):
        claimed.discard(key)

    ok = await gf.run_daily_group_digest(
        datetime(2026, 11, 25, 10, 0), read_records=read, send_group=send_group, claim=claim, release=release
    )
    assert ok is False and not claimed
