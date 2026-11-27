"""Moliya guruhi kunlik hisobotidan fakt saldo olish testlari."""

from datetime import date
from types import SimpleNamespace

import pytest

from src.services.core.finance import daily_report_ingest as dri
from src.services.core.finance.balance_reconcile import JORIY_FIELD

SAMPLE = (
    "📊 Kunlik moliya — 24.11.2026\n"
    "Kirim P2P — 500 000\n"
    "Chiqim P2P — 120 000\n\n"
    "Kun oxiri pul:\n"
    "P2P — 142 068\n"
    "Naqd UZS — 0\n"
    "Naqd USD — 900$\n"
    "Bank — 4 384 599,9\n\n"
    "Nazorat: Bank ↔ Airtable farqi: 0\n"
)
OWNER = 111
MOLIYACHI = 8611068511


@pytest.fixture(autouse=True)
def _ids(monkeypatch):
    from src.settings import settings

    monkeypatch.setenv("MOLIYACHI_TELEGRAM_ID", str(MOLIYACHI))
    monkeypatch.setattr(settings, "OWNER_ID", OWNER, raising=False)


def test_parse_sample_only_end_of_day_section():
    r = dri.parse_daily_report(SAMPLE)
    assert r.report_date == date(2026, 11, 24)
    assert r.balances == {"P2P": 142_068, "Naqd UZS": 0, "Naqd USD": 900, "Bank": 4_384_599.9}


@pytest.mark.parametrize("raw,val", [
    ("142 068", 142_068), ("4 384 599,9", 4_384_599.9),
    ("900$", 900), ("1 500 000 soʻm", 1_500_000), ("abc", None),
])
def test_parse_amount(raw, val):
    assert dri.parse_amount(raw) == val


def test_mapping_covers_all_lines():
    assert set(dri.parse_daily_report(SAMPLE).balances) <= set(dri.ACCOUNT_MAP)
    assert dri.ACCOUNT_MAP["P2P"][0] == "recNtlN2Sj7LDtkMG"
    assert dri.ACCOUNT_MAP["Naqd USD"][1] == "USD"


def _records(p2p=142_068.0):
    vals = {"recNtlN2Sj7LDtkMG": p2p, "recHVOcCQkisfitiD": 4_384_599.9,
            "recTZ8GgVFBdZGf8s": 0, "recseGjV7hF4L1vl7": 900}
    return [{"id": k, "fields": {JORIY_FIELD: v}} for k, v in vals.items()]


class _Store:
    def __init__(self, p2p=142_068.0):
        self.data: dict = {}
        self.p2p = p2p
        self.owner: list = []

    async def write(self, rid, fields):
        self.data[rid] = fields
        return True

    async def read(self):
        return _records(self.p2p), True

    async def notify(self, text):
        self.owner.append(text)
        return True

    async def run(self, text=SAMPLE, sender=MOLIYACHI, day=date(2026, 11, 25)):
        return await dri.ingest_daily_report(
            text, sender_id=sender, message_date=day,
            write=self.write, read_records=self.read, notify_owner=self.notify,
        )


@pytest.mark.asyncio
async def test_ingest_writes_and_reports_match():
    s = _Store()
    assert await s.run() == "✅ Airtable bilan mos"
    f = s.data["recNtlN2Sj7LDtkMG"]
    assert f["Fakt saldo (hisob valyutasida)"] == 142_068
    assert f["Fakt saldo sanasi"] == "2026-11-24"
    assert f["Fakt saldo manbasi"] == dri.SOURCE_LABEL
    assert s.owner == []


@pytest.mark.asyncio
async def test_ingest_reports_diff_and_notifies_owner():
    s = _Store(p2p=-10_480_000.0)
    reply = await s.run()
    assert reply.startswith("⚠️ P2P: Airtable") and "hisobot 142 068" in reply
    assert len(s.owner) == 1


@pytest.mark.asyncio
async def test_resend_last_wins():
    s = _Store()
    await s.run()
    await s.run(SAMPLE.replace("142 068", "150 000"))
    assert s.data["recNtlN2Sj7LDtkMG"]["Fakt saldo (hisob valyutasida)"] == 150_000


@pytest.mark.asyncio
async def test_unauthorized_sender_ignored():
    s = _Store()
    assert await s.run(sender=999) is None
    assert s.data == {}


@pytest.mark.asyncio
async def test_date_skew_warns_without_writing():
    s = _Store()
    reply = await s.run(day=date(2026, 11, 30))
    assert "Sanani tekshiring" in reply and s.data == {}


@pytest.mark.asyncio
async def test_handler_filters_group_and_replies(monkeypatch):
    from src.handlers import airtable_gap_handler as h
    from src.settings import settings

    monkeypatch.setattr(settings, "HISOBCHI_FINANCE_GROUP_ID", -1003967389019, raising=False)
    msg = SimpleNamespace(chat=SimpleNamespace(id=-1003967389019), text=SAMPLE)
    assert h.is_group_daily_report(msg)
    assert not h.is_group_daily_report(SimpleNamespace(chat=SimpleNamespace(id=-1), text=SAMPLE))


RULE_TEXT = (
    "📌 Qoida: moliyachi har kuni \"📊 Kunlik moliya\" hisobotini guruhga yozadi "
    "(\"Kun oxiri pul\" boʻlimi bilan). Bot qoldiqni Airtable ga yozadi."
)


def test_rule_text_is_not_report():
    assert not dri.is_daily_report(RULE_TEXT)
    assert dri.is_daily_report(SAMPLE)
    assert dri.is_daily_report("  \n" + SAMPLE)


@pytest.mark.asyncio
async def test_rule_text_gets_no_reply():
    s = _Store()
    assert await s.run(RULE_TEXT) is None
    assert s.data == {}


@pytest.mark.asyncio
async def test_header_without_section_warns():
    reply = await _Store().run("📊 Kunlik moliya — 24.11.2026\nKirim: 0")
    assert reply and "Kun oxiri pul" in reply
