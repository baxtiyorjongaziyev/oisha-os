"""Ikki xil DB fasadi ustida bir xil natija.

`src.db.Database` da `execute()` YO'Q, `DatabasePool` da BOR. Ilgari kod
faqat ikkinchisini nazarda tutgan va production'da `AttributeError` bergan,
u esa `except` ichida yutilib "ma'lumot yo'q" ga aylangan.
"""

import pytest

from src.services.utils.db_rows import execute_write, fetch_rows

SQL = "SELECT manager_name, overall_score FROM call_analyses WHERE created_at LIKE ?"
PARAMS = ["2026-07-21%"]


class PoolLike:
    """`DatabasePool` — execute() bor, dict qaytaradi."""

    def __init__(self):
        self.calls = []

    async def execute(self, sql, params):
        self.calls.append((sql, params))
        return [{"manager_name": "Sardor", "overall_score": 90}]


class CursorLike:
    description = (("manager_name",), ("overall_score",))

    def __init__(self, rows):
        self._rows = rows

    async def fetchall(self):
        return self._rows


class ConnLike:
    def __init__(self, rows):
        self._rows = rows
        self.committed = False
        self.executed = []

    async def execute(self, sql, params):
        self.executed.append((sql, params))
        return CursorLike(self._rows)

    async def commit(self):
        self.committed = True


class DatabaseLike:
    """`src.db.Database` — execute() YO'Q, faqat get_connection()."""

    def __init__(self, rows):
        self.conn = ConnLike(rows)

    async def get_connection(self):
        return self.conn


@pytest.mark.asyncio
async def test_pool_facade_returns_dicts():
    rows = await fetch_rows(PoolLike(), SQL, PARAMS)

    assert rows == [{"manager_name": "Sardor", "overall_score": 90}]


@pytest.mark.asyncio
async def test_database_facade_maps_tuples_via_cursor_description():
    """Bu yo'l ilgari umuman ishlamasdi."""
    db = DatabaseLike([("Sardor", 90), ("Aziz", 40)])

    rows = await fetch_rows(db, SQL, PARAMS)

    assert rows == [
        {"manager_name": "Sardor", "overall_score": 90},
        {"manager_name": "Aziz", "overall_score": 40},
    ]
    assert db.conn.executed == [(SQL, PARAMS)]


@pytest.mark.asyncio
async def test_database_facade_passes_through_dict_rows():
    db = DatabaseLike([{"manager_name": "Sardor", "overall_score": 90}])

    assert await fetch_rows(db, SQL, PARAMS) == [
        {"manager_name": "Sardor", "overall_score": 90}
    ]


@pytest.mark.asyncio
async def test_empty_result_is_empty_list_not_error():
    assert await fetch_rows(DatabaseLike([]), SQL, PARAMS) == []


@pytest.mark.asyncio
async def test_unsupported_object_raises_instead_of_pretending_empty():
    class Nothing:
        pass

    with pytest.raises(TypeError):
        await fetch_rows(Nothing(), SQL, PARAMS)


@pytest.mark.asyncio
async def test_missing_connection_raises():
    class NoConn:
        async def get_connection(self):
            return None

    with pytest.raises(RuntimeError):
        await fetch_rows(NoConn(), SQL, PARAMS)


@pytest.mark.asyncio
async def test_write_commits_on_database_facade():
    db = DatabaseLike([])

    await execute_write(db, "INSERT INTO call_analyses (call_id) VALUES (?)", ["c1"])

    assert db.conn.executed[0][1] == ["c1"]
    assert db.conn.committed is True


@pytest.mark.asyncio
async def test_write_uses_pool_execute_when_available():
    pool = PoolLike()

    await execute_write(pool, "INSERT INTO call_analyses (call_id) VALUES (?)", ["c1"])

    assert pool.calls[0][1] == ["c1"]


@pytest.mark.asyncio
async def test_coach_reads_through_database_facade():
    """Uchidan-uchiga: murabbiy `Database` fasadida ham hisobot beradi."""
    from src.services.core.sales_quality_coach import SalesQualityCoach

    db = DatabaseLike([("Sardor", 90, "good", "[]", "[]", "sale", "c1", 300)])
    db.conn.execute = _cursor_with_columns(
        ["manager_name", "overall_score", "category", "weaknesses",
         "strengths", "outcome", "call_id", "duration_seconds"],
        [("Sardor", 90, "good", "[]", "[]", "sale", "c1", 300),
         ("Sardor", 70, "average", "[]", "[]", "follow_up", "c2", 200)],
    )

    report = await SalesQualityCoach(db=db).generate_daily_report("2026-07-21")

    assert report is not None
    assert "Sardor" in report


def _cursor_with_columns(columns, rows):
    class Cursor:
        description = tuple((c,) for c in columns)

        async def fetchall(self):
            return rows

    async def execute(sql, params):
        return Cursor()

    return execute
