"""Immutable AI snapshots and append-only human review/appeal audit."""
import hashlib
import json
from contextlib import contextmanager
from pathlib import Path
import sqlite3
import time

DEFAULT_REVIEWS = Path("data/conversation_quality.sqlite3")


class ReviewConflict(ValueError):
    pass


class QualityReviews:
    def __init__(self, path=None):
        self.path = Path(DEFAULT_REVIEWS if path is None else path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS evaluations (
                    call_id TEXT PRIMARY KEY, lead_id INTEGER, manager_id TEXT,
                    digest TEXT NOT NULL, payload TEXT NOT NULL, updated_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS reviews (
                    id INTEGER PRIMARY KEY, call_id TEXT NOT NULL, digest TEXT NOT NULL,
                    actor TEXT NOT NULL, decision TEXT NOT NULL, reason TEXT NOT NULL,
                    corrected_score REAL, created_at INTEGER NOT NULL
                );
            """)
        self.path.chmod(0o600)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def save(self, call_id, lead_id, manager_id, evaluation):
        payload = json.dumps(evaluation, ensure_ascii=False, sort_keys=True)
        digest = hashlib.sha256(f"{lead_id}:{manager_id}:{payload}".encode()).hexdigest()
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO evaluations VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(call_id) DO UPDATE SET lead_id=excluded.lead_id, "
                "manager_id=excluded.manager_id, digest=excluded.digest, payload=excluded.payload, "
                "updated_at=excluded.updated_at",
                (call_id, lead_id, str(manager_id) if manager_id is not None else None,
                 digest, payload, int(time.time())),
            )
        return digest

    def list(self, limit=200):
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM evaluations ORDER BY updated_at DESC LIMIT ?",
                                (max(1, min(limit, 500)),)).fetchall()
            return [self._view(conn, row) for row in rows]

    def get(self, call_id):
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM evaluations WHERE call_id = ?", (call_id,)).fetchone()
            return self._view(conn, row) if row else None

    def manager_window(self, manager_id, start, end):
        """Current snapshots whose latest review falls in the requested window."""
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT e.* FROM evaluations e JOIN reviews r ON r.id = "
                "(SELECT MAX(id) FROM reviews WHERE call_id=e.call_id AND digest=e.digest) "
                "WHERE e.manager_id=? AND r.created_at>=? AND r.created_at<?",
                (str(manager_id), start, end),
            ).fetchall()
            return [self._view(conn, row) for row in rows]

    @staticmethod
    def _view(conn, row):
        reviews = [dict(r) for r in conn.execute(
            "SELECT id, actor, decision, reason, corrected_score, created_at FROM reviews "
            "WHERE call_id = ? AND digest = ? ORDER BY id", (row["call_id"], row["digest"]),
        )]
        result = {**json.loads(row["payload"]), "call_id": row["call_id"],
                  "lead_id": row["lead_id"], "manager_id": row["manager_id"],
                  "revision": row["digest"], "updated_at": row["updated_at"], "reviews": reviews}
        result["review_status"] = reviews[-1]["decision"] if reviews else "pending"
        result["reviewed_score"] = reviews[-1]["corrected_score"] if reviews else None
        result["quality_approved"] = bool(result["review_status"] == "approved" and result["review_ready"])
        result["kpi_eligible"] = False  # Pilot, no approved payroll policy.
        return result

    def review(self, call_id, revision, actor, decision, reason, corrected_score=None):
        if decision not in {"approved", "rejected", "appealed"} or not reason.strip():
            raise ValueError("review_reason_required")
        if corrected_score is not None and not 0 <= corrected_score <= 100:
            raise ValueError("invalid_review_score")
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM evaluations WHERE call_id = ?", (call_id,)).fetchone()
            if not row or row["digest"] != revision:
                raise ReviewConflict("evaluation_changed")
            evaluation = json.loads(row["payload"])
            if decision == "approved" and not evaluation["review_ready"]:
                raise ValueError("insufficient_evidence")
            conn.execute("INSERT INTO reviews (call_id,digest,actor,decision,reason,corrected_score,created_at) "
                         "VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (call_id, revision, actor, decision, reason.strip(), corrected_score, int(time.time())))
        return self.get(call_id)
