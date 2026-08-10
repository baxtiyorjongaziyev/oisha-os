"""Javobsiz qo'ng'iroqlar va qo'ng'iroq hajmi testlari.

KO'R NUQTA: `if not audio_url: continue` sababli javobsiz qo'ng'iroq
bazaga umuman tushmasdi. Natijada teskari rag'bat paydo bo'lgan edi —
telefon ko'tarmaydigan sotuvchi statistikada eng yaxshi ko'rinardi.
Quyidagi testlar shu holat qaytmasligini ta'minlaydi.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.core.call_analyzer import CallAnalyzer
from src.services.core.call_events import (
    CallEventLog,
    CallVolume,
    aggregate_volume,
    format_duration,
    is_answered,
    team_volume,
)


def event(manager="Aziz", duration=180, answered=None, analyzed=0):
    return {
        "manager_name": manager,
        "duration_seconds": duration,
        "answered": (1 if duration > 0 else 0) if answered is None else answered,
        "analyzed": analyzed,
        "has_recording": 1 if duration > 0 else 0,
    }


# ── Javob berilganini aniqlash ───────────────────────────────────────────


@pytest.mark.parametrize(
    "duration,expected",
    [(0, False), (1, True), (272, True), (None, False), ("", False), ("45", True)],
)
def test_answered_is_decided_by_talk_time(duration, expected):
    """Yozuv borligi mezon emas — yozuv o'chirilgan bo'lishi mumkin."""
    assert is_answered(duration) is expected


def test_format_duration():
    assert format_duration(272) == "04:32"
    assert format_duration(0) == "00:00"


# ── Panel ko'rsatkichlari ────────────────────────────────────────────────


def test_team_panel_matches_the_advert_shape():
    rows = [event(duration=272) for _ in range(98)] + [
        event(duration=0) for _ in range(30)
    ]

    team = team_volume(rows)

    assert team.total == 128
    assert team.answered == 98
    assert team.missed == 30
    assert team.avg_duration_label == "04:32"


def test_avg_duration_excludes_missed_calls():
    """Javobsizlarni (0s) o'rtachaga qo'shsak, ko'rsatkich buziladi."""
    rows = [event(duration=300), event(duration=0), event(duration=0)]

    assert team_volume(rows).avg_duration_seconds == 300


def test_answer_rate_per_seller():
    rows = (
        [event(manager="Aziz", duration=200) for _ in range(9)]
        + [event(manager="Aziz", duration=0)]
        + [event(manager="Bek", duration=200) for _ in range(3)]
        + [event(manager="Bek", duration=0) for _ in range(7)]
    )

    volumes = aggregate_volume(rows)

    assert volumes["Aziz"].answer_rate == pytest.approx(90.0)
    assert volumes["Bek"].answer_rate == pytest.approx(30.0)


def test_seller_who_never_answers_is_visible():
    """Eski tizimda bu odam UMUMAN ko'rinmasdi."""
    rows = [event(manager="Bek", duration=0) for _ in range(20)]

    volume = aggregate_volume(rows)["Bek"]

    assert volume.total == 20
    assert volume.answered == 0
    assert volume.missed == 20
    assert volume.answer_rate == 0.0
    assert volume.avg_duration_seconds == 0.0  # nolga bo'linish yo'q


def test_rows_without_manager_skipped_per_seller_but_counted_for_team():
    rows = [event(manager=""), event(manager="Aziz")]

    assert "" not in aggregate_volume(rows)
    assert team_volume(rows).total == 2


def test_empty_input_is_safe():
    assert team_volume([]).total == 0
    assert team_volume([]).answer_rate == 0.0
    assert aggregate_volume([]) == {}
    assert CallVolume().avg_duration_label == "00:00"


# ── Yozish ───────────────────────────────────────────────────────────────


class _Conn:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

        async def _r():
            cur = MagicMock()
            cur.fetchall = AsyncMock(return_value=[])
            return cur

        return _r()

    async def commit(self):
        return None

    def inserts(self):
        return [
            params
            for sql, params in self.calls
            if "INSERT OR IGNORE INTO call_events" in sql
        ]


def _db(conn):
    db = MagicMock()
    db.get_connection = AsyncMock(return_value=conn)
    return db


@pytest.mark.asyncio
async def test_missed_call_recorded_as_unanswered():
    conn = _Conn()

    await CallEventLog(_db(conn)).record(
        call_id="c1", lead_id=7, duration_seconds=0, has_recording=False,
        manager_name="Aziz",
    )

    params = conn.inserts()[0]
    assert params[0] == "c1"
    assert params[7] == 0   # answered
    assert params[8] == 0   # has_recording


@pytest.mark.asyncio
async def test_answered_call_recorded_with_duration():
    conn = _Conn()

    await CallEventLog(_db(conn)).record(
        call_id="c2", lead_id=7, duration_seconds=272, has_recording=True,
        manager_name="Aziz",
    )

    params = conn.inserts()[0]
    assert params[6] == 272  # duration
    assert params[7] == 1    # answered


@pytest.mark.asyncio
async def test_record_is_noop_without_db_or_id():
    assert await CallEventLog(None).record(
        call_id="c", lead_id=1, duration_seconds=0, has_recording=False
    ) is False
    assert await CallEventLog(_db(_Conn())).record(
        call_id="", lead_id=1, duration_seconds=0, has_recording=False
    ) is False


@pytest.mark.asyncio
async def test_db_failure_does_not_raise():
    db = MagicMock()
    db.get_connection = AsyncMock(side_effect=RuntimeError("db down"))

    assert await CallEventLog(db).record(
        call_id="c", lead_id=1, duration_seconds=0, has_recording=False
    ) is False


# ── Analizatorga ulanish (eng muhim regressiya testi) ────────────────────


def _analyzer_with(notes, conn):
    amocrm = MagicMock()
    amocrm.get_lead_notes = AsyncMock(return_value=notes)
    amocrm.get_user_name = MagicMock(return_value="Aziz Karimov")
    db = _db(conn)
    return CallAnalyzer(
        amocrm=amocrm, voice_processor=MagicMock(), db=db, gemini_client=None
    )


@pytest.mark.asyncio
async def test_call_without_recording_still_reaches_the_log():
    """ENG MUHIM: yozuvsiz qo'ng'iroq endi tashlanmaydi, qayd etiladi."""
    notes = [{
        "id": 9001,
        "note_type": "call_in",
        "params": {"uniq": "missed-1", "duration": 0, "phone": "+998901112233"},
    }]
    conn = _Conn()

    processed = await _analyzer_with(notes, conn).process_call_recordings_for_lead(
        lead_id=42, responsible_user_id=5
    )

    assert processed == 0  # tahlil qilinmadi — yozuv yo'q
    params = conn.inserts()[0]
    assert params[0] == "missed-1"
    assert params[7] == 0            # answered = 0
    assert params[3] == "Aziz Karimov"  # menejerga bog'landi


@pytest.mark.asyncio
async def test_dry_run_does_not_write_events():
    notes = [{"id": 9002, "note_type": "call_in",
              "params": {"uniq": "missed-2", "duration": 0}}]
    conn = _Conn()

    await _analyzer_with(notes, conn).process_call_recordings_for_lead(
        lead_id=42, write=False
    )

    assert conn.inserts() == []
