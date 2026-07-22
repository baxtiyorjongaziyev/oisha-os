"""Ikki xil DB fasadi ustidan bir xil ishlaydigan so'rov yordamchilari.

Loyihada ikkita turdosh fasad yuradi:
  - `src.db.Database` — `get_connection()` beradi, `execute()` YO'Q
  - `src.database_pool.DatabasePool` — `execute()` beradi

Chaqiruvchi qaysi biri kelishini bilmaydi (`api_state.db_instance` birinchisi,
ba'zi servislar ikkinchisini oladi). Ilgari kod to'g'ridan-to'g'ri
`db.execute(...)` deb yozilgan va `Database` kelganda `AttributeError`
`except` ichida yutilgan — natijada "ma'lumot yo'q" deb ko'rsatilgan,
aslida jadval to'la edi.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)


async def _maybe_await(value: Any) -> Any:
    if hasattr(value, "__await__"):
        return await value
    return value


async def fetch_rows(
    db: Any,
    sql: str,
    params: Optional[Sequence[Any]] = None,
) -> List[Dict[str, Any]]:
    """SELECT natijasini dict ro'yxati qilib qaytaradi.

    Xatolikni yutmaydi — chaqiruvchi "bo'sh natija" va "so'rov yiqildi"
    holatlarini farqlay olishi kerak.
    """
    params = list(params or [])

    # 1-yo'l: DatabasePool.execute() — allaqachon dict qaytaradi
    execute = getattr(db, "execute", None)
    if callable(execute):
        rows = await _maybe_await(execute(sql, params))
        return [dict(row) for row in (rows or [])]

    # 2-yo'l: Database.get_connection() — kursor bilan ishlaymiz
    get_connection = getattr(db, "get_connection", None)
    if not callable(get_connection):
        raise TypeError(f"Qo'llab-quvvatlanmaydigan DB obyekti: {type(db).__name__}")

    conn = await _maybe_await(get_connection())
    if conn is None:
        raise RuntimeError("database_not_connected")

    cursor = await _maybe_await(conn.execute(sql, params))
    raw = await _maybe_await(cursor.fetchall())
    if not raw:
        return []

    first = raw[0]
    if isinstance(first, dict):
        return [dict(row) for row in raw]

    description = getattr(cursor, "description", None)
    if not description:
        raise RuntimeError("cursor_description_missing")
    columns = [col[0] for col in description]
    return [dict(zip(columns, row)) for row in raw]


async def execute_write(
    db: Any,
    sql: str,
    params: Optional[Sequence[Any]] = None,
) -> None:
    """INSERT/UPDATE/DELETE — commit bilan. Xatolikni yutmaydi."""
    params = list(params or [])

    execute = getattr(db, "execute", None)
    if callable(execute):
        await _maybe_await(execute(sql, params))
        return

    get_connection = getattr(db, "get_connection", None)
    if not callable(get_connection):
        raise TypeError(f"Qo'llab-quvvatlanmaydigan DB obyekti: {type(db).__name__}")

    conn = await _maybe_await(get_connection())
    if conn is None:
        raise RuntimeError("database_not_connected")

    await _maybe_await(conn.execute(sql, params))
    commit = getattr(conn, "commit", None)
    if callable(commit):
        await _maybe_await(commit())
