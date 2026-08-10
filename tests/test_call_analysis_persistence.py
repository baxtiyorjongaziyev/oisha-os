"""Qo'ng'iroq tahlili bazaga BALLAR bilan yozilishini kafolatlaydigan testlar.

REGRESSIYA TARIXI:
    `CallAnalyzer` har bir qo'ng'iroqni to'liq rubrik bo'yicha baholardi,
    natijani AmoCRM notasiga yozardi — lekin bazaga faqat matnli ustunlar
    tushardi. `sales_quality_coach` esa aynan `overall_score`,
    `manager_name`, `strengths`, `weaknesses`, `outcome`,
    `duration_seconds` ustunlarini o'qiydi. Natijada murabbiylik qatlami
    bo'sh ma'lumot ustida ishlardi va sotuvchi konversiyasiga ta'sir qila
    olmasdi.

    Quyidagi testlar shu uzilish qaytib kelmasligini ta'minlaydi.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.core.call_analyzer import CallAnalyzer
from src.services.core.sales_playbook import (
    OUTCOME_MEETING,
    OUTCOME_THINKING,
    OUTCOME_UNKNOWN,
)

# Murabbiylik qatlami (`sales_quality_coach`) o'qiydigan ustunlar. Bu
# ro'yxat qisqarmasligi kerak.
COACH_REQUIRED_COLUMNS = {
    "manager_name",
    "overall_score",
    "strengths",
    "weaknesses",
    "outcome",
    "duration_seconds",
}


class _RecordingConn:
    """Bajarilgan SQL va parametrlarni yig'ib boradigan soxta ulanish."""

    def __init__(self):
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

        async def _result():
            cursor = MagicMock()
            cursor.fetchall = AsyncMock(return_value=[])
            cursor.fetchone = AsyncMock(return_value=None)
            return cursor

        return _result()

    async def commit(self):
        return None

    def insert_row(self):
        """`INSERT ... INTO call_analyses` ni ustun→qiymat lug'ati qilib beradi."""
        for sql, params in self.calls:
            if "INTO call_analyses" not in sql:
                continue
            columns = sql.split("(", 1)[1].split(")", 1)[0]
            names = [c.strip() for c in columns.replace("\n", " ").split(",")]
            return dict(zip(names, params))
        return {}


def _analyzer(conn):
    db = MagicMock()
    db.get_connection = AsyncMock(return_value=conn)
    return CallAnalyzer(amocrm=MagicMock(), voice_processor=MagicMock(), db=db)


def _analysis(**overrides):
    base = {
        "sifat_bahosi": 78,
        "lead_bahosi": 64,
        "natija": OUTCOME_MEETING,
        "kuchli_tomonlar": ["Ehtiyojni yaxshi ochdi"],
        "zaif_tomonlar": ["Keyingi qadam muddati aytilmadi"],
        "etirozlar": ["qimmat"],
        "rubrik_baholar": {
            "salomlashish": 80,
            "ehtiyojlar": 85,
            "qiymat": 75,
            "etirozlar": 70,
            "yakunlash": 80,
            "muloqot_sifati": 75,
        },
    }
    base.update(overrides)
    return base


async def _log(conn, **overrides):
    kwargs = {
        "call_id": "call-1",
        "lead_id": 42,
        "category": "Mijoz",
        "summary": "Mijoz brending bo'yicha qiziqdi",
        "client_mood": "Ijobiy",
        "next_steps": "Seshanba uchrashuv",
        "transcript": "…",
        "audio_url": "https://example.invalid/a.mp3",
        "caller_phone": "+998901234567",
        "task_id": "task-9",
        "analysis": _analysis(),
        "duration_seconds": 245,
        "manager_id": 77,
        "manager_name": "Aziz Karimov",
    }
    kwargs.update(overrides)
    await _analyzer(conn)._log_call_analysis(**kwargs)
    return conn.insert_row()


@pytest.mark.asyncio
async def test_insert_covers_every_column_the_coach_reads():
    conn = _RecordingConn()
    row = await _log(conn)

    missing = COACH_REQUIRED_COLUMNS - set(row)
    assert not missing, f"Murabbiy o'qiydigan ustunlar yozilmadi: {sorted(missing)}"


@pytest.mark.asyncio
async def test_rubric_score_reaches_the_database():
    conn = _RecordingConn()
    row = await _log(conn)

    assert row["overall_score"] == 78
    assert row["client_interest_level"] == 64
    assert json.loads(row["scores"])["ehtiyojlar"] == 85


@pytest.mark.asyncio
async def test_manager_and_duration_are_persisted():
    """Menejer ismisiz qo'ng'iroqni hech kimga bog'lab bo'lmaydi."""
    conn = _RecordingConn()
    row = await _log(conn)

    assert row["manager_name"] == "Aziz Karimov"
    assert row["manager_id"] == 77
    assert row["duration_seconds"] == 245


@pytest.mark.asyncio
async def test_coaching_lists_are_stored_as_json():
    conn = _RecordingConn()
    row = await _log(conn)

    assert json.loads(row["strengths"]) == ["Ehtiyojni yaxshi ochdi"]
    assert json.loads(row["weaknesses"]) == ["Keyingi qadam muddati aytilmadi"]
    assert json.loads(row["objections"]) == ["qimmat"]


@pytest.mark.asyncio
async def test_converting_outcome_marked_as_conversion():
    conn = _RecordingConn()
    row = await _log(conn)

    assert row["outcome"] == OUTCOME_MEETING
    assert row["converted"] == 1


@pytest.mark.asyncio
async def test_non_converting_outcome_not_marked():
    conn = _RecordingConn()
    row = await _log(conn, analysis=_analysis(natija=OUTCOME_THINKING))

    assert row["outcome"] == OUTCOME_THINKING
    assert row["converted"] == 0


@pytest.mark.asyncio
async def test_missing_analysis_degrades_to_safe_defaults():
    """Tahlil bo'lmasa ham yozuv yiqilmasligi kerak — eski chaqiruvlar
    `analysis` bermasligi mumkin."""
    conn = _RecordingConn()
    row = await _log(conn, analysis=None, duration_seconds=0, manager_name="")

    assert row["overall_score"] == 0
    assert row["outcome"] == OUTCOME_UNKNOWN
    assert row["converted"] == 0


@pytest.mark.asyncio
async def test_schema_is_ensured_before_insert():
    """Migratsiya yozuvdan OLDIN yugurishi kerak, aks holda yangi
    ustunlarga yozib bo'lmaydi."""
    from src.services.core.call_analyses_schema import reset_schema_cache

    reset_schema_cache()
    conn = _RecordingConn()
    await _log(conn)

    statements = [sql for sql, _ in conn.calls]
    create_idx = next(
        i for i, sql in enumerate(statements) if "CREATE TABLE" in sql
    )
    insert_idx = next(
        i for i, sql in enumerate(statements) if "INTO call_analyses" in sql
    )
    assert create_idx < insert_idx


@pytest.mark.asyncio
async def test_db_failure_does_not_break_the_call_pipeline():
    """Baza yiqilsa ham qo'ng'iroq tahlili to'xtamasligi kerak."""
    db = MagicMock()
    db.get_connection = AsyncMock(side_effect=RuntimeError("db down"))
    analyzer = CallAnalyzer(amocrm=MagicMock(), voice_processor=MagicMock(), db=db)

    await analyzer._log_call_analysis(
        call_id="c",
        lead_id=1,
        category="Mijoz",
        summary="s",
        client_mood="Ijobiy",
        next_steps="n",
        transcript="t",
        audio_url="u",
        analysis=_analysis(),
    )  # exception ko'tarmasligi kerak


# ── Menejer ismini aniqlash ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_manager_name_resolved_from_amocrm():
    amocrm = MagicMock()
    amocrm.get_user_name = MagicMock(return_value="Dilnoza Rasulova")
    analyzer = CallAnalyzer(amocrm=amocrm, voice_processor=MagicMock(), db=MagicMock())

    assert await analyzer._resolve_manager_name(55) == "Dilnoza Rasulova"


@pytest.mark.asyncio
async def test_manager_name_empty_without_responsible_user():
    analyzer = CallAnalyzer(
        amocrm=MagicMock(), voice_processor=MagicMock(), db=MagicMock()
    )

    assert await analyzer._resolve_manager_name(None) == ""


@pytest.mark.asyncio
async def test_manager_name_survives_amocrm_error():
    amocrm = MagicMock()
    amocrm.get_user_name = MagicMock(side_effect=RuntimeError("amocrm down"))
    analyzer = CallAnalyzer(amocrm=amocrm, voice_processor=MagicMock(), db=MagicMock())

    assert await analyzer._resolve_manager_name(55) == ""
