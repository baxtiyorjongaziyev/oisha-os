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
    p1 = gf.find_next_gap(txs, hisoblar, "2026-11-23")
    assert p1 is not None and p1.table == "Hisoblar" and p1.field == "Fakt saldo"

    p2 = gf.find_next_gap(txs, hisoblar, "2026-11-23", skipped={"recH1:Fakt saldo"})
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
