"""Safe SQL query builder — prevents SQL injection via parameterized queries.

Usage:
    from src.db.query_builder import QueryBuilder
    q = QueryBuilder("users")
    q.select("user_id", "first_name").where("role = ?", "manager").order_by("created_at", desc=True)
    sql, params = q.build()
    # → ("SELECT user_id, first_name FROM users WHERE role = ? ORDER BY created_at DESC", ("manager",))
"""
from __future__ import annotations

import structlog
from typing import Any, Dict, List, Optional, Tuple

logger = structlog.get_logger()


class QueryBuilder:
    """Fluent SQL query builder with parameterized queries."""

    def __init__(self, table: str):
        self._table = table
        self._columns: List[str] = []
        self._where_clauses: List[str] = []
        self._where_params: List[Any] = []
        self._order_by: Optional[str] = None
        self._order_desc: bool = False
        self._limit: Optional[int] = None
        self._offset: Optional[int] = None
        self._group_by: Optional[str] = None
        self._having: Optional[str] = None
        self._having_params: List[Any] = []
        self._joins: List[str] = []
        self._set_clauses: List[str] = []
        self._set_params: List[Any] = []

    def select(self, *columns: str) -> "QueryBuilder":
        """Select specific columns."""
        self._columns.extend(columns)
        return self

    def where(self, clause: str, *params: Any) -> "QueryBuilder":
        """Add WHERE clause with parameterized values."""
        self._where_clauses.append(clause)
        self._where_params.extend(params)
        return self

    def where_in(self, column: str, values: List[Any]) -> "QueryBuilder":
        """Add WHERE IN clause safely."""
        if not values:
            self._where_clauses.append("1 = 0")
        else:
            placeholders = ", ".join("?" for _ in values)
            self._where_clauses.append(f"{column} IN ({placeholders})")
            self._where_params.extend(values)
        return self

    def where_between(self, column: str, low: Any, high: Any) -> "QueryBuilder":
        """Add WHERE BETWEEN clause."""
        self._where_clauses.append(f"{column} BETWEEN ? AND ?")
        self._where_params.extend([low, high])
        return self

    def where_like(self, column: str, pattern: str) -> "QueryBuilder":
        """Add WHERE LIKE clause."""
        self._where_clauses.append(f"{column} LIKE ?")
        self._where_params.append(pattern)
        return self

    def order_by(self, column: str, desc: bool = False) -> "QueryBuilder":
        """Set ORDER BY."""
        self._order_by = column
        self._order_desc = desc
        return self

    def limit(self, n: int) -> "QueryBuilder":
        """Set LIMIT."""
        self._limit = n
        return self

    def offset(self, n: int) -> "QueryBuilder":
        """Set OFFSET."""
        self._offset = n
        return self

    def group_by(self, column: str) -> "QueryBuilder":
        """Set GROUP BY."""
        self._group_by = column
        return self

    def having(self, clause: str, *params: Any) -> "QueryBuilder":
        """Add HAVING clause."""
        self._having = clause
        self._having_params.extend(params)
        return self

    def join(self, table: str, on: str) -> "QueryBuilder":
        """Add JOIN clause."""
        self._joins.append(f"JOIN {table} ON {on}")
        return self

    def left_join(self, table: str, on: str) -> "QueryBuilder":
        """Add LEFT JOIN clause."""
        self._joins.append(f"LEFT JOIN {table} ON {on}")
        return self

    def set(self, **kwargs: Any) -> "QueryBuilder":
        """Set columns for UPDATE."""
        for col, val in kwargs.items():
            self._set_clauses.append(f"{col} = ?")
            self._set_params.append(val)
        return self

    def build_select(self) -> Tuple[str, Tuple[Any, ...]]:
        """Build SELECT query."""
        cols = ", ".join(self._columns) if self._columns else "*"
        sql = f"SELECT {cols} FROM {self._table}"  # nosec B608

        if self._joins:
            sql += " " + " ".join(self._joins)

        params: List[Any] = []

        if self._where_clauses:
            sql += " WHERE " + " AND ".join(self._where_clauses)
            params.extend(self._where_params)

        if self._group_by:
            sql += f" GROUP BY {self._group_by}"

        if self._having:
            sql += f" HAVING {self._having}"
            params.extend(self._having_params)

        if self._order_by:
            direction = "DESC" if self._order_desc else "ASC"
            sql += f" ORDER BY {self._order_by} {direction}"

        if self._limit is not None:
            sql += f" LIMIT {int(self._limit)}"

        if self._offset is not None:
            sql += f" OFFSET {int(self._offset)}"

        return sql, tuple(params)

    def build_insert(self, data: Dict[str, Any]) -> Tuple[str, Tuple[Any, ...]]:
        """Build INSERT query."""
        cols = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        sql = f"INSERT INTO {self._table} ({cols}) VALUES ({placeholders})"  # nosec B608
        return sql, tuple(data.values())

    def build_update(self) -> Tuple[str, Tuple[Any, ...]]:
        """Build UPDATE query."""
        if not self._set_clauses:
            raise ValueError("No SET clauses defined")

        sql = f"UPDATE {self._table} SET {', '.join(self._set_clauses)}"  # nosec B608
        params: List[Any] = list(self._set_params)

        if self._where_clauses:
            sql += " WHERE " + " AND ".join(self._where_clauses)
            params.extend(self._where_params)

        return sql, tuple(params)

    def build_delete(self) -> Tuple[str, Tuple[Any, ...]]:
        """Build DELETE query."""
        sql = f"DELETE FROM {self._table}"  # nosec B608
        params: List[Any] = []

        if self._where_clauses:
            sql += " WHERE " + " AND ".join(self._where_clauses)
            params.extend(self._where_params)

        return sql, tuple(params)

    def build_upsert(
        self,
        data: Dict[str, Any],
        conflict_columns: List[str],
        update_columns: List[str],
    ) -> Tuple[str, Tuple[Any, ...]]:
        """Build INSERT OR REPLACE / upsert query."""
        cols = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        update_clause = ", ".join(f"{col} = excluded.{col}" for col in update_columns)
        conflict_key = ", ".join(conflict_columns)

        sql = (
            f"INSERT INTO {self._table} ({cols}) VALUES ({placeholders}) "  # nosec B608
            f"ON CONFLICT({conflict_key}) DO UPDATE SET {update_clause}"
        )
        return sql, tuple(data.values())

    def build_count(self) -> Tuple[str, Tuple[Any, ...]]:
        """Build COUNT query."""
        sql = f"SELECT COUNT(*) FROM {self._table}"  # nosec B608
        params: List[Any] = []

        if self._where_clauses:
            sql += " WHERE " + " AND ".join(self._where_clauses)
            params.extend(self._where_params)

        return sql, tuple(params)

    # Alias for backward compat
    build = build_select


def safe_insert(table: str, data: Dict[str, Any]) -> Tuple[str, Tuple[Any, ...]]:
    """Quick safe INSERT."""
    return QueryBuilder(table).build_insert(data)


def safe_update(
    table: str,
    data: Dict[str, Any],
    where: str,
    *params: Any,
) -> Tuple[str, Tuple[Any, ...]]:
    """Quick safe UPDATE."""
    q = QueryBuilder(table).set(**data).where(where, *params)
    return q.build_update()


def safe_delete(
    table: str,
    where: str,
    *params: Any,
) -> Tuple[str, Tuple[Any, ...]]:
    """Quick safe DELETE."""
    q = QueryBuilder(table).where(where, *params)
    return q.build_delete()
