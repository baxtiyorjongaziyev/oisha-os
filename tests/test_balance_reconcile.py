"""Kunlik qoldiq rekonsiliatsiyasi testlari."""

from datetime import date, datetime

import pytest

from src.services.core.finance import balance_reconcile as br

TODAY = "2026-11-25"
NOW = datetime(2026, 11, 25, 12, 0)


@pytest.fixture(autouse=True)
def _topic_set(monkeypatch):
    monkeypatch.setattr(br, "_balance_topic_set", lambda: True)


def _hisob(rid, nom, joriy, fakt, sana=TODAY, valyuta="UZS", faol=True):
    return {"id": rid, "fields": {
        "Hisob nomi": nom, "Valyuta": valyuta, "Faol": faol,
        br.JORIY_FIELD: joriy, br.FAKT_FIELD: fakt, br.FAKT_DATE_FIELD: sana,
    }}


def test_mismatch_detects_p2p_case():
    recs = [_hisob("recP2P", "P2P karta", -10_480_000, 142_068)]
    ms = br.find_mismatches(recs, TODAY)
    assert len(ms) == 1
    assert ms[0].farq == pytest.approx(10_622_068)
    text = br.format_mismatch(ms[0])
    assert "P2P karta" in text and "Transfer" in text


def test_threshold_uzs_and_usd():
    recs = [
        _hisob("r1", "A", 100_000, 110_000),          # 10 000 — chegarada, jim
        _hisob("r2", "B", 100_000, 110_001),          # oshdi
        _hisob("r3", "C", 500, 501, valyuta="USD"),    # 1$ — jim
        _hisob("r4", "D", 500, 501.5, valyuta="USD"),  # oshdi
    ]
    assert {m.record_id for m in br.find_mismatches(recs, TODAY)} == {"r2", "r4"}


def test_mismatch_ignores_old_fakt_inactive_and_missing():
    recs = [
        _hisob("r1", "Eski", 0, 50_000, sana="2026-11-24"),
        _hisob("r2", "Nofaol", 0, 50_000, faol=False),
        _hisob("r3", "Boʻsh", None, 50_000),
    ]
    assert br.find_mismatches(recs, TODAY) == []


def test_find_stale():
    recs = [
        _hisob("r1", "Yangi", 0, 0, sana="2026-11-23"),   # 2 kun — hali emas
        _hisob("r2", "Eski", 0, 0, sana="2026-11-22"),    # 3 kun
        _hisob("r3", "Hech", 0, 0, sana=""),
        _hisob("r4", "Nofaol", 0, 0, sana="2026-01-01", faol=False),
    ]
    assert [s.record_id for s in br.find_stale(recs, date(2026, 11, 25))] == ["r2", "r3"]


class _Harness:
    def __init__(self, records, ok=True, send_ok=True):
        self.records, self.ok, self.send_ok = records, ok, send_ok
        self.claims: set = set()
        self.group: list = []
        self.owner: list = []

    async def read(self):
        return self.records, self.ok

    async def send_group(self, text):
        self.group.append(text)
        return self.send_ok

    async def send_owner(self, text):
        self.owner.append(text)
        return self.send_ok

    async def claim(self, job, key):
        if (job, key) in self.claims:
            return False
        self.claims.add((job, key))
        return True

    async def release(self, job, key):
        self.claims.discard((job, key))

    async def run(self, now=NOW):
        return await br.run_balance_reconcile(
            now, read_records=self.read, send_group=self.send_group,
            send_owner=self.send_owner, claim=self.claim, release=self.release,
        )


@pytest.mark.asyncio
async def test_run_is_idempotent_per_day():
    h = _Harness([_hisob("recP2P", "P2P karta", -10_480_000, 142_068),
                  _hisob("recOK", "Kassa", 1_000, 1_000)])
    assert await h.run() == 2
    assert len(h.group) == 1 and len(h.owner) == 1
    assert await h.run() == 0  # takror — jim (DB claim restartdan keyin ham saqlanadi)
    assert len(h.group) == 1


@pytest.mark.asyncio
async def test_silent_when_no_diff():
    h = _Harness([_hisob("recOK", "Kassa", 1_000, 1_000)])
    assert await h.run() == 0
    assert h.group == [] and h.owner == []


@pytest.mark.asyncio
async def test_quiet_hours_sends_nothing():
    h = _Harness([_hisob("recP2P", "P2P karta", 0, 500_000)])
    assert await h.run(datetime(2026, 11, 25, 23, 30)) == 0
    assert await h.run(datetime(2026, 11, 25, 6, 30)) == 0
    assert h.group == [] and h.claims == set()


@pytest.mark.asyncio
async def test_failed_send_releases_claim():
    h = _Harness([_hisob("recP2P", "P2P karta", 0, 500_000)], send_ok=False)
    assert await h.run() == 0
    assert h.claims == set()


@pytest.mark.asyncio
async def test_stale_reminder_once_per_day():
    h = _Harness([_hisob("r2", "Bank", 0, 0, sana="2026-11-20")])
    assert await h.run() == 1
    assert "yangilanmagan" in h.group[0]
    assert await h.run(datetime(2026, 11, 25, 18, 0)) == 0  # shu kuni takrorlanmaydi


@pytest.mark.asyncio
async def test_no_stale_reminder_when_report_recent():
    h = _Harness([
        _hisob("r1", "Bank UZS", 0, 0, sana="2026-10-10"),
        _hisob("r2", "P2P karta", 0, 0, sana="2026-11-24"),
    ])
    assert await h.run() == 0
    assert h.group == []


@pytest.mark.asyncio
async def test_no_stale_reminder_without_balance_topic(monkeypatch):
    monkeypatch.setattr(br, "_balance_topic_set", lambda: False)
    h = _Harness([_hisob("r1", "Bank UZS", 0, 0, sana="2026-10-10")])
    assert await h.run() == 0
    assert h.group == []


def test_missing_faol_checkbox_means_inactive():
    rec = _hisob("r1", "X", 0, 50_000)
    del rec["fields"]["Faol"]
    assert br.find_mismatches([rec], TODAY) == []
    assert br.find_stale([rec], date(2026, 11, 25)) == []


@pytest.mark.asyncio
async def test_partial_delivery_retries_only_failed_destination():
    h = _Harness([_hisob("recP2P", "P2P karta", 0, 500_000)])

    async def owner_fail(text):
        h.owner.append(text)
        return False

    original = h.send_owner
    h.send_owner = owner_fail
    assert await h.run() == 1
    h.send_owner = original
    assert await h.run() == 1
    assert len(h.group) == 1 and len(h.owner) == 2


def test_reconcile_slot_tolerates_drift():
    from src.schedulers.moliya.loop import reconcile_slot

    assert reconcile_slot(datetime(2026, 11, 25, 22, 31)) == "2026-11-25 22:30"
    assert reconcile_slot(datetime(2026, 11, 25, 22, 4)) == "2026-11-25 22:00"
    assert reconcile_slot(datetime(2026, 11, 25, 22, 10)) is None


@pytest.mark.asyncio
async def test_stale_accounts_grouped_into_one_message():
    h = _Harness([
        _hisob("r1", "Bank UZS", 0, 0, sana="2026-10-10"),
        _hisob("r2", "P2P karta", 0, 0, sana="2026-10-10"),
        _hisob("r3", "Naqd USD", 0, 0, sana="2026-10-11"),
    ])
    assert await h.run() == 1
    assert len(h.group) == 1
    msg = h.group[0]
    assert "Bank UZS" in msg and "P2P karta" in msg and "Naqd USD" in msg
    assert "46 kun oldin" in msg
    assert await h.run() == 0


@pytest.mark.asyncio
async def test_stale_send_failure_releases_all_claims():
    h = _Harness([
        _hisob("r1", "A", 0, 0, sana="2026-10-10"),
        _hisob("r2", "B", 0, 0, sana="2026-10-10"),
    ], send_ok=False)
    assert await h.run() == 0
    assert not any(c[0] == br.STALE_DIGEST_JOB for c in h.claims)
