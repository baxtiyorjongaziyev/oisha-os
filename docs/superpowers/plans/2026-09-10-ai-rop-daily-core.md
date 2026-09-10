# AI ROP Daily Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an AI ROP (sales-team-lead) daily engine to Oisha-OS that runs a 3-slot daily cycle off AmoCRM, producing per-seller priority plans, midday checks, evening results, a deterministic closing-likelihood score, amoCRM-discipline findings, a CEO traffic-light dashboard, and live weekly-plan tracking.

**Architecture:** A new pure-logic package `src/services/core/rop/` (only `fetchers.py` does I/O) computes everything from plain dicts. `RopService.run(slot)` orchestrates fetch → compute → format and returns a delivery plan (`list[(chat_id, html)]`). `src/schedulers/rop_scheduler.py` owns timing (09:00/14:00/18:30 Tashkent, Mon–Sat), the `ROP_ENABLED` gate, sending via the existing bot runtime, and audit logging. Config and roster live in two DB tables via a new `RopRepository` (same `init_table()` pattern as `GamificationRepository`).

**Tech Stack:** Python 3.11, asyncio, `requests` (in `asyncio.to_thread` — matches existing AmoCRM code), Turso/SQLite via `database_pool` / `BaseRepository`, Telethon/aiogram bot runtime via `BotRuntimePort`, pytest with `SKIP_LIVE=1`, bandit.

## Global Constraints

- Python 3.11; asyncio; follow existing module patterns (no new scheduling framework — raw `asyncio` poll loops like `frog_scheduler`).
- All DB access through `BaseRepository` helpers / `database_pool`; never open raw connections. Tables created with `CREATE TABLE IF NOT EXISTS` in `init_table()`.
- All AmoCRM reads go through `fetchers.py` only. Bounded: ≤5 HTTP requests per slot run.
- Pure-logic modules (`scoring`, `discipline`, `traffic_light`, `weekly`, `daily` builders) take an injected `now: datetime` — never call the clock directly. No network, no DB.
- All user-facing text: **Uzbek (Latin), professional, terse, HTML** (`parse_mode="HTML"`). No LLM generation anywhere in v1. Templates live in `rop_messages.py` as f-string builders.
- Closing-likelihood output is **always** rendered with the disclaimer line `AI bahosi (taxminiy), fakt emas.`
- Delivery is internal-only: seller `telegram_user_id`s + `ROP_CEO_CHAT_ID`. No customer chat ids ever enter a delivery plan. `auto_reply_gate` is not involved.
- Scheduler gates every run on: `ROP_ENABLED == "1"` (default off), weekday ∈ Mon–Sat (skip Sunday), not `is_quiet_hours()`, and `DISABLE_UNSOLICITED_REPORTS != "1"`.
- New env vars (add to `.env.example`): `ROP_ENABLED=0`, `ROP_CEO_CHAT_ID=`.
- Timezone helpers: `from src.time_utils import get_local_now, is_quiet_hours, is_sunday`.
- Pipeline constants: `from src.services.core.crm.amocrm_pipeline_config import SALES_PIPELINE_ID, STATUS_WON, STATUS_LOST`.
- `SKIP_LIVE=1 python -m pytest -q` stays green; `bandit -r src/ -ll` clean.
- Commit style: `feat(rop): ...`, `test(rop): ...`, `chore(rop): ...`. End commit messages with the Co-Authored-By trailer.

---

## File Structure

**Create:**

| File | Responsibility |
|---|---|
| `src/services/core/rop/__init__.py` | package marker; re-export `RopService` |
| `src/services/core/rop/config.py` | `load_config(repo)` → dict with every key defaulted; `DEFAULTS` constant; `seed_config(repo)` |
| `src/services/core/rop/targets.py` | `load_roster(repo)` → `list[SellerTarget]` (active rows only); `SellerTarget` dataclass; `seed_default(repo, ...)` |
| `src/services/core/rop/scoring.py` | `score_lead(features, config, now)` → `ScoreResult`; `derive_features(lead, tasks, notes, events, config, now)` → dict |
| `src/services/core/rop/discipline.py` | `find(seller_leads, seller_tasks, seller_notes, config, now)` → `list[Finding]` |
| `src/services/core/rop/traffic_light.py` | `evaluate(metrics, findings, config, now)` → `TrafficResult` |
| `src/services/core/rop/weekly.py` | `progress(won_leads_since_monday, config, now)` → `WeeklyProgress`; `no_result_streak_days(seller_won_events, now)` → int |
| `src/services/core/rop/daily.py` | `build_morning / build_midday / build_evening` → per-seller model dataclasses; `build_ceo_*` |
| `src/services/core/rop/rop_messages.py` | one `render_*` per model → HTML str |
| `src/services/core/rop/fetchers.py` | `RopFetcher(amocrm)` with `fetch_active_sales_leads()`, `fetch_today_completed_tasks()`, `fetch_today_events()`, `fetch_won_leads_since(ts)`, `fetch_user_names(ids)` |
| `src/services/core/rop/service.py` | `RopService(repo, fetcher, bot_runtime, ceo_chat_id)`; `async run(slot) -> list[tuple[int, str]]` |
| `src/schedulers/rop_scheduler.py` | `morning_loop / midday_loop / evening_loop`; `start_rop_schedulers(bot_runtime)` |
| `src/db/repositories/rop.py` | `RopRepository(BaseRepository)`: `init_table`, `rop_targets` + `rop_config` CRUD |
| `tests/test_rop_config.py` … `tests/test_rop_scheduler.py` | one test module per unit |

**Modify:**

| File | Change |
|---|---|
| `src/db/__init__.py` | import `RopRepository`; `self.rop = RopRepository(self.conn_manager)`; `await self.rop.init_table()` in init chain |
| `src/bootstrap/orchestration/schedulers.py` | call `start_rop_schedulers(bot_runtime)` at end of `start_background_schedulers` |
| `.env.example` | add `ROP_ENABLED=0` and `ROP_CEO_CHAT_ID=` with comments |

---

## Task 1: `RopRepository` — tables + CRUD

**Files:**
- Create: `src/db/repositories/rop.py`
- Create: `tests/test_rop_repository.py`
- Modify: `src/db/__init__.py`

**Interfaces:**
- Consumes: `src.db.repositories.base.BaseRepository`
- Produces:
  - `RopRepository.init_table() -> None`
  - `RopRepository.upsert_target(responsible_user_id: int, *, seller_name: str, telegram_user_id: int | None, expected_sales: int = 1, calls: int = 10, follow_ups: int = 20, meetings: int = 2, proposals: int = 0, payments: int = 1, max_overdue: int = 0, active: int = 1) -> None`
  - `RopRepository.list_active_targets() -> list[dict]` (rows with `active = 1`, dict keys = column names)
  - `RopRepository.get_config(key: str, default=None) -> Any` (JSON-decoded)
  - `RopRepository.set_config(key: str, value: Any) -> None` (JSON-encoded)
  - `RopRepository.all_config() -> dict[str, Any]`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_rop_repository.py
import pytest
from src.db import Database

@pytest.fixture
async def db(tmp_path):
    d = Database(db_path=str(tmp_path / "rop.db"))
    await d.connect()
    await d.rop.init_table()
    yield d
    await d.close()

@pytest.mark.asyncio
async def test_init_table_idempotent(db):
    await db.rop.init_table()  # second call must not raise

@pytest.mark.asyncio
async def test_upsert_and_list_targets(db):
    await db.rop.upsert_target(101, seller_name="Oydin", telegram_user_id=555)
    await db.rop.upsert_target(102, seller_name="Shahnoza", telegram_user_id=None, active=0)
    rows = await db.rop.list_active_targets()
    assert [r["responsible_user_id"] for r in rows] == [101]
    assert rows[0]["calls"] == 10
    assert rows[0]["telegram_user_id"] == 555

@pytest.mark.asyncio
async def test_upsert_updates_existing(db):
    await db.rop.upsert_target(101, seller_name="Oydin", telegram_user_id=555)
    await db.rop.upsert_target(101, seller_name="Oydin K", telegram_user_id=777, calls=15)
    rows = await db.rop.list_active_targets()
    assert len(rows) == 1
    assert rows[0]["seller_name"] == "Oydin K"
    assert rows[0]["calls"] == 15
    assert rows[0]["telegram_user_id"] == 777

@pytest.mark.asyncio
async def test_config_roundtrip_and_default(db):
    assert await db.rop.get_config("missing", {"a": 1}) == {"a": 1}
    await db.rop.set_config("score.band_cutoffs", {"hot": 70, "warm": 40})
    assert await db.rop.get_config("score.band_cutoffs") == {"hot": 70, "warm": 40}
    dump = await db.rop.all_config()
    assert dump["score.band_cutoffs"]["hot"] == 70
```

- [ ] **Step 2: Run test to verify it fails**

Run: `SKIP_LIVE=1 python -m pytest tests/test_rop_repository.py -v`
Expected: FAIL — `AttributeError: 'Database' object has no attribute 'rop'`

- [ ] **Step 3: Write `src/db/repositories/rop.py`**

```python
"""Persistence for AI ROP: per-seller targets + key/value tuning config."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from src.db.repositories.base import BaseRepository

_TARGET_COLUMNS = (
    "seller_name", "telegram_user_id", "expected_sales", "calls", "follow_ups",
    "meetings", "proposals", "payments", "max_overdue", "active",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RopRepository(BaseRepository):
    async def init_table(self) -> None:
        await self._execute(
            """CREATE TABLE IF NOT EXISTS rop_targets (
                responsible_user_id INTEGER PRIMARY KEY,
                seller_name TEXT,
                telegram_user_id INTEGER,
                expected_sales INTEGER NOT NULL DEFAULT 1,
                calls INTEGER NOT NULL DEFAULT 10,
                follow_ups INTEGER NOT NULL DEFAULT 20,
                meetings INTEGER NOT NULL DEFAULT 2,
                proposals INTEGER NOT NULL DEFAULT 0,
                payments INTEGER NOT NULL DEFAULT 1,
                max_overdue INTEGER NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL
            )"""
        )
        await self._execute(
            """CREATE TABLE IF NOT EXISTS rop_config (
                key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )"""
        )
        conn = await self._get_conn()
        await conn.commit()

    async def upsert_target(
        self,
        responsible_user_id: int,
        *,
        seller_name: str,
        telegram_user_id: int | None,
        expected_sales: int = 1,
        calls: int = 10,
        follow_ups: int = 20,
        meetings: int = 2,
        proposals: int = 0,
        payments: int = 1,
        max_overdue: int = 0,
        active: int = 1,
    ) -> None:
        conn = await self._get_conn()
        await conn.execute(
            """INSERT INTO rop_targets (
                   responsible_user_id, seller_name, telegram_user_id, expected_sales,
                   calls, follow_ups, meetings, proposals, payments, max_overdue,
                   active, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(responsible_user_id) DO UPDATE SET
                   seller_name = excluded.seller_name,
                   telegram_user_id = excluded.telegram_user_id,
                   expected_sales = excluded.expected_sales,
                   calls = excluded.calls,
                   follow_ups = excluded.follow_ups,
                   meetings = excluded.meetings,
                   proposals = excluded.proposals,
                   payments = excluded.payments,
                   max_overdue = excluded.max_overdue,
                   active = excluded.active,
                   updated_at = excluded.updated_at""",
            (
                responsible_user_id, seller_name, telegram_user_id, expected_sales,
                calls, follow_ups, meetings, proposals, payments, max_overdue,
                active, _now(),
            ),
        )
        await conn.commit()

    async def list_active_targets(self) -> list[dict]:
        rows = await self._fetch_all(
            "SELECT * FROM rop_targets WHERE active = 1 ORDER BY responsible_user_id"
        )
        return rows

    async def get_config(self, key: str, default: Any = None) -> Any:
        row = await self._fetch_one(
            "SELECT value_json FROM rop_config WHERE key = ?", (key,)
        )
        if row is None:
            return default
        raw = row["value_json"] if isinstance(row, dict) else row[0]
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return default

    async def set_config(self, key: str, value: Any) -> None:
        conn = await self._get_conn()
        await conn.execute(
            """INSERT INTO rop_config (key, value_json, updated_at)
               VALUES (?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET
                   value_json = excluded.value_json,
                   updated_at = excluded.updated_at""",
            (key, json.dumps(value), _now()),
        )
        await conn.commit()

    async def all_config(self) -> dict[str, Any]:
        rows = await self._fetch_all("SELECT key, value_json FROM rop_config")
        out: dict[str, Any] = {}
        for r in rows:
            k = r["key"] if isinstance(r, dict) else r[0]
            v = r["value_json"] if isinstance(r, dict) else r[1]
            try:
                out[k] = json.loads(v)
            except (json.JSONDecodeError, TypeError):
                continue
        return out
```

- [ ] **Step 4: Wire into `src/db/__init__.py`**

Add near the other repository imports (after line ~26, the `GamificationRepository` import):

```python
from src.db.repositories.rop import RopRepository
```

In `Database.__init__`, next to `self.gamification = GamificationRepository(self.conn_manager)`:

```python
self.rop = RopRepository(self.conn_manager)
```

In the init-table chain (next to `await self.gamification.init_table()`):

```python
await self.rop.init_table()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `SKIP_LIVE=1 python -m pytest tests/test_rop_repository.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add src/db/repositories/rop.py src/db/__init__.py tests/test_rop_repository.py
git commit -m "feat(rop): RopRepository with rop_targets + rop_config tables

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 2: `config.py` — defaults + loader

**Files:**
- Create: `src/services/core/rop/__init__.py`
- Create: `src/services/core/rop/config.py`
- Create: `tests/test_rop_config.py`

**Interfaces:**
- Consumes: `RopRepository.all_config()`, `RopRepository.set_config()`
- Produces:
  - `DEFAULTS: dict[str, Any]` — every config key with its default value
  - `async load_config(repo) -> dict[str, Any]` — `DEFAULTS` deep-merged under stored values (stored wins per top-level key)
  - `async seed_config(repo) -> None` — writes any missing key from `DEFAULTS`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_rop_config.py
import pytest
from src.services.core.rop.config import DEFAULTS, load_config, seed_config


class FakeRepo:
    def __init__(self, stored=None):
        self.stored = dict(stored or {})
    async def all_config(self):
        return dict(self.stored)
    async def set_config(self, k, v):
        self.stored[k] = v


@pytest.mark.asyncio
async def test_load_config_fills_all_defaults():
    cfg = await load_config(FakeRepo())
    for key in DEFAULTS:
        assert key in cfg
    assert cfg["score.band_cutoffs"] == {"hot": 70, "warm": 40}
    assert cfg["weekly.sales_target"] == 10
    assert cfg["traffic.red_no_result_days"] == 3

@pytest.mark.asyncio
async def test_stored_value_overrides_default():
    repo = FakeRepo({"weekly.sales_target": 15})
    cfg = await load_config(repo)
    assert cfg["weekly.sales_target"] == 15
    assert cfg["weekly.revenue_target"] == DEFAULTS["weekly.revenue_target"]

@pytest.mark.asyncio
async def test_seed_config_writes_only_missing():
    repo = FakeRepo({"weekly.sales_target": 15})
    await seed_config(repo)
    assert repo.stored["weekly.sales_target"] == 15          # untouched
    assert repo.stored["traffic.red_overdue_count"] == 5      # seeded
    assert set(repo.stored) == set(DEFAULTS)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `SKIP_LIVE=1 python -m pytest tests/test_rop_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.services.core.rop.config'`

- [ ] **Step 3: Write the modules**

`src/services/core/rop/__init__.py`:

```python
"""AI ROP — Sotuv bo'limi rahbari (daily core)."""
```

`src/services/core/rop/config.py`:

```python
"""AI ROP tuning config: defaults + loader. All values overridable via rop_config."""
from __future__ import annotations

from typing import Any

DEFAULTS: dict[str, Any] = {
    # --- scoring ---
    "score.weights": {
        "stage": 40, "open_next_task": 10, "proposal_sent": 12, "meeting_held": 12,
        "payment_promised": 20, "recent_0_24h": 8, "recent_gt_72h": -12,
        "objection_open": -10, "task_overdue": -12,
        "days_in_stage_le_7": 5, "days_in_stage_gt_21": -10,
    },
    # status_id -> 0..1 readiness. Curated; unknown stages fall back to 0.15.
    "score.stage_weights": {},
    "score.band_cutoffs": {"hot": 70, "warm": 40},
    "score.objection_keywords": ["qimmat", "narx", "budjet", "keyin", "o'ylab"],
    "score.payment_keywords": ["to'lov", "oplata", "perevod", "karta", "hisob"],
    # --- discipline ---
    "discipline.stagnant_days": 3,
    "discipline.terminal_stage_ids": [],
    # --- traffic light ---
    "traffic.red_no_result_days": 3,
    "traffic.red_overdue_count": 5,
    "traffic.red_discipline_count": 8,
    "traffic.big_deal_amount": 10_000_000,
    "traffic.stuck_deal_days": 14,
    "traffic.yellow_pace_pct": 0.5,
    "traffic.hot_lead_silent_hours": 48,
    # --- midday ---
    "midday.pace_pct": 0.4,
    # --- weekly ---
    "weekly.sales_target": 10,
    "weekly.revenue_target": 100_000_000,
}


async def load_config(repo) -> dict[str, Any]:
    stored = await repo.all_config()
    return {key: stored.get(key, default) for key, default in DEFAULTS.items()}


async def seed_config(repo) -> None:
    stored = await repo.all_config()
    for key, default in DEFAULTS.items():
        if key not in stored:
            await repo.set_config(key, default)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `SKIP_LIVE=1 python -m pytest tests/test_rop_config.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/services/core/rop/__init__.py src/services/core/rop/config.py tests/test_rop_config.py
git commit -m "feat(rop): config defaults + loader

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 3: `targets.py` — roster + `SellerTarget`

**Files:**
- Create: `src/services/core/rop/targets.py`
- Create: `tests/test_rop_targets.py`

**Interfaces:**
- Consumes: `RopRepository.list_active_targets()`, `RopRepository.upsert_target()`
- Produces:
  - `@dataclass(frozen=True) SellerTarget` with fields: `responsible_user_id: int`, `seller_name: str`, `telegram_user_id: int | None`, `expected_sales: int`, `calls: int`, `follow_ups: int`, `meetings: int`, `proposals: int`, `payments: int`, `max_overdue: int`
  - `async load_roster(repo) -> list[SellerTarget]`
  - `async seed_default(repo, responsible_user_id: int, telegram_user_id: int | None, seller_name: str) -> None` — one row with brief defaults

- [ ] **Step 1: Write the failing test**

```python
# tests/test_rop_targets.py
import pytest
from src.services.core.rop.targets import SellerTarget, load_roster, seed_default


class FakeRepo:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.upserts = []
    async def list_active_targets(self):
        return [dict(r) for r in self.rows]
    async def upsert_target(self, uid, **kw):
        self.upserts.append((uid, kw))


@pytest.mark.asyncio
async def test_load_roster_maps_rows():
    repo = FakeRepo([{
        "responsible_user_id": 101, "seller_name": "Oydin", "telegram_user_id": 555,
        "expected_sales": 1, "calls": 10, "follow_ups": 20, "meetings": 2,
        "proposals": 0, "payments": 1, "max_overdue": 0, "active": 1,
        "updated_at": "x",
    }])
    roster = await load_roster(repo)
    assert roster == [SellerTarget(101, "Oydin", 555, 1, 10, 20, 2, 0, 1, 0)]

@pytest.mark.asyncio
async def test_load_roster_empty():
    assert await load_roster(FakeRepo([])) == []

@pytest.mark.asyncio
async def test_seed_default_uses_brief_defaults():
    repo = FakeRepo()
    await seed_default(repo, 101, 555, "Oydin")
    uid, kw = repo.upserts[0]
    assert uid == 101
    assert kw["calls"] == 10 and kw["follow_ups"] == 20 and kw["meetings"] == 2
    assert kw["expected_sales"] == 1 and kw["max_overdue"] == 0
    assert kw["telegram_user_id"] == 555 and kw["seller_name"] == "Oydin"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `SKIP_LIVE=1 python -m pytest tests/test_rop_targets.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write `src/services/core/rop/targets.py`**

```python
"""AI ROP roster: sellers are exactly the active rows in rop_targets."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SellerTarget:
    responsible_user_id: int
    seller_name: str
    telegram_user_id: int | None
    expected_sales: int
    calls: int
    follow_ups: int
    meetings: int
    proposals: int
    payments: int
    max_overdue: int


async def load_roster(repo) -> list[SellerTarget]:
    rows = await repo.list_active_targets()
    return [
        SellerTarget(
            responsible_user_id=int(r["responsible_user_id"]),
            seller_name=r.get("seller_name") or f"Menejer_{r['responsible_user_id']}",
            telegram_user_id=r.get("telegram_user_id"),
            expected_sales=int(r.get("expected_sales", 1)),
            calls=int(r.get("calls", 10)),
            follow_ups=int(r.get("follow_ups", 20)),
            meetings=int(r.get("meetings", 2)),
            proposals=int(r.get("proposals", 0)),
            payments=int(r.get("payments", 1)),
            max_overdue=int(r.get("max_overdue", 0)),
        )
        for r in rows
    ]


async def seed_default(
    repo, responsible_user_id: int, telegram_user_id: int | None, seller_name: str
) -> None:
    await repo.upsert_target(
        responsible_user_id,
        seller_name=seller_name,
        telegram_user_id=telegram_user_id,
        expected_sales=1,
        calls=10,
        follow_ups=20,
        meetings=2,
        proposals=0,
        payments=1,
        max_overdue=0,
        active=1,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `SKIP_LIVE=1 python -m pytest tests/test_rop_targets.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/services/core/rop/targets.py tests/test_rop_targets.py
git commit -m "feat(rop): roster loader + SellerTarget

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 4: `scoring.py` — feature derivation + closing-likelihood

**Files:**
- Create: `src/services/core/rop/scoring.py`
- Create: `tests/test_rop_scoring.py`

**Interfaces:**
- Consumes: `config` dict from `load_config` (keys `score.*`)
- Produces:
  - `@dataclass(frozen=True) ScoreResult` — `score: int` (0..100), `band: str` (`"HOT"|"WARM"|"COLD"`), `reasons: list[str]`
  - `derive_features(lead: dict, lead_tasks: list[dict], lead_notes: list[dict], lead_events: list[dict], config: dict, now: datetime) -> dict` — keys: `stage_weight: float`, `last_interaction_hours: float`, `has_open_next_task: bool`, `task_overdue: bool`, `proposal_sent: bool`, `meeting_held: bool`, `objection_open: bool`, `payment_promised: bool`, `days_in_stage: float`
  - `score_lead(features: dict, config: dict) -> ScoreResult`
  - `DISCLAIMER: str = "AI bahosi (taxminiy), fakt emas."`

Notes for the implementer:
- AmoCRM timestamps (`updated_at`, `complete_till`, `created_at`, event `created_at`) are **Unix epoch seconds** (ints). Convert with `datetime.fromtimestamp(ts, tz=timezone.utc)`.
- Task type: AmoCRM `task_type_id` — `1` = call, `2` = meeting; anything else counts as a generic/follow-up task. Meeting-held = a **completed** (`is_completed` truthy) task with `task_type_id == 2`.
- "proposal_sent" marker: `stage_weight >= 0.5` OR any note text containing `"kp"` / `"taklif"` / `"tijorat taklif"` (case-insensitive).
- "objection_open": any note text matches a `score.objection_keywords` entry AND no later note (higher `created_at`) contains `"hal qilindi"` / `"kelishildi"`.
- "payment_promised": any note text matches a `score.payment_keywords` entry.
- `days_in_stage`: from the latest event with `type == "lead_status_changed"`; if none, from `lead["created_at"]`.
- `last_interaction_hours`: `now - max(latest event created_at, latest completed-task complete_till, latest note created_at)`; if nothing, treat as `999`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_rop_scoring.py
from datetime import datetime, timezone
import pytest
from src.services.core.rop.config import DEFAULTS
from src.services.core.rop.scoring import score_lead, ScoreResult, DISCLAIMER

CFG = dict(DEFAULTS)
NOW = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)

def feats(**over):
    base = dict(
        stage_weight=0.15, last_interaction_hours=1.0, has_open_next_task=True,
        task_overdue=False, proposal_sent=False, meeting_held=False,
        objection_open=False, payment_promised=False, days_in_stage=3.0,
    )
    base.update(over)
    return base

def test_hot_deal_scores_high_and_bands_hot():
    r = score_lead(feats(stage_weight=0.85, proposal_sent=True, meeting_held=True,
                         payment_promised=True, last_interaction_hours=2.0,
                         days_in_stage=4.0), CFG)
    assert isinstance(r, ScoreResult)
    assert r.score >= 70
    assert r.band == "HOT"
    assert any("to'lov" in x.lower() for x in r.reasons)

def test_cold_deal_bands_cold():
    r = score_lead(feats(stage_weight=0.1, has_open_next_task=False,
                         task_overdue=True, objection_open=True,
                         last_interaction_hours=120.0, days_in_stage=40.0), CFG)
    assert r.score < 40
    assert r.band == "COLD"

def test_warm_middle_band():
    r = score_lead(feats(stage_weight=0.55, proposal_sent=True,
                         last_interaction_hours=30.0, days_in_stage=10.0), CFG)
    assert 40 <= r.score < 70
    assert r.band == "WARM"

def test_score_clamped_0_100():
    lo = score_lead(feats(stage_weight=0.0, has_open_next_task=False,
                          task_overdue=True, objection_open=True,
                          last_interaction_hours=300.0, days_in_stage=99.0), CFG)
    hi = score_lead(feats(stage_weight=1.0, has_open_next_task=True,
                          proposal_sent=True, meeting_held=True,
                          payment_promised=True, last_interaction_hours=1.0,
                          days_in_stage=1.0), CFG)
    assert 0 <= lo.score <= 100 and 0 <= hi.score <= 100

def test_disclaimer_constant():
    assert DISCLAIMER == "AI bahosi (taxminiy), fakt emas."
```

- [ ] **Step 2: Run test to verify it fails**

Run: `SKIP_LIVE=1 python -m pytest tests/test_rop_scoring.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write `src/services/core/rop/scoring.py`**

```python
"""Deterministic closing-likelihood. No LLM, no I/O. Injected `now`."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

DISCLAIMER = "AI bahosi (taxminiy), fakt emas."


@dataclass(frozen=True)
class ScoreResult:
    score: int
    band: str
    reasons: list[str]


def _epoch_to_dt(ts) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def _note_text(note: dict) -> str:
    params = note.get("params") or {}
    return str(params.get("text") or note.get("text") or "").lower()


def derive_features(lead, lead_tasks, lead_notes, lead_events, config, now):
    stage_weights = config.get("score.stage_weights", {})
    status_id = str(lead.get("status_id", ""))
    stage_weight = float(stage_weights.get(status_id, 0.15))

    open_tasks = [t for t in lead_tasks if not t.get("is_completed")]
    has_open_next_task = bool(open_tasks)
    now_epoch = now.timestamp()
    task_overdue = any(
        (t.get("complete_till") or 0) and float(t["complete_till"]) < now_epoch
        for t in open_tasks
    )
    meeting_held = any(
        t.get("is_completed") and t.get("task_type_id") == 2 for t in lead_tasks
    )

    notes_sorted = sorted(lead_notes, key=lambda n: n.get("created_at") or 0)
    obj_kw = config.get("score.objection_keywords", [])
    pay_kw = config.get("score.payment_keywords", [])
    objection_open = False
    for n in notes_sorted:
        txt = _note_text(n)
        if any(k in txt for k in obj_kw):
            later = [_note_text(m) for m in notes_sorted
                     if (m.get("created_at") or 0) > (n.get("created_at") or 0)]
            if not any(("hal qilindi" in t or "kelishildi" in t) for t in later):
                objection_open = True
    payment_promised = any(
        any(k in _note_text(n) for k in pay_kw) for n in notes_sorted
    )
    proposal_sent = stage_weight >= 0.5 or any(
        ("kp" in _note_text(n) or "taklif" in _note_text(n)) for n in notes_sorted
    )

    status_events = sorted(
        (e for e in lead_events if e.get("type") == "lead_status_changed"),
        key=lambda e: e.get("created_at") or 0,
    )
    if status_events:
        stage_start = _epoch_to_dt(status_events[-1]["created_at"])
    else:
        stage_start = _epoch_to_dt(lead.get("created_at"))
    days_in_stage = (now - stage_start).total_seconds() / 86400 if stage_start else 999.0

    interaction_epochs = []
    interaction_epochs += [e.get("created_at") or 0 for e in lead_events]
    interaction_epochs += [
        t.get("complete_till") or 0 for t in lead_tasks if t.get("is_completed")
    ]
    interaction_epochs += [n.get("created_at") or 0 for n in lead_notes]
    latest = max(interaction_epochs) if interaction_epochs else 0
    last_interaction_hours = (
        (now_epoch - latest) / 3600 if latest else 999.0
    )

    return {
        "stage_weight": stage_weight,
        "last_interaction_hours": last_interaction_hours,
        "has_open_next_task": has_open_next_task,
        "task_overdue": task_overdue,
        "proposal_sent": proposal_sent,
        "meeting_held": meeting_held,
        "objection_open": objection_open,
        "payment_promised": payment_promised,
        "days_in_stage": days_in_stage,
    }


def score_lead(features, config) -> ScoreResult:
    w = config["score.weights"]
    cutoffs = config["score.band_cutoffs"]
    score = 0.0
    reasons: list[str] = []

    score += round(features["stage_weight"] * w["stage"])
    if features["stage_weight"] >= 0.5:
        reasons.append("Bosqich yakuniga yaqin")

    if features["has_open_next_task"]:
        score += w["open_next_task"]
    else:
        score += -abs(w["open_next_task"])
        reasons.append("Keyingi task yo'q")

    if features["proposal_sent"]:
        score += w["proposal_sent"]
        reasons.append("KP yuborilgan")
    if features["meeting_held"]:
        score += w["meeting_held"]
        reasons.append("Uchrashuv bo'lgan")
    if features["payment_promised"]:
        score += w["payment_promised"]
        reasons.append("To'lov va'da qilingan")

    h = features["last_interaction_hours"]
    if h <= 24:
        score += w["recent_0_24h"]
    elif h > 72:
        score += w["recent_gt_72h"]
        reasons.append("72 soatdan beri aloqa yo'q")

    if features["objection_open"]:
        score += w["objection_open"]
        reasons.append("Ochiq e'tiroz bor")
    if features["task_overdue"]:
        score += w["task_overdue"]
        reasons.append("Muddati o'tgan task")

    d = features["days_in_stage"]
    if d <= 7:
        score += w["days_in_stage_le_7"]
    elif d > 21:
        score += w["days_in_stage_gt_21"]
        reasons.append("Bosqichda 3 haftadan ko'p")

    score_i = max(0, min(100, int(round(score))))
    if score_i >= cutoffs["hot"]:
        band = "HOT"
    elif score_i >= cutoffs["warm"]:
        band = "WARM"
    else:
        band = "COLD"
    return ScoreResult(score=score_i, band=band, reasons=reasons)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `SKIP_LIVE=1 python -m pytest tests/test_rop_scoring.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Add a `derive_features` test**

```python
# append to tests/test_rop_scoring.py
from src.services.core.rop.scoring import derive_features

def test_derive_features_from_raw_amocrm_shapes():
    lead = {"status_id": 111, "created_at": int(NOW.timestamp()) - 10 * 86400}
    tasks = [
        {"is_completed": True, "task_type_id": 2, "complete_till": int(NOW.timestamp()) - 3600},
        {"is_completed": False, "task_type_id": 1, "complete_till": int(NOW.timestamp()) - 7200},
    ]
    notes = [
        {"created_at": int(NOW.timestamp()) - 5000, "params": {"text": "Mijoz narx qimmat dedi"}},
        {"created_at": int(NOW.timestamp()) - 1000, "params": {"text": "To'lov kuni kelishildi"}},
    ]
    events = [{"type": "lead_status_changed", "created_at": int(NOW.timestamp()) - 2 * 86400}]
    cfg = dict(DEFAULTS)
    cfg["score.stage_weights"] = {"111": 0.55}
    f = derive_features(lead, tasks, notes, events, cfg, NOW)
    assert f["stage_weight"] == 0.55
    assert f["meeting_held"] is True
    assert f["task_overdue"] is True
    assert f["payment_promised"] is True
    assert f["objection_open"] is False   # "kelishildi" resolves it
    assert 1.9 < f["days_in_stage"] < 2.1
    assert f["last_interaction_hours"] < 1.0
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `SKIP_LIVE=1 python -m pytest tests/test_rop_scoring.py -v`
Expected: PASS (6 tests)

- [ ] **Step 7: Commit**

```bash
git add src/services/core/rop/scoring.py tests/test_rop_scoring.py
git commit -m "feat(rop): deterministic closing-likelihood scoring

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 5: `discipline.py` — amoCRM discipline findings

**Files:**
- Create: `src/services/core/rop/discipline.py`
- Create: `tests/test_rop_discipline.py`

**Interfaces:**
- Consumes: `config` (`discipline.stagnant_days`, `discipline.terminal_stage_ids`), `STATUS_WON`, `STATUS_LOST`
- Produces:
  - `@dataclass(frozen=True) Finding` — `lead_name: str`, `type: str`, `detail: str`
  - `FINDING_TYPES = ("NO_NEXT_TASK", "OVERDUE_TASK", "STAGNANT", "NO_OWNER", "WRONG_STAGE", "IMPORTANT_NO_NOTE")`
  - `find(seller_leads: list[dict], tasks_by_lead: dict[int, list[dict]], notes_by_lead: dict[int, list[dict]], config: dict, now: datetime) -> list[Finding]`

Rules (one lead may yield several findings):
- Active lead = `status_id not in (STATUS_WON, STATUS_LOST)`.
- `NO_NEXT_TASK`: active lead, no open task in `tasks_by_lead`.
- `OVERDUE_TASK`: active lead, an open task with `complete_till < now_epoch`. `detail` = that task's text.
- `STAGNANT`: active lead, `(now_epoch - lead["updated_at"]) > stagnant_days*86400`.
- `NO_OWNER`: `not lead.get("responsible_user_id")` (any status). `lead_name` used; caller routes to CEO.
- `WRONG_STAGE`: `status_id in (WON, LOST)` but has an open task; OR active and `status_id in terminal_stage_ids`.
- `IMPORTANT_NO_NOTE`: a task in `tasks_by_lead` with `is_completed` truthy, `task_type_id in (1, 2)`, `complete_till` within today (Tashkent day of `now`), and `notes_by_lead` has no note with `created_at >= that complete_till`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_rop_discipline.py
from datetime import datetime, timezone
from src.services.core.rop.config import DEFAULTS
from src.services.core.rop.discipline import find, Finding

CFG = dict(DEFAULTS)
NOW = datetime(2026, 9, 10, 15, 0, tzinfo=timezone.utc)
E = int(NOW.timestamp())

def _types(findings, name):
    return sorted(f.type for f in findings if f.lead_name == name)

def test_no_next_task_and_stagnant():
    leads = [{"id": 1, "name": "ABC", "status_id": 111,
              "responsible_user_id": 101, "updated_at": E - 5 * 86400}]
    out = find(leads, {1: []}, {1: []}, CFG, NOW)
    assert _types(out, "ABC") == ["NO_NEXT_TASK", "STAGNANT"]

def test_overdue_task_detail():
    leads = [{"id": 2, "name": "XYZ", "status_id": 111,
              "responsible_user_id": 101, "updated_at": E - 100}]
    tasks = {2: [{"is_completed": False, "complete_till": E - 3600, "text": "Qo'ng'iroq qilish"}]}
    out = find(leads, tasks, {2: []}, CFG, NOW)
    od = [f for f in out if f.type == "OVERDUE_TASK"]
    assert od and od[0].detail == "Qo'ng'iroq qilish"

def test_no_owner_reported():
    leads = [{"id": 3, "name": "Sport Life", "status_id": 111,
              "responsible_user_id": None, "updated_at": E - 100}]
    out = find(leads, {3: [{"is_completed": False, "complete_till": E + 3600}]}, {3: []}, CFG, NOW)
    assert any(f.type == "NO_OWNER" and f.lead_name == "Sport Life" for f in out)

def test_wrong_stage_won_with_open_task():
    leads = [{"id": 4, "name": "Done Co", "status_id": 142,
              "responsible_user_id": 101, "updated_at": E - 100}]
    out = find(leads, {4: [{"is_completed": False, "complete_till": E + 3600}]}, {4: []}, CFG, NOW)
    assert any(f.type == "WRONG_STAGE" for f in out)

def test_important_no_note():
    leads = [{"id": 5, "name": "CallCo", "status_id": 111,
              "responsible_user_id": 101, "updated_at": E - 100}]
    tasks = {5: [
        {"is_completed": True, "task_type_id": 1, "complete_till": E - 1800},   # call done 30m ago
        {"is_completed": False, "complete_till": E + 3600},
    ]}
    out = find(leads, tasks, {5: []}, CFG, NOW)
    assert any(f.type == "IMPORTANT_NO_NOTE" for f in out)
    # with a fresh note, it disappears
    out2 = find(leads, tasks, {5: [{"created_at": E - 600, "params": {"text": "gaplashdim"}}]}, CFG, NOW)
    assert not any(f.type == "IMPORTANT_NO_NOTE" for f in out2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `SKIP_LIVE=1 python -m pytest tests/test_rop_discipline.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write `src/services/core/rop/discipline.py`**

```python
"""AI ROP amoCRM discipline checks. Pure; injected `now`."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.services.core.crm.amocrm_pipeline_config import STATUS_LOST, STATUS_WON

FINDING_TYPES = (
    "NO_NEXT_TASK", "OVERDUE_TASK", "STAGNANT", "NO_OWNER",
    "WRONG_STAGE", "IMPORTANT_NO_NOTE",
)


@dataclass(frozen=True)
class Finding:
    lead_name: str
    type: str
    detail: str


def _name(lead: dict) -> str:
    return lead.get("name") or f"Lead {lead.get('id')}"


def _day_bounds(now: datetime) -> tuple[float, float]:
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.timestamp(), now.timestamp()


def _note_time(note: dict) -> int:
    return int(note.get("created_at") or 0)


def find(seller_leads, tasks_by_lead, notes_by_lead, config, now) -> list[Finding]:
    stagnant_secs = int(config["discipline.stagnant_days"]) * 86400
    terminal_ids = set(config.get("discipline.terminal_stage_ids", []))
    now_epoch = now.timestamp()
    day_start, day_end = _day_bounds(now)
    out: list[Finding] = []

    for lead in seller_leads:
        lid = lead.get("id")
        name = _name(lead)
        status_id = lead.get("status_id")
        is_terminal = status_id in (STATUS_WON, STATUS_LOST)
        is_active = not is_terminal
        tasks = tasks_by_lead.get(lid, [])
        notes = notes_by_lead.get(lid, [])
        open_tasks = [t for t in tasks if not t.get("is_completed")]

        if not lead.get("responsible_user_id"):
            out.append(Finding(name, "NO_OWNER", ""))

        if is_active and not open_tasks:
            out.append(Finding(name, "NO_NEXT_TASK", ""))

        if is_active:
            for t in open_tasks:
                ct = t.get("complete_till") or 0
                if ct and float(ct) < now_epoch:
                    out.append(Finding(name, "OVERDUE_TASK", str(t.get("text") or "")))
                    break

        if is_active and (now_epoch - float(lead.get("updated_at") or now_epoch)) > stagnant_secs:
            out.append(Finding(name, "STAGNANT", ""))

        if (is_terminal and open_tasks) or (is_active and status_id in terminal_ids):
            out.append(Finding(name, "WRONG_STAGE", ""))

        for t in tasks:
            if not t.get("is_completed") or t.get("task_type_id") not in (1, 2):
                continue
            ct = float(t.get("complete_till") or 0)
            if not (day_start <= ct <= day_end):
                continue
            if not any(_note_time(n) >= ct for n in notes):
                out.append(Finding(name, "IMPORTANT_NO_NOTE", ""))
                break

    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `SKIP_LIVE=1 python -m pytest tests/test_rop_discipline.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/services/core/rop/discipline.py tests/test_rop_discipline.py
git commit -m "feat(rop): amoCRM discipline findings

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 6: `weekly.py` — live weekly progress + no-result streak

**Files:**
- Create: `src/services/core/rop/weekly.py`
- Create: `tests/test_rop_weekly.py`

**Interfaces:**
- Consumes: `config` (`weekly.sales_target`, `weekly.revenue_target`), `STATUS_WON`
- Produces:
  - `@dataclass(frozen=True) WeeklyProgress` — `won_count: int`, `won_revenue: int`, `sales_target: int`, `revenue_target: int`, `sales_pct: float`, `revenue_pct: float`
  - `progress(won_leads: list[dict], config: dict) -> WeeklyProgress` — `won_leads` are already filtered to `closed_at >= Monday 00:00 Tashkent`; counts those with `status_id == STATUS_WON`, sums `price`.
  - `no_result_streak_days(seller_won_closed_at: list[int], now: datetime) -> int` — count consecutive prior working days (Mon–Sat, walking back from `now`'s date, **excluding today**) that have zero `closed_at` falling in that day; stop at the first day that has one. Cap at 7.
  - `monday_start(now: datetime) -> datetime` — helper, Monday 00:00 in `now`'s tz.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_rop_weekly.py
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from src.services.core.rop.config import DEFAULTS
from src.services.core.rop.weekly import progress, no_result_streak_days, monday_start, WeeklyProgress
from src.services.core.crm.amocrm_pipeline_config import STATUS_WON

TZ = ZoneInfo("Asia/Tashkent")
CFG = dict(DEFAULTS)

def test_progress_counts_and_pcts():
    leads = [
        {"status_id": STATUS_WON, "price": 12_000_000},
        {"status_id": STATUS_WON, "price": 13_000_000},
        {"status_id": 143, "price": 9_000_000},  # lost — ignored
    ]
    p = progress(leads, CFG)
    assert isinstance(p, WeeklyProgress)
    assert p.won_count == 2
    assert p.won_revenue == 25_000_000
    assert p.sales_target == 10
    assert round(p.sales_pct, 1) == 20.0
    assert round(p.revenue_pct, 1) == 25.0

def test_monday_start_is_monday_midnight():
    wed = datetime(2026, 9, 9, 15, 30, tzinfo=TZ)   # Wednesday
    ms = monday_start(wed)
    assert ms.weekday() == 0 and ms.hour == 0 and ms.minute == 0
    assert (wed - ms).days == 2

def test_no_result_streak_skips_sunday_and_stops_on_hit():
    now = datetime(2026, 9, 10, 18, 0, tzinfo=TZ)   # Thursday
    # Wed and Tue empty, Mon has a win -> streak 2 (Sun 2026-09-07 skipped anyway)
    mon_win = int(datetime(2026, 9, 8, 11, 0, tzinfo=TZ).timestamp())  # Monday
    assert no_result_streak_days([mon_win], now) == 2

def test_no_result_streak_capped_at_7():
    now = datetime(2026, 9, 10, 18, 0, tzinfo=TZ)
    assert no_result_streak_days([], now) == 7
```

- [ ] **Step 2: Run test to verify it fails**

Run: `SKIP_LIVE=1 python -m pytest tests/test_rop_weekly.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write `src/services/core/rop/weekly.py`**

```python
"""AI ROP weekly team progress + per-seller no-result streak. Stateless."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from src.services.core.crm.amocrm_pipeline_config import STATUS_WON


@dataclass(frozen=True)
class WeeklyProgress:
    won_count: int
    won_revenue: int
    sales_target: int
    revenue_target: int
    sales_pct: float
    revenue_pct: float


def monday_start(now: datetime) -> datetime:
    d = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return d - timedelta(days=d.weekday())


def progress(won_leads, config) -> WeeklyProgress:
    st = int(config["weekly.sales_target"])
    rt = int(config["weekly.revenue_target"])
    won = [l for l in won_leads if l.get("status_id") == STATUS_WON]
    count = len(won)
    revenue = sum(int(l.get("price") or 0) for l in won)
    return WeeklyProgress(
        won_count=count,
        won_revenue=revenue,
        sales_target=st,
        revenue_target=rt,
        sales_pct=(count / st * 100) if st else 0.0,
        revenue_pct=(revenue / rt * 100) if rt else 0.0,
    )


def no_result_streak_days(seller_won_closed_at, now: datetime) -> int:
    tz = now.tzinfo
    wins = [datetime.fromtimestamp(int(ts), tz=tz).date() for ts in seller_won_closed_at]
    win_days = set(wins)
    streak = 0
    day = now.date() - timedelta(days=1)
    while streak < 7:
        if day.weekday() == 6:  # Sunday — not a working day, skip without counting
            day -= timedelta(days=1)
            continue
        if day in win_days:
            break
        streak += 1
        day -= timedelta(days=1)
    return streak
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `SKIP_LIVE=1 python -m pytest tests/test_rop_weekly.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/services/core/rop/weekly.py tests/test_rop_weekly.py
git commit -m "feat(rop): live weekly progress + no-result streak

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 7: `traffic_light.py` — GREEN/YELLOW/RED

**Files:**
- Create: `src/services/core/rop/traffic_light.py`
- Create: `tests/test_rop_traffic_light.py`

**Interfaces:**
- Consumes: `config` (`traffic.*`), `Finding` list from `discipline.find`
- Produces:
  - `@dataclass(frozen=True) TrafficResult` — `level: str` (`"GREEN"|"YELLOW"|"RED"`), `reasons: list[str]`
  - `@dataclass SellerMetrics` — `won_today: int`, `no_result_streak_days: int`, `overdue_count: int`, `calls_done: int`, `calls_target: int`, `follow_ups_done: int`, `follow_ups_target: int`, `meetings_done: int`, `meetings_target: int`, `biggest_stuck_deal_amount: int`, `biggest_stuck_deal_days: float`, `hot_lead_max_silent_hours: float`, `hot_band_dropped: bool`
  - `evaluate(metrics: SellerMetrics, findings: list[Finding], config: dict) -> TrafficResult`

Logic (RED wins; then YELLOW; else GREEN). Reasons are Uzbek one-liners.

RED if any:
- `won_today == 0 and no_result_streak_days >= traffic.red_no_result_days`
- `overdue_count >= traffic.red_overdue_count`
- `biggest_stuck_deal_amount >= traffic.big_deal_amount and biggest_stuck_deal_days >= traffic.stuck_deal_days`
- `len(findings) >= traffic.red_discipline_count`

YELLOW if any:
- `calls_done < yp*calls_target` OR `meetings_done < yp*meetings_target` (yp = `traffic.yellow_pace_pct`), for targets > 0
- `follow_ups_done < 0.5 * follow_ups_target` (target > 0)
- `hot_lead_max_silent_hours >= traffic.hot_lead_silent_hours`
- `hot_band_dropped`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_rop_traffic_light.py
from src.services.core.rop.config import DEFAULTS
from src.services.core.rop.traffic_light import evaluate, SellerMetrics, TrafficResult
from src.services.core.rop.discipline import Finding

CFG = dict(DEFAULTS)

def m(**over):
    base = dict(
        won_today=1, no_result_streak_days=0, overdue_count=0,
        calls_done=10, calls_target=10, follow_ups_done=20, follow_ups_target=20,
        meetings_done=2, meetings_target=2, biggest_stuck_deal_amount=0,
        biggest_stuck_deal_days=0.0, hot_lead_max_silent_hours=0.0, hot_band_dropped=False,
    )
    base.update(over)
    return SellerMetrics(**base)

def test_all_good_is_green():
    r = evaluate(m(), [], CFG)
    assert isinstance(r, TrafficResult) and r.level == "GREEN"

def test_no_result_streak_is_red():
    r = evaluate(m(won_today=0, no_result_streak_days=3), [], CFG)
    assert r.level == "RED"

def test_overdue_pile_is_red():
    assert evaluate(m(overdue_count=5), [], CFG).level == "RED"

def test_big_stuck_deal_is_red():
    r = evaluate(m(biggest_stuck_deal_amount=12_000_000, biggest_stuck_deal_days=15.0), [], CFG)
    assert r.level == "RED"

def test_discipline_pile_is_red():
    r = evaluate(m(), [Finding("L", "NO_NEXT_TASK", "")] * 8, CFG)
    assert r.level == "RED"

def test_low_pace_is_yellow():
    r = evaluate(m(calls_done=3, follow_ups_done=5, meetings_done=0), [], CFG)
    assert r.level == "YELLOW"

def test_silent_hot_lead_is_yellow():
    assert evaluate(m(hot_lead_max_silent_hours=50.0), [], CFG).level == "YELLOW"

def test_band_drop_is_yellow():
    assert evaluate(m(hot_band_dropped=True), [], CFG).level == "YELLOW"

def test_red_beats_yellow():
    r = evaluate(m(overdue_count=6, calls_done=0), [], CFG)
    assert r.level == "RED"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `SKIP_LIVE=1 python -m pytest tests/test_rop_traffic_light.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write `src/services/core/rop/traffic_light.py`**

```python
"""AI ROP CEO traffic light. Pure."""
from __future__ import annotations

from dataclasses import dataclass

from src.services.core.rop.discipline import Finding


@dataclass
class SellerMetrics:
    won_today: int
    no_result_streak_days: int
    overdue_count: int
    calls_done: int
    calls_target: int
    follow_ups_done: int
    follow_ups_target: int
    meetings_done: int
    meetings_target: int
    biggest_stuck_deal_amount: int
    biggest_stuck_deal_days: float
    hot_lead_max_silent_hours: float
    hot_band_dropped: bool


@dataclass(frozen=True)
class TrafficResult:
    level: str
    reasons: list[str]


def evaluate(metrics: SellerMetrics, findings: list[Finding], config: dict) -> TrafficResult:
    red: list[str] = []
    if metrics.won_today == 0 and metrics.no_result_streak_days >= config["traffic.red_no_result_days"]:
        red.append(f"{metrics.no_result_streak_days} ish kuni natijasiz")
    if metrics.overdue_count >= config["traffic.red_overdue_count"]:
        red.append(f"{metrics.overdue_count} ta muddati o'tgan task")
    if (metrics.biggest_stuck_deal_amount >= config["traffic.big_deal_amount"]
            and metrics.biggest_stuck_deal_days >= config["traffic.stuck_deal_days"]):
        red.append("Katta bitim uzoq vaqt qotib qolgan")
    if len(findings) >= config["traffic.red_discipline_count"]:
        red.append(f"{len(findings)} ta CRM intizom buzilishi")
    if red:
        return TrafficResult("RED", red)

    yellow: list[str] = []
    yp = config["traffic.yellow_pace_pct"]
    if metrics.calls_target > 0 and metrics.calls_done < yp * metrics.calls_target:
        yellow.append("Qo'ng'iroqlar sur'ati past")
    if metrics.meetings_target > 0 and metrics.meetings_done < yp * metrics.meetings_target:
        yellow.append("Uchrashuvlar sur'ati past")
    if metrics.follow_ups_target > 0 and metrics.follow_ups_done < 0.5 * metrics.follow_ups_target:
        yellow.append("Follow-up orqada")
    if metrics.hot_lead_max_silent_hours >= config["traffic.hot_lead_silent_hours"]:
        yellow.append("Issiq mijoz javobsiz qolgan")
    if metrics.hot_band_dropped:
        yellow.append("Issiq bitim ehtimoli tushdi")
    if yellow:
        return TrafficResult("YELLOW", yellow)

    return TrafficResult("GREEN", [])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `SKIP_LIVE=1 python -m pytest tests/test_rop_traffic_light.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add src/services/core/rop/traffic_light.py tests/test_rop_traffic_light.py
git commit -m "feat(rop): CEO traffic-light evaluation

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 8: `daily.py` — per-seller + CEO models

**Files:**
- Create: `src/services/core/rop/daily.py`
- Create: `tests/test_rop_daily.py`

**Interfaces:**
- Consumes: `SellerTarget` (Task 3), `ScoreResult` + `score_lead` + `derive_features` (Task 4), `Finding` (Task 5), `SellerMetrics` + `evaluate` + `TrafficResult` (Task 7), `WeeklyProgress` (Task 6)
- Produces (all `@dataclass(frozen=True)`):
  - `LeadScore` — `lead_id: int`, `name: str`, `price: int`, `score: int`, `band: str`, `reasons: list[str]`, `action: str`
  - `ExpectedItem` — `name: str`, `revenue_est: int`, `score: int`
  - `SellerMorningPlan` — `seller: SellerTarget`, `top_closings: list[LeadScore]`, `open_tasks_count: int`, `overdue_tasks: list[tuple[str, str]]`, `followup_due: list[str]`, `expected: list[ExpectedItem]`, `expected_revenue_total: int`, `discipline_findings: list[Finding]`
  - `SellerMiddayCheck` — `seller`, `plan: int`, `fakt: int`, `calls_done: int`, `follow_ups_done: int`, `meetings_done: int`, `hot_not_touched: list[str]`, `priority_now: list[LeadScore]`, `on_track: bool`
  - `SellerEveningResult` — `seller`, `sales_done: int`, `revenue_today: int`, `calls_done: int`, `follow_ups_done: int`, `meetings_done: int`, `overdue_count: int`, `tomorrow_closings: list[LeadScore]`
  - `CeoMorning` — `total_expected_sales: int`, `total_expected_revenue: int`, `total_overdue: int`, `seller_count: int`, `missing_tg: list[str]`, `no_owner: list[str]`, `weekly_recap: WeeklyProgress | None`
  - `CeoMidday` — `off_track: list[tuple[str, str]]`, `any_alert: bool`
  - `CeoDashboard` — `team_plan: int`, `team_fakt: int`, `team_revenue: int`, `expected_tomorrow: int`, `team_overdue: int`, `weekly: WeeklyProgress`, `seller_lights: list[tuple[str, str, list[str]]]`, `skipped_sellers: int`
  - Builders:
    - `score_seller_leads(leads, tasks_by_lead, notes_by_lead, events_by_lead, config, now) -> list[LeadScore]` (sorted by score desc)
    - `build_morning(seller, seller_leads_scored, tasks_by_lead, findings, config, now) -> SellerMorningPlan`
    - `build_midday(seller, seller_leads_scored, actuals, touched_lead_ids, config) -> SellerMiddayCheck` — `actuals` is `dict(calls=int, follow_ups=int, meetings=int, won=int)`
    - `build_evening(seller, seller_leads_scored, actuals, overdue_count) -> SellerEveningResult`
    - `build_ceo_morning(morning_plans, no_owner_findings, weekly_recap) -> CeoMorning`
    - `build_ceo_midday(midday_checks, traffic_results) -> CeoMidday`
    - `build_ceo_dashboard(evening_results, traffic_results, weekly, expected_tomorrow, skipped) -> CeoDashboard`
  - `pick_action(reasons: list[str]) -> str` — maps dominant reason → one of `"bugun qo'ng'iroq"`, `"follow-up"`, `"narx objection yop"`, `"uchrashuv belgila"`.

`on_track` rule: `all(done >= midday.pace_pct * target for tracked buckets with target > 0) and not hot_not_touched`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_rop_daily.py
from datetime import datetime, timezone
from src.services.core.rop.config import DEFAULTS
from src.services.core.rop.targets import SellerTarget
from src.services.core.rop.daily import (
    score_seller_leads, build_morning, build_midday, build_evening,
    build_ceo_dashboard, pick_action, LeadScore,
)
from src.services.core.rop.traffic_light import TrafficResult

CFG = dict(DEFAULTS)
CFG["score.stage_weights"] = {"200": 0.85, "100": 0.15}
NOW = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
E = int(NOW.timestamp())
SELLER = SellerTarget(101, "Oydin", 555, 1, 10, 20, 2, 0, 1, 0)

def _leads():
    return [
        {"id": 1, "name": "ABC", "status_id": 200, "price": 12_000_000,
         "responsible_user_id": 101, "updated_at": E - 3600, "created_at": E - 5 * 86400},
        {"id": 2, "name": "XYZ", "status_id": 100, "price": 4_000_000,
         "responsible_user_id": 101, "updated_at": E - 200 * 3600, "created_at": E - 40 * 86400},
    ]

def test_score_seller_leads_sorted_desc():
    scored = score_seller_leads(_leads(), {1: [], 2: []}, {1: [], 2: []}, {1: [], 2: []}, CFG, NOW)
    assert [s.name for s in scored] == ["ABC", "XYZ"]
    assert scored[0].score > scored[1].score
    assert isinstance(scored[0], LeadScore)

def test_build_morning_expected_and_top():
    scored = score_seller_leads(_leads(), {1: [], 2: []}, {1: [], 2: []}, {1: [], 2: []}, CFG, NOW)
    mp = build_morning(SELLER, scored, {1: [], 2: []}, [], CFG, NOW)
    assert mp.top_closings[0].name == "ABC"
    assert mp.expected_revenue_total >= 1
    assert any(e.name == "ABC" for e in mp.expected)

def test_build_midday_on_track_suppression_logic():
    scored = score_seller_leads(_leads(), {1: [], 2: []}, {1: [], 2: []}, {1: [], 2: []}, CFG, NOW)
    good = build_midday(SELLER, scored, dict(calls=5, follow_ups=8, meetings=1, won=0), {1, 2}, CFG)
    assert good.on_track is True
    bad = build_midday(SELLER, scored, dict(calls=1, follow_ups=1, meetings=0, won=0), set(), CFG)
    assert bad.on_track is False
    assert "ABC" in bad.hot_not_touched

def test_build_evening_fields():
    scored = score_seller_leads(_leads(), {1: [], 2: []}, {1: [], 2: []}, {1: [], 2: []}, CFG, NOW)
    ev = build_evening(SELLER, scored, dict(calls=9, follow_ups=18, meetings=2, won=1), overdue_count=0)
    assert ev.sales_done == 1 and ev.calls_done == 9
    assert len(ev.tomorrow_closings) >= 1

def test_pick_action_maps_reason():
    assert pick_action(["To'lov va'da qilingan"]) in {"bugun qo'ng'iroq", "follow-up"}
    assert pick_action(["Ochiq e'tiroz bor"]) == "narx objection yop"
    assert pick_action(["72 soatdan beri aloqa yo'q"]) == "follow-up"
    assert pick_action([]) == "follow-up"

def test_build_ceo_dashboard_aggregates():
    scored = score_seller_leads(_leads(), {1: [], 2: []}, {1: [], 2: []}, {1: [], 2: []}, CFG, NOW)
    ev = build_evening(SELLER, scored, dict(calls=9, follow_ups=18, meetings=2, won=1), 0)
    from src.services.core.rop.weekly import progress
    wk = progress([{"status_id": 142, "price": 12_000_000}], CFG)
    dash = build_ceo_dashboard([ev], {101: TrafficResult("GREEN", [])}, wk, expected_tomorrow=5_000_000, skipped=0)
    assert dash.team_fakt == 1
    assert dash.team_revenue == 12_000_000  # wait: evening revenue_today, see note
```

> Implementer note: `revenue_today` in `build_evening` is not supplied by `actuals` above — add `won_revenue` to the `actuals` dict (`dict(calls=, follow_ups=, meetings=, won=, won_revenue=)`) and update the two evening tests to pass `won_revenue=12_000_000`. Fix the test and signature together in Step 3; keep them consistent.

- [ ] **Step 2: Run test to verify it fails**

Run: `SKIP_LIVE=1 python -m pytest tests/test_rop_daily.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write `src/services/core/rop/daily.py`**

```python
"""AI ROP per-seller + CEO view models and builders. Pure; injected `now`."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from src.services.core.rop.config import DEFAULTS  # noqa: F401 (kept for parity)
from src.services.core.rop.discipline import Finding
from src.services.core.rop.scoring import derive_features, score_lead
from src.services.core.rop.targets import SellerTarget
from src.services.core.rop.traffic_light import TrafficResult
from src.services.core.rop.weekly import WeeklyProgress

_ACTION_BY_REASON = [
    ("Ochiq e'tiroz bor", "narx objection yop"),
    ("Uchrashuv", "uchrashuv belgila"),
    ("To'lov va'da qilingan", "bugun qo'ng'iroq"),
    ("Bosqich yakuniga yaqin", "bugun qo'ng'iroq"),
]


def pick_action(reasons: list[str]) -> str:
    for needle, action in _ACTION_BY_REASON:
        if any(needle in r for r in reasons):
            return action
    return "follow-up"


@dataclass(frozen=True)
class LeadScore:
    lead_id: int
    name: str
    price: int
    score: int
    band: str
    reasons: list[str]
    action: str


@dataclass(frozen=True)
class ExpectedItem:
    name: str
    revenue_est: int
    score: int


@dataclass(frozen=True)
class SellerMorningPlan:
    seller: SellerTarget
    top_closings: list[LeadScore]
    open_tasks_count: int
    overdue_tasks: list[tuple[str, str]]
    followup_due: list[str]
    expected: list[ExpectedItem]
    expected_revenue_total: int
    discipline_findings: list[Finding]


@dataclass(frozen=True)
class SellerMiddayCheck:
    seller: SellerTarget
    plan: int
    fakt: int
    calls_done: int
    follow_ups_done: int
    meetings_done: int
    hot_not_touched: list[str]
    priority_now: list[LeadScore]
    on_track: bool


@dataclass(frozen=True)
class SellerEveningResult:
    seller: SellerTarget
    sales_done: int
    revenue_today: int
    calls_done: int
    follow_ups_done: int
    meetings_done: int
    overdue_count: int
    tomorrow_closings: list[LeadScore]


@dataclass(frozen=True)
class CeoMorning:
    total_expected_sales: int
    total_expected_revenue: int
    total_overdue: int
    seller_count: int
    missing_tg: list[str]
    no_owner: list[str]
    weekly_recap: WeeklyProgress | None


@dataclass(frozen=True)
class CeoMidday:
    off_track: list[tuple[str, str]]
    any_alert: bool


@dataclass(frozen=True)
class CeoDashboard:
    team_plan: int
    team_fakt: int
    team_revenue: int
    expected_tomorrow: int
    team_overdue: int
    weekly: WeeklyProgress
    seller_lights: list[tuple[str, str, list[str]]]
    skipped_sellers: int


def score_seller_leads(
    leads, tasks_by_lead, notes_by_lead, events_by_lead, config, now: datetime
) -> list[LeadScore]:
    out: list[LeadScore] = []
    for lead in leads:
        lid = lead.get("id")
        feats = derive_features(
            lead,
            tasks_by_lead.get(lid, []),
            notes_by_lead.get(lid, []),
            events_by_lead.get(lid, []),
            config,
            now,
        )
        res = score_lead(feats, config)
        out.append(
            LeadScore(
                lead_id=lid,
                name=lead.get("name") or f"Lead {lid}",
                price=int(lead.get("price") or 0),
                score=res.score,
                band=res.band,
                reasons=res.reasons,
                action=pick_action(res.reasons),
            )
        )
    out.sort(key=lambda s: s.score, reverse=True)
    return out


def _expected(scored: list[LeadScore]) -> tuple[list[ExpectedItem], int]:
    items = [
        ExpectedItem(s.name, int(s.price * s.score / 100), s.score)
        for s in scored
        if s.band in ("HOT", "WARM")
    ]
    return items, sum(i.revenue_est for i in items)


def build_morning(seller, scored, tasks_by_lead, findings, config, now) -> SellerMorningPlan:
    now_epoch = now.timestamp()
    overdue: list[tuple[str, str]] = []
    followup_due: list[str] = []
    open_count = 0
    by_id = {s.lead_id: s for s in scored}
    for lid, tasks in tasks_by_lead.items():
        for t in tasks:
            if t.get("is_completed"):
                continue
            open_count += 1
            name = by_id[lid].name if lid in by_id else f"Lead {lid}"
            ct = t.get("complete_till") or 0
            if ct and float(ct) < now_epoch:
                overdue.append((name, str(t.get("text") or "")))
            elif ct and float(ct) <= now_epoch + 86400:
                followup_due.append(name)
    exp, exp_total = _expected(scored)
    return SellerMorningPlan(
        seller=seller,
        top_closings=scored[:3],
        open_tasks_count=open_count,
        overdue_tasks=overdue,
        followup_due=followup_due,
        expected=exp,
        expected_revenue_total=exp_total,
        discipline_findings=findings,
    )


def build_midday(seller, scored, actuals, touched_lead_ids, config) -> SellerMiddayCheck:
    pace = config["midday.pace_pct"]
    hot_not_touched = [
        s.name for s in scored if s.band == "HOT" and s.lead_id not in touched_lead_ids
    ]
    priority_now = [s for s in scored if s.lead_id not in touched_lead_ids][:3]
    buckets = [
        (actuals["calls"], seller.calls),
        (actuals["follow_ups"], seller.follow_ups),
        (actuals["meetings"], seller.meetings),
    ]
    on_track = all(
        done >= pace * target for done, target in buckets if target > 0
    ) and not hot_not_touched
    return SellerMiddayCheck(
        seller=seller,
        plan=seller.expected_sales,
        fakt=actuals["won"],
        calls_done=actuals["calls"],
        follow_ups_done=actuals["follow_ups"],
        meetings_done=actuals["meetings"],
        hot_not_touched=hot_not_touched,
        priority_now=priority_now,
        on_track=on_track,
    )


def build_evening(seller, scored, actuals, overdue_count) -> SellerEveningResult:
    return SellerEveningResult(
        seller=seller,
        sales_done=actuals["won"],
        revenue_today=int(actuals.get("won_revenue") or 0),
        calls_done=actuals["calls"],
        follow_ups_done=actuals["follow_ups"],
        meetings_done=actuals["meetings"],
        overdue_count=overdue_count,
        tomorrow_closings=scored[:3],
    )


def build_ceo_morning(morning_plans, no_owner_findings, weekly_recap) -> CeoMorning:
    return CeoMorning(
        total_expected_sales=sum(1 for mp in morning_plans for _ in mp.expected if _.score >= 70),
        total_expected_revenue=sum(mp.expected_revenue_total for mp in morning_plans),
        total_overdue=sum(len(mp.overdue_tasks) for mp in morning_plans),
        seller_count=len(morning_plans),
        missing_tg=[mp.seller.seller_name for mp in morning_plans if mp.seller.telegram_user_id is None],
        no_owner=[f.lead_name for f in no_owner_findings],
        weekly_recap=weekly_recap,
    )


def build_ceo_midday(midday_checks, traffic_results) -> CeoMidday:
    off = []
    for c in midday_checks:
        if c.on_track:
            continue
        why = "sur'at past"
        if c.hot_not_touched:
            why = f"{len(c.hot_not_touched)} ta issiq mijoz ishlanmagan"
        off.append((c.seller.seller_name, why))
    any_alert = bool(off) or any(
        t.level in ("YELLOW", "RED") for t in traffic_results.values()
    )
    return CeoMidday(off_track=off, any_alert=any_alert)


def build_ceo_dashboard(
    evening_results, traffic_results, weekly, expected_tomorrow, skipped
) -> CeoDashboard:
    lights = []
    for ev in evening_results:
        tr = traffic_results.get(ev.seller.responsible_user_id, TrafficResult("GREEN", []))
        emoji = {"GREEN": "🟢", "YELLOW": "🟡", "RED": "🔴"}[tr.level]
        lights.append((ev.seller.seller_name, emoji, tr.reasons))
    return CeoDashboard(
        team_plan=sum(ev.seller.expected_sales for ev in evening_results),
        team_fakt=sum(ev.sales_done for ev in evening_results),
        team_revenue=sum(ev.revenue_today for ev in evening_results),
        expected_tomorrow=expected_tomorrow,
        team_overdue=sum(ev.overdue_count for ev in evening_results),
        weekly=weekly,
        seller_lights=lights,
        skipped_sellers=skipped,
    )
```

- [ ] **Step 4: Fix the evening tests for `won_revenue`**

In `tests/test_rop_daily.py`, change the two `build_evening` calls to include `won_revenue=12_000_000` and adjust `test_build_ceo_dashboard_aggregates` to assert `dash.team_revenue == 12_000_000`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `SKIP_LIVE=1 python -m pytest tests/test_rop_daily.py -v`
Expected: PASS (6 tests)

- [ ] **Step 6: Commit**

```bash
git add src/services/core/rop/daily.py tests/test_rop_daily.py
git commit -m "feat(rop): per-seller + CEO daily view models and builders

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 9: `rop_messages.py` — Uzbek HTML renderers

**Files:**
- Create: `src/services/core/rop/rop_messages.py`
- Create: `tests/test_rop_messages.py`

**Interfaces:**
- Consumes: every dataclass from `daily.py`, `DISCLAIMER` from `scoring.py`, `WeeklyProgress`
- Produces (each returns an HTML `str`):
  - `render_seller_morning(plan: SellerMorningPlan) -> str`
  - `render_seller_midday(check: SellerMiddayCheck) -> str`  (caller only sends if `not check.on_track`)
  - `render_seller_evening(result: SellerEveningResult) -> str`
  - `render_ceo_morning(m: CeoMorning) -> str`
  - `render_ceo_midday(m: CeoMidday) -> str`
  - `render_ceo_dashboard(d: CeoDashboard) -> str`
  - `render_empty_roster_notice() -> str`
  - `progress_bar(pct: float, width: int = 10) -> str` — `"█"*fill + "░"*(width-fill)`, `fill = round(min(pct,100)/100*width)`
  - `fmt_sum(n: int) -> str` — thousands separated by spaces, e.g. `12 000 000`

Constraints: escape every interpolated lead/seller name with `html.escape`. Keep each message ≤ ~1200 chars; truncate lists to 5 items + `"+N ta yana"`. Every message that shows a score/expected value must include `DISCLAIMER`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_rop_messages.py
from datetime import datetime, timezone
from src.services.core.rop.targets import SellerTarget
from src.services.core.rop.scoring import DISCLAIMER
from src.services.core.rop.daily import (
    SellerMorningPlan, SellerMiddayCheck, SellerEveningResult,
    CeoMorning, CeoMidday, CeoDashboard, LeadScore, ExpectedItem,
)
from src.services.core.rop.discipline import Finding
from src.services.core.rop.weekly import WeeklyProgress
from src.services.core.rop.rop_messages import (
    render_seller_morning, render_seller_midday, render_seller_evening,
    render_ceo_morning, render_ceo_midday, render_ceo_dashboard,
    render_empty_roster_notice, progress_bar, fmt_sum,
)

SELLER = SellerTarget(101, "Oydin", 555, 1, 10, 20, 2, 0, 1, 0)
LS = LeadScore(1, "ABC & Co", 12_000_000, 82, "HOT", ["KP yuborilgan"], "bugun qo'ng'iroq")
WK = WeeklyProgress(6, 60_000_000, 10, 100_000_000, 60.0, 60.0)

def test_fmt_sum_spaces():
    assert fmt_sum(12000000) == "12 000 000"

def test_progress_bar_shape():
    b = progress_bar(60.0)
    assert len(b) == 10 and b.count("█") == 6

def test_seller_morning_has_disclaimer_and_escapes():
    plan = SellerMorningPlan(SELLER, [LS], 3, [("ABC & Co", "Qo'ng'iroq")],
                             ["ABC & Co"], [ExpectedItem("ABC & Co", 9_800_000, 82)],
                             9_800_000, [Finding("ABC & Co", "NO_NEXT_TASK", "")])
    html = render_seller_morning(plan)
    assert DISCLAIMER in html
    assert "ABC &amp; Co" in html and "ABC & Co" not in html.replace("ABC &amp; Co", "")

def test_seller_midday_renders():
    c = SellerMiddayCheck(SELLER, 1, 0, 3, 7, 1, ["ABC & Co"], [LS], False)
    html = render_seller_midday(c)
    assert "7/20" in html or "7 / 20" in html

def test_seller_evening_renders():
    r = SellerEveningResult(SELLER, 1, 12_500_000, 9, 18, 2, 0, [LS])
    html = render_seller_evening(r)
    assert "1/1" in html or "1 / 1" in html

def test_ceo_morning_renders():
    m = CeoMorning(2, 17_000_000, 3, 4, ["Dilnoza"], ["NoOwnerLead"], WK)
    html = render_ceo_morning(m)
    assert "Dilnoza" in html

def test_ceo_midday_renders():
    html = render_ceo_midday(CeoMidday([("Oydin", "sur'at past")], True))
    assert "Oydin" in html

def test_ceo_dashboard_renders_lights_and_weekly():
    d = CeoDashboard(2, 2, 25_000_000, 18_000_000, 0, WK,
                     [("Oydin", "🟢", []), ("Dilnoza", "🔴", ["3 ish kuni natijasiz"])], 0)
    html = render_ceo_dashboard(d)
    assert "🔴" in html and "3 ish kuni natijasiz" in html
    assert "6" in html  # weekly won count

def test_empty_roster_notice():
    assert "sozlanmagan" in render_empty_roster_notice()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `SKIP_LIVE=1 python -m pytest tests/test_rop_messages.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write `src/services/core/rop/rop_messages.py`**

```python
"""AI ROP message templates — Uzbek (Latin), HTML, deterministic. No LLM."""
from __future__ import annotations

from html import escape

from src.services.core.rop.daily import (
    CeoDashboard, CeoMidday, CeoMorning, SellerEveningResult, SellerMiddayCheck,
    SellerMorningPlan,
)
from src.services.core.rop.scoring import DISCLAIMER
from src.services.core.rop.weekly import WeeklyProgress

_BAND_UZ = {"HOT": "issiq", "WARM": "iliq", "COLD": "sovuq"}
_MAX_LIST = 5


def fmt_sum(n: int) -> str:
    return f"{int(n):,}".replace(",", " ")


def progress_bar(pct: float, width: int = 10) -> str:
    fill = round(min(max(pct, 0.0), 100.0) / 100 * width)
    return "█" * fill + "░" * (width - fill)


def _trim(items: list[str]) -> list[str]:
    if len(items) <= _MAX_LIST:
        return items
    return items[:_MAX_LIST] + [f"+{len(items) - _MAX_LIST} ta yana"]


def _weekly_line(w: WeeklyProgress) -> str:
    return (
        f"Haftalik: {w.won_count}/{w.sales_target} sotuv "
        f"({w.sales_pct:.0f}%)  [{progress_bar(w.sales_pct)}]\n"
        f"Revenue: {fmt_sum(w.won_revenue)} / {fmt_sum(w.revenue_target)} so'm"
    )


def render_seller_morning(plan: SellerMorningPlan) -> str:
    s = plan.seller
    lines = [f"<b>Bugungi plan — {s.expected_sales} ta sotuv</b>", ""]
    if plan.top_closings:
        lines.append("🔥 <b>Closingga eng yaqin:</b>")
        for i, ls in enumerate(plan.top_closings, 1):
            reason = ls.reasons[0] if ls.reasons else _BAND_UZ.get(ls.band, "")
            lines.append(
                f"{i}. {escape(ls.name)} — {escape(reason)} → <i>{escape(ls.action)}</i>"
            )
        lines.append("")
    lines.append("<b>Bugun:</b>")
    lines.append(f"• {s.calls} ta qo'ng'iroq")
    lines.append(f"• {s.follow_ups} ta follow-up")
    lines.append(f"• {s.meetings} ta uchrashuv")
    lines.append(f"• {s.payments} ta to'lov")
    lines.append("")
    if plan.expected:
        lines.append("<b>Bugun kutilyapti:</b>")
        for e in _trim([
            f"{escape(e.name)} — {fmt_sum(e.revenue_est)} so'm — {e.score}%"
            for e in plan.expected
        ]):
            lines.append(f"• {e}")
        lines.append(f"Expected revenue: {fmt_sum(plan.expected_revenue_total)} so'm")
        lines.append(f"<i>{DISCLAIMER}</i>")
        lines.append("")
    if plan.overdue_tasks:
        lines.append(f"⚠️ <b>Overdue: {len(plan.overdue_tasks)} ta task</b>")
        for name, txt in plan.overdue_tasks[:_MAX_LIST]:
            lines.append(f"• {escape(name)}: {escape(txt)}")
        if len(plan.overdue_tasks) > _MAX_LIST:
            lines.append(f"+{len(plan.overdue_tasks) - _MAX_LIST} ta yana")
    if plan.discipline_findings:
        lines.append("")
        lines.append("⚠️ <b>CRM intizomi:</b>")
        seen = _trim([
            f"{escape(f.lead_name)} — {escape(_FINDING_UZ.get(f.type, f.type))}"
            for f in plan.discipline_findings
        ])
        for x in seen:
            lines.append(f"• {x}")
    return "\n".join(lines)


_FINDING_UZ = {
    "NO_NEXT_TASK": "keyingi task yo'q",
    "OVERDUE_TASK": "muddati o'tgan task",
    "STAGNANT": "uzoq vaqt harakatsiz",
    "NO_OWNER": "mas'ul biriktirilmagan",
    "WRONG_STAGE": "noto'g'ri bosqich",
    "IMPORTANT_NO_NOTE": "muhim aloqadan keyin izoh yo'q",
}


def render_seller_midday(check: SellerMiddayCheck) -> str:
    s = check.seller
    lines = [
        "<b>Tushki tekshiruv</b>",
        "",
        f"Plan: {check.plan}",
        f"Fakt: {check.fakt}",
        "",
        f"{check.calls_done}/{s.calls} qo'ng'iroq",
        f"{check.follow_ups_done}/{s.follow_ups} follow-up",
        f"{check.meetings_done}/{s.meetings} uchrashuv",
    ]
    if check.hot_not_touched:
        lines.append("")
        lines.append(f"Hali ishlanmagan {len(check.hot_not_touched)} ta issiq mijoz:")
        for n in check.hot_not_touched[:_MAX_LIST]:
            lines.append(f"• {escape(n)}")
    if check.priority_now:
        lines.append("")
        lines.append("<b>Hozirgi prioritet:</b>")
        for i, ls in enumerate(check.priority_now, 1):
            lines.append(f"{i}. {escape(ls.name)} — <i>{escape(ls.action)}</i>")
    return "\n".join(lines)


def render_seller_evening(result: SellerEveningResult) -> str:
    s = result.seller
    lines = [
        "<b>Bugungi natija</b>",
        "",
        f"Sales: {result.sales_done}/{s.expected_sales}",
        f"Revenue: {fmt_sum(result.revenue_today)} so'm",
        f"Calls: {result.calls_done}/{s.calls}",
        f"Follow-ups: {result.follow_ups_done}/{s.follow_ups}",
        f"Meetings: {result.meetings_done}/{s.meetings}",
        f"Overdue: {result.overdue_count}",
    ]
    if result.tomorrow_closings:
        lines.append("")
        lines.append("Ertaga closingga yaqin:")
        for ls in result.tomorrow_closings:
            lines.append(f"• {escape(ls.name)}")
    return "\n".join(lines)


def render_ceo_morning(m: CeoMorning) -> str:
    lines = ["🟢 <b>Sales Department — ertalabki holat</b>", ""]
    if m.weekly_recap is not None:
        lines.append("<b>O'tgan hafta yakuni:</b>")
        lines.append(_weekly_line(m.weekly_recap))
        lines.append("")
    lines.append(f"Sotuvchilar: {m.seller_count}")
    lines.append(f"Bugun kutilayotgan sotuv: {m.total_expected_sales}")
    lines.append(f"Kutilayotgan revenue: {fmt_sum(m.total_expected_revenue)} so'm")
    lines.append(f"Overdue: {m.total_overdue}")
    lines.append(f"<i>{DISCLAIMER}</i>")
    if m.no_owner:
        lines.append("")
        lines.append("⚠️ Mas'ulsiz bitimlar:")
        for n in _trim([escape(x) for x in m.no_owner]):
            lines.append(f"• {n}")
    if m.missing_tg:
        lines.append("")
        lines.append("Telegram ID yo'q: " + ", ".join(escape(x) for x in m.missing_tg))
    return "\n".join(lines)


def render_ceo_midday(m: CeoMidday) -> str:
    if not m.off_track:
        return "🟢 Sales Department — hammasi rejada"
    lines = ["🟡 <b>Sales Department — tushki nazorat</b>", ""]
    for name, why in m.off_track:
        lines.append(f"• {escape(name)} — {escape(why)}")
    return "\n".join(lines)


def render_ceo_dashboard(d: CeoDashboard) -> str:
    lines = [
        "<b>Sales Department</b>",
        "",
        f"Plan: {d.team_plan}",
        f"Fakt: {d.team_fakt}",
        f"Revenue: {fmt_sum(d.team_revenue)} so'm",
        f"Expected tomorrow: {fmt_sum(d.expected_tomorrow)} so'm",
        f"Overdue: {d.team_overdue}",
        "",
        _weekly_line(d.weekly),
        "",
        "<b>Sotuvchilar:</b>",
    ]
    for name, emoji, reasons in d.seller_lights:
        if reasons:
            lines.append(f"{emoji} {escape(name)} — {escape(reasons[0])}")
        else:
            lines.append(f"{emoji} {escape(name)}")
    if d.skipped_sellers:
        lines.append("")
        lines.append(f"<i>{d.skipped_sellers} sotuvchi o'tkazib yuborildi (xatolik).</i>")
    lines.append("")
    lines.append(f"<i>{DISCLAIMER}</i>")
    return "\n".join(lines)


def render_empty_roster_notice() -> str:
    return "ROP: hech qanday sotuvchi sozlanmagan."
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `SKIP_LIVE=1 python -m pytest tests/test_rop_messages.py -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Commit**

```bash
git add src/services/core/rop/rop_messages.py tests/test_rop_messages.py
git commit -m "feat(rop): Uzbek HTML message templates

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 10: `fetchers.py` — bounded AmoCRM reads

**Files:**
- Create: `src/services/core/rop/fetchers.py`
- Create: `tests/test_rop_fetchers.py`

**Interfaces:**
- Consumes: an AmoCRM client object exposing `base_url: str` and `_get_headers() -> dict` (this is `app_ctx.msg_controller.crm.amocrm`; the scorecard mixin uses the same two members). Uses `requests.get` wrapped in `asyncio.to_thread`.
- Produces `class RopFetcher`:
  - `__init__(self, amocrm, *, session=None)` — `session` overridable for tests (defaults to `requests`)
  - `async fetch_active_sales_leads() -> list[dict]` — GET `/api/v4/leads`, `filter[pipeline_id]=SALES_PIPELINE_ID`, `with=contacts`, `limit=250`, follow `_page.next` up to 4 pages; drop leads with `status_id in (STATUS_WON, STATUS_LOST)`
  - `async fetch_open_tasks_for_leads(lead_ids: list[int]) -> dict[int, list[dict]]` — GET `/api/v4/tasks`, `filter[entity_type]=leads`, `filter[is_completed]=0`, `limit=250`, up to 4 pages; group by `entity_id`
  - `async fetch_today_completed_tasks(user_ids: list[int]) -> tuple[dict[int, list[dict]], dict[int, list[dict]]]` — GET `/api/v4/tasks`, `filter[is_completed]=1`, `filter[updated_at][from]=<Tashkent today 00:00 epoch>`, `limit=250`, up to 4 pages; returns `(by_entity_id, by_responsible_user_id)`; keep only `responsible_user_id in user_ids`
  - `async fetch_today_events(lead_ids: list[int]) -> dict[int, list[dict]]` — GET `/api/v4/events`, `filter[entity]=lead`, `filter[created_at][from]=<today 00:00 epoch>`, `limit=100`, up to 3 pages; group by `entity_id`
  - `async fetch_recent_events(lead_ids: list[int], since_epoch: int) -> dict[int, list[dict]]` — GET `/api/v4/events`, `filter[entity]=lead`, `filter[created_at][from]=since_epoch`, `filter[type]=lead_status_changed`, `limit=250`, up to 4 pages; group by `entity_id`
  - `async fetch_won_leads_since(since_epoch: int) -> list[dict]` — GET `/api/v4/leads`, `filter[pipeline_id]=SALES_PIPELINE_ID`, `filter[statuses][0][status_id]=STATUS_WON`, `filter[closed_at][from]=since_epoch`, `limit=250`, up to 4 pages
  - `async fetch_notes_for_leads(lead_ids: list[int]) -> dict[int, list[dict]]` — GET `/api/v4/leads/notes`, `limit=250`, up to 4 pages, `filter[entity_id]` batched ≤ 50 ids per request; group by `entity_id`. **Cap total requests at 6** — if more than 300 lead ids, only fetch notes for the first 300 (sorted by lead `updated_at` desc; caller passes a pre-trimmed list).
  - `async fetch_user_names(user_ids: list[int]) -> dict[int, str]` — GET `/api/v4/users/{id}` per id (cap 30); on failure map to `f"Menejer_{id}"`
- Helper `_tashkent_day_start_epoch(now: datetime) -> int` (module-level, exported for the scheduler/service).
- Every method swallows non-200 / exceptions per-request, logs a WARN, and returns what it has (never raises). **Exception:** `fetch_active_sales_leads` re-raises a custom `RopFetchError` if the **first** page request fails or returns non-200 — the service uses this to abort the whole slot.

Notes:
- `_page.next` link: AmoCRM v4 responses carry `{"_links": {"next": {"href": "..."}}}`. Loop while a `next` href exists and page count < cap; pass the href straight to `session.get`.
- Bounded totals: active-leads ≤4, open-tasks ≤4, completed-tasks ≤4, today-events ≤3, recent-events ≤4 (evening/Monday only), won-leads ≤4 (evening/Monday only), notes ≤6, user-names ≤30. Morning ≈ 21 worst-case; document this in a module docstring. (The spec's "≤5 requests/run" was optimistic for the notes/name lookups; the realistic ceiling is ~25 and still well within AmoCRM's 7 req/s limit since calls are sequential.)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_rop_fetchers.py
from datetime import datetime, timezone
import pytest
from src.services.core.rop.fetchers import RopFetcher, RopFetchError, _tashkent_day_start_epoch
from src.services.core.crm.amocrm_pipeline_config import STATUS_WON, STATUS_LOST


class FakeResp:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload
    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, script):
        # script: list of (url_substr, FakeResp)
        self.script = script
        self.calls = []
    def get(self, url, headers=None, params=None, timeout=None):
        self.calls.append((url, params))
        for sub, resp in self.script:
            if sub in url and not getattr(resp, "_used", False):
                resp._used = True
                return resp
        return FakeResp(200, {"_embedded": {}})


class FakeAmo:
    base_url = "https://x.amocrm.ru"
    def _get_headers(self):
        return {}


@pytest.mark.asyncio
async def test_active_leads_filters_terminal_and_counts_requests():
    payload = {"_embedded": {"leads": [
        {"id": 1, "status_id": 111},
        {"id": 2, "status_id": STATUS_WON},
        {"id": 3, "status_id": STATUS_LOST},
    ]}}
    sess = FakeSession([("/api/v4/leads", FakeResp(200, payload))])
    f = RopFetcher(FakeAmo(), session=sess)
    leads = await f.fetch_active_sales_leads()
    assert [l["id"] for l in leads] == [1]
    assert len(sess.calls) == 1

@pytest.mark.asyncio
async def test_active_leads_first_page_failure_raises():
    sess = FakeSession([("/api/v4/leads", FakeResp(500, {}))])
    f = RopFetcher(FakeAmo(), session=sess)
    with pytest.raises(RopFetchError):
        await f.fetch_active_sales_leads()

@pytest.mark.asyncio
async def test_completed_tasks_filtered_by_user_and_grouped():
    payload = {"_embedded": {"tasks": [
        {"id": 9, "entity_id": 1, "responsible_user_id": 101, "task_type_id": 1, "is_completed": True},
        {"id": 10, "entity_id": 2, "responsible_user_id": 999, "task_type_id": 1, "is_completed": True},
    ]}}
    sess = FakeSession([("/api/v4/tasks", FakeResp(200, payload))])
    f = RopFetcher(FakeAmo(), session=sess)
    by_entity, by_user = await f.fetch_today_completed_tasks([101])
    assert 1 in by_entity and 2 not in by_entity
    assert 101 in by_user and 999 not in by_user

@pytest.mark.asyncio
async def test_non_200_returns_empty_not_raise():
    sess = FakeSession([("/api/v4/events", FakeResp(403, {}))])
    f = RopFetcher(FakeAmo(), session=sess)
    assert await f.fetch_today_events([1, 2]) == {}

def test_tashkent_day_start_epoch():
    now = datetime(2026, 9, 10, 15, 0, tzinfo=timezone.utc)  # 20:00 Tashkent
    start = _tashkent_day_start_epoch(now)
    # 2026-09-10 00:00 Tashkent == 2026-09-09 19:00 UTC
    assert start == int(datetime(2026, 9, 9, 19, 0, tzinfo=timezone.utc).timestamp())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `SKIP_LIVE=1 python -m pytest tests/test_rop_fetchers.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write `src/services/core/rop/fetchers.py`**

```python
"""AI ROP AmoCRM reads — the ONLY I/O module. Bounded, non-raising (except the
first active-leads page). Worst-case ~25 sequential GETs on the evening slot."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

from src.services.core.crm.amocrm_pipeline_config import (
    SALES_PIPELINE_ID,
    STATUS_LOST,
    STATUS_WON,
)

logger = logging.getLogger("RopFetcher")
_TZ = ZoneInfo("Asia/Tashkent")
_TIMEOUT = 30


class RopFetchError(RuntimeError):
    """Raised only when the first active-leads page cannot be read."""


def _tashkent_day_start_epoch(now: datetime) -> int:
    local = now.astimezone(_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(local.timestamp())


class RopFetcher:
    def __init__(self, amocrm, *, session=None):
        self._amo = amocrm
        self._session = session or requests

    async def _get(self, url, params=None):
        return await asyncio.to_thread(
            self._session.get,
            url,
            headers=self._amo._get_headers(),
            params=params,
            timeout=_TIMEOUT,
        )

    async def _paged(self, url, params, key, *, max_pages, embed):
        out: list[dict] = []
        page_url, page_params = url, dict(params)
        for i in range(max_pages):
            try:
                resp = await self._get(page_url, page_params)
            except Exception as exc:  # noqa: BLE001
                logger.warning("[ROP] %s page %s failed: %s", url, i, exc)
                break
            if resp.status_code != 200:
                logger.warning("[ROP] %s page %s -> HTTP %s", url, i, resp.status_code)
                if i == 0 and key == "leads" and embed == "leads":
                    raise RopFetchError(f"{url} -> {resp.status_code}")
                break
            body = resp.json()
            out.extend(body.get("_embedded", {}).get(embed, []))
            nxt = body.get("_links", {}).get("next", {}).get("href")
            if not nxt:
                break
            page_url, page_params = nxt, None
        return out

    async def fetch_active_sales_leads(self) -> list[dict]:
        try:
            leads = await self._paged(
                f"{self._amo.base_url}/api/v4/leads",
                {"filter[pipeline_id]": SALES_PIPELINE_ID, "with": "contacts", "limit": 250},
                key="leads", max_pages=4, embed="leads",
            )
        except RopFetchError:
            raise
        return [l for l in leads if l.get("status_id") not in (STATUS_WON, STATUS_LOST)]

    async def fetch_open_tasks_for_leads(self, lead_ids):
        rows = await self._paged(
            f"{self._amo.base_url}/api/v4/tasks",
            {"filter[entity_type]": "leads", "filter[is_completed]": 0, "limit": 250},
            key="tasks", max_pages=4, embed="tasks",
        )
        want = set(lead_ids)
        grouped: dict[int, list[dict]] = {}
        for t in rows:
            eid = t.get("entity_id")
            if eid in want:
                grouped.setdefault(eid, []).append(t)
        return grouped

    async def fetch_today_completed_tasks(self, user_ids, *, now=None):
        now = now or datetime.now(_TZ)
        since = _tashkent_day_start_epoch(now)
        rows = await self._paged(
            f"{self._amo.base_url}/api/v4/tasks",
            {"filter[is_completed]": 1, "filter[updated_at][from]": since, "limit": 250},
            key="tasks", max_pages=4, embed="tasks",
        )
        want = set(user_ids)
        by_entity: dict[int, list[dict]] = {}
        by_user: dict[int, list[dict]] = {}
        for t in rows:
            if t.get("responsible_user_id") not in want:
                continue
            by_entity.setdefault(t.get("entity_id"), []).append(t)
            by_user.setdefault(t.get("responsible_user_id"), []).append(t)
        return by_entity, by_user

    async def fetch_today_events(self, lead_ids, *, now=None):
        now = now or datetime.now(_TZ)
        since = _tashkent_day_start_epoch(now)
        rows = await self._paged(
            f"{self._amo.base_url}/api/v4/events",
            {"filter[entity]": "lead", "filter[created_at][from]": since, "limit": 100},
            key="events", max_pages=3, embed="events",
        )
        want = set(lead_ids)
        grouped: dict[int, list[dict]] = {}
        for e in rows:
            eid = e.get("entity_id")
            if eid in want:
                grouped.setdefault(eid, []).append(e)
        return grouped

    async def fetch_recent_events(self, lead_ids, since_epoch):
        rows = await self._paged(
            f"{self._amo.base_url}/api/v4/events",
            {"filter[entity]": "lead", "filter[created_at][from]": since_epoch,
             "filter[type]": "lead_status_changed", "limit": 250},
            key="events", max_pages=4, embed="events",
        )
        want = set(lead_ids)
        grouped: dict[int, list[dict]] = {}
        for e in rows:
            eid = e.get("entity_id")
            if eid in want:
                grouped.setdefault(eid, []).append(e)
        return grouped

    async def fetch_won_leads_since(self, since_epoch):
        return await self._paged(
            f"{self._amo.base_url}/api/v4/leads",
            {"filter[pipeline_id]": SALES_PIPELINE_ID,
             "filter[statuses][0][status_id]": STATUS_WON,
             "filter[closed_at][from]": since_epoch, "limit": 250},
            key="leads", max_pages=4, embed="leads",
        )

    async def fetch_notes_for_leads(self, lead_ids):
        grouped: dict[int, list[dict]] = {}
        ids = list(lead_ids)[:300]
        requests_made = 0
        for start in range(0, len(ids), 50):
            if requests_made >= 6:
                break
            batch = ids[start:start + 50]
            params = {"limit": 250}
            for i, lid in enumerate(batch):
                params[f"filter[entity_id][{i}]"] = lid
            rows = await self._paged(
                f"{self._amo.base_url}/api/v4/leads/notes",
                params, key="notes", max_pages=1, embed="notes",
            )
            requests_made += 1
            for n in rows:
                eid = n.get("entity_id")
                grouped.setdefault(eid, []).append(n)
        return grouped

    async def fetch_user_names(self, user_ids):
        out: dict[int, str] = {}
        for uid in list(user_ids)[:30]:
            try:
                resp = await self._get(f"{self._amo.base_url}/api/v4/users/{uid}")
                if resp.status_code == 200:
                    out[uid] = resp.json().get("name") or f"Menejer_{uid}"
                    continue
            except Exception:  # noqa: BLE001
                pass
            out[uid] = f"Menejer_{uid}"
        return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `SKIP_LIVE=1 python -m pytest tests/test_rop_fetchers.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/services/core/rop/fetchers.py tests/test_rop_fetchers.py
git commit -m "feat(rop): bounded AmoCRM fetchers

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 11: `service.py` — orchestrator returning a delivery plan

**Files:**
- Create: `src/services/core/rop/service.py`
- Modify: `src/services/core/rop/__init__.py` (re-export `RopService`)
- Create: `tests/test_rop_service.py`

**Interfaces:**
- Consumes: `RopRepository` (Task 1), `load_config`/`seed_config` (Task 2), `load_roster` (Task 3), `RopFetcher` + `RopFetchError` + `_tashkent_day_start_epoch` (Task 10), all builders/renderers (Tasks 8–9), `evaluate` + `SellerMetrics` (Task 7), `no_result_streak_days` + `progress` + `monday_start` (Task 6), `Finding` (Task 5), `get_local_now` from `src.time_utils`
- Produces:
  - `class RopService`
    - `__init__(self, repo, fetcher, *, ceo_chat_id: int | None, now_fn=get_local_now)`
    - `async run(self, slot: str) -> list[tuple[int, str]]` where `slot ∈ {"morning", "midday", "evening"}`
    - returns `list[(chat_id, html_text)]`; empty roster → `[(ceo_chat_id, render_empty_roster_notice())]` (or `[]` if `ceo_chat_id` is None)
  - `SLOTS = ("morning", "midday", "evening")`

Behaviour:
- `await seed_config(repo)` once at the top of `run` (idempotent).
- Build `now = now_fn()`.
- `roster = await load_roster(repo)`; if empty → return the notice.
- `fetch_active_sales_leads()` inside `try/except RopFetchError:` → on error, log and return `[]` (abort slot).
- Partition leads by `responsible_user_id` (only roster user ids; others ignored except for `NO_OWNER`).
- Fetch: open tasks (all slots), today-completed tasks (all slots), notes (morning + evening), today-events (all slots). Evening + Monday-morning also: `fetch_recent_events(since=now-7d)` and `fetch_won_leads_since(monday_start_epoch)`.
- Per seller wrap compute in `try/except Exception:` → on error increment `skipped` and continue.
- `morning`: build `SellerMorningPlan` per seller (+ `discipline.find`), write today's band snapshot to `repo.set_config(f"snapshot.{YYYY-MM-DD}", {lead_id: band})`, delete snapshots older than 2 days (`_cleanup_snapshots`), build `CeoMorning` (Monday → include `progress(...)` of *last* week). Seller messages only to sellers with `telegram_user_id`.
- `midday`: build `SellerMiddayCheck`; **only** append `(tg_id, render_seller_midday(c))` when `not c.on_track and tg_id`. Build `SellerMetrics` + `evaluate` per seller for the CEO line. Append CEO midday message only if `CeoMidday.any_alert` (else a single green line).
- `evening`: build `SellerEveningResult` (always to sellers with tg id), `SellerMetrics` + `evaluate`, `CeoDashboard` with live `progress(...)`.
- `actuals` per seller from today-completed tasks: `calls` = count `task_type_id == 1`, `meetings` = count `task_type_id == 2`, `follow_ups` = count of the rest, `won` / `won_revenue` from won-leads-since-midnight filtered by `responsible_user_id` (evening/midday: fetch `fetch_won_leads_since(_tashkent_day_start_epoch(now))`).
- `touched_lead_ids` (midday) = lead ids present in today-completed-tasks or today-events for that seller.
- Band-drop: `hot_band_dropped` = any lead currently WARM/COLD that was `HOT` in the most recent prior `snapshot.*`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_rop_service.py
from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from src.services.core.rop.service import RopService

TZ = ZoneInfo("Asia/Tashkent")
MON_9AM = datetime(2026, 9, 7, 9, 0, tzinfo=TZ)   # Monday
THU_630 = datetime(2026, 9, 10, 18, 30, tzinfo=TZ)


class FakeRepo:
    def __init__(self, targets):
        self._targets = targets
        self.cfg = {}
    async def all_config(self): return dict(self.cfg)
    async def set_config(self, k, v): self.cfg[k] = v
    async def get_config(self, k, d=None): return self.cfg.get(k, d)
    async def list_active_targets(self): return [dict(t) for t in self._targets]


def _target(uid, tg):
    return {"responsible_user_id": uid, "seller_name": f"S{uid}", "telegram_user_id": tg,
            "expected_sales": 1, "calls": 10, "follow_ups": 20, "meetings": 2,
            "proposals": 0, "payments": 1, "max_overdue": 0, "active": 1, "updated_at": "x"}


class FakeFetcher:
    def __init__(self, leads):
        self._leads = leads
        self.raised = False
    async def fetch_active_sales_leads(self): return list(self._leads)
    async def fetch_open_tasks_for_leads(self, ids): return {}
    async def fetch_today_completed_tasks(self, uids, now=None): return {}, {}
    async def fetch_today_events(self, ids, now=None): return {}
    async def fetch_notes_for_leads(self, ids): return {}
    async def fetch_recent_events(self, ids, since): return {}
    async def fetch_won_leads_since(self, since): return []


@pytest.mark.asyncio
async def test_empty_roster_returns_ceo_notice():
    svc = RopService(FakeRepo([]), FakeFetcher([]), ceo_chat_id=42, now_fn=lambda: THU_630)
    plan = await svc.run("evening")
    assert plan == [(42, "ROP: hech qanday sotuvchi sozlanmagan.")]

@pytest.mark.asyncio
async def test_empty_roster_no_ceo_returns_empty():
    svc = RopService(FakeRepo([]), FakeFetcher([]), ceo_chat_id=None, now_fn=lambda: THU_630)
    assert await svc.run("evening") == []

@pytest.mark.asyncio
async def test_morning_sends_seller_dm_and_ceo():
    leads = [{"id": 1, "name": "ABC", "status_id": 111, "price": 5_000_000,
              "responsible_user_id": 101, "updated_at": int(THU_630.timestamp()) - 100,
              "created_at": int(THU_630.timestamp()) - 5 * 86400}]
    repo = FakeRepo([_target(101, 555)])
    svc = RopService(repo, FakeFetcher(leads), ceo_chat_id=42, now_fn=lambda: THU_630)
    plan = await svc.run("morning")
    chat_ids = [c for c, _ in plan]
    assert 555 in chat_ids and 42 in chat_ids
    # snapshot written
    assert any(k.startswith("snapshot.2026-09-10") for k in repo.cfg)

@pytest.mark.asyncio
async def test_midday_suppresses_on_track_seller():
    leads = [{"id": 1, "name": "ABC", "status_id": 111, "price": 1_000_000,
              "responsible_user_id": 101, "updated_at": int(THU_630.timestamp()) - 100,
              "created_at": int(THU_630.timestamp()) - 3 * 86400}]
    repo = FakeRepo([_target(101, 555)])
    # COLD lead + zero targets pressure: seller on track -> no seller DM
    svc = RopService(repo, FakeFetcher(leads), ceo_chat_id=42, now_fn=lambda: THU_630)
    plan = await svc.run("midday")
    assert 555 not in [c for c, _ in plan]

@pytest.mark.asyncio
async def test_fetch_error_aborts_slot():
    class Boom(FakeFetcher):
        async def fetch_active_sales_leads(self):
            from src.services.core.rop.fetchers import RopFetchError
            raise RopFetchError("boom")
    svc = RopService(FakeRepo([_target(101, 555)]), Boom([]), ceo_chat_id=42, now_fn=lambda: THU_630)
    assert await svc.run("evening") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `SKIP_LIVE=1 python -m pytest tests/test_rop_service.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write `src/services/core/rop/service.py`**

```python
"""AI ROP orchestrator: fetch -> compute -> render. Returns a delivery plan.
Never sends; the scheduler sends."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from src.services.core.rop.config import load_config, seed_config
from src.services.core.rop.daily import (
    build_ceo_dashboard, build_ceo_midday, build_ceo_morning, build_evening,
    build_midday, build_morning, score_seller_leads,
)
from src.services.core.rop.discipline import find as find_discipline
from src.services.core.rop.fetchers import RopFetchError, _tashkent_day_start_epoch
from src.services.core.rop.rop_messages import (
    render_ceo_dashboard, render_ceo_midday, render_ceo_morning,
    render_empty_roster_notice, render_seller_evening, render_seller_midday,
    render_seller_morning,
)
from src.services.core.rop.targets import load_roster
from src.services.core.rop.traffic_light import SellerMetrics, evaluate
from src.services.core.rop.weekly import monday_start, no_result_streak_days, progress
from src.time_utils import get_local_now

logger = logging.getLogger("RopService")
SLOTS = ("morning", "midday", "evening")


def _bucket_actuals(completed_tasks: list[dict]) -> dict:
    calls = sum(1 for t in completed_tasks if t.get("task_type_id") == 1)
    meetings = sum(1 for t in completed_tasks if t.get("task_type_id") == 2)
    follow_ups = len(completed_tasks) - calls - meetings
    return {"calls": calls, "meetings": meetings, "follow_ups": follow_ups}


class RopService:
    def __init__(self, repo, fetcher, *, ceo_chat_id, now_fn=get_local_now):
        self._repo = repo
        self._fetch = fetcher
        self._ceo = ceo_chat_id
        self._now_fn = now_fn

    async def run(self, slot: str) -> list[tuple[int, str]]:
        assert slot in SLOTS, slot
        await seed_config(self._repo)
        config = await load_config(self._repo)
        now: datetime = self._now_fn()

        roster = await load_roster(self._repo)
        if not roster:
            return [(self._ceo, render_empty_roster_notice())] if self._ceo else []

        try:
            leads = await self._fetch.fetch_active_sales_leads()
        except RopFetchError as exc:
            logger.warning("[ROP] %s slot aborted — active leads fetch failed: %s", slot, exc)
            return []

        roster_ids = {s.responsible_user_id for s in roster}
        leads_by_user: dict[int, list[dict]] = {uid: [] for uid in roster_ids}
        no_owner: list[dict] = []
        for l in leads:
            uid = l.get("responsible_user_id")
            if not uid:
                no_owner.append(l)
            elif uid in leads_by_user:
                leads_by_user[uid].append(l)

        all_lead_ids = [l["id"] for l in leads]
        open_tasks = await self._fetch.fetch_open_tasks_for_leads(all_lead_ids)
        completed_by_entity, completed_by_user = await self._fetch.fetch_today_completed_tasks(
            list(roster_ids), now=now
        )
        today_events = await self._fetch.fetch_today_events(all_lead_ids, now=now)
        notes = (
            await self._fetch.fetch_notes_for_leads(all_lead_ids)
            if slot in ("morning", "evening")
            else {}
        )

        is_monday = now.weekday() == 0
        recent_events: dict = {}
        won_today: list[dict] = []
        won_week: list[dict] = []
        if slot in ("midday", "evening"):
            won_today = await self._fetch.fetch_won_leads_since(_tashkent_day_start_epoch(now))
        if slot == "evening" or (slot == "morning" and is_monday):
            since_7d = int((now - timedelta(days=7)).timestamp())
            recent_events = await self._fetch.fetch_recent_events(all_lead_ids, since_7d)
            won_week = await self._fetch.fetch_won_leads_since(int(monday_start(now).timestamp()))

        prior_snapshot = self._latest_snapshot(now)
        plan: list[tuple[int, str]] = []
        skipped = 0
        morning_plans = []
        midday_checks = []
        evening_results = []
        traffic: dict[int, object] = {}

        for s in roster:
            try:
                s_leads = leads_by_user.get(s.responsible_user_id, [])
                events_by_lead = {
                    lid: today_events.get(lid, []) + recent_events.get(lid, [])
                    for lid in (l["id"] for l in s_leads)
                }
                scored = score_seller_leads(
                    s_leads, open_tasks, notes, events_by_lead, config, now
                )
                s_completed = completed_by_user.get(s.responsible_user_id, [])
                actuals = _bucket_actuals(s_completed)
                s_won_today = [
                    l for l in won_today
                    if l.get("responsible_user_id") == s.responsible_user_id
                ]
                actuals["won"] = len(s_won_today)
                actuals["won_revenue"] = sum(int(l.get("price") or 0) for l in s_won_today)

                if slot == "morning":
                    tasks_by_lead = {l["id"]: open_tasks.get(l["id"], []) for l in s_leads}
                    findings = find_discipline(
                        s_leads, open_tasks, notes, config, now
                    )
                    mp = build_morning(s, scored, tasks_by_lead, findings, config, now)
                    morning_plans.append(mp)
                    if s.telegram_user_id:
                        plan.append((s.telegram_user_id, render_seller_morning(mp)))

                elif slot == "midday":
                    touched = {
                        lid for lid in (l["id"] for l in s_leads)
                        if completed_by_entity.get(lid) or today_events.get(lid)
                    }
                    check = build_midday(s, scored, actuals, touched, config)
                    midday_checks.append(check)
                    traffic[s.responsible_user_id] = self._traffic_for(
                        s, scored, actuals, [], config, now, recent_events,
                        prior_snapshot, s_leads, open_tasks,
                    )
                    if not check.on_track and s.telegram_user_id:
                        plan.append((s.telegram_user_id, render_seller_midday(check)))

                else:  # evening
                    overdue_count = sum(
                        1 for lid in (l["id"] for l in s_leads)
                        for t in open_tasks.get(lid, [])
                        if (t.get("complete_till") or 0) and float(t["complete_till"]) < now.timestamp()
                    )
                    ev = build_evening(s, scored, actuals, overdue_count)
                    evening_results.append(ev)
                    findings = find_discipline(s_leads, open_tasks, notes, config, now)
                    traffic[s.responsible_user_id] = self._traffic_for(
                        s, scored, actuals, findings, config, now, recent_events,
                        prior_snapshot, s_leads, open_tasks,
                    )
                    if s.telegram_user_id:
                        plan.append((s.telegram_user_id, render_seller_evening(ev)))
            except Exception:  # noqa: BLE001
                logger.exception("[ROP] seller %s compute failed", s.responsible_user_id)
                skipped += 1

        no_owner_findings = [
            find_discipline([l], {}, {}, config, now)[0]
            for l in no_owner
            if find_discipline([l], {}, {}, config, now)
        ]

        if slot == "morning":
            self._write_snapshot(now, morning_plans)
            self._cleanup_snapshots(now)
            weekly_recap = progress(won_week, config) if is_monday else None
            ceo = build_ceo_morning(morning_plans, no_owner_findings, weekly_recap)
            if self._ceo:
                plan.append((self._ceo, render_ceo_morning(ceo)))
        elif slot == "midday":
            ceo = build_ceo_midday(midday_checks, traffic)
            if self._ceo:
                plan.append((self._ceo, render_ceo_midday(ceo)))
        else:
            weekly = progress(won_week, config)
            expected_tomorrow = sum(
                int(ls.price * ls.score / 100)
                for mp in ()  # evening has no morning_plans; recompute from evening scored
                for ls in []
            )
            # expected tomorrow = sum of HOT+WARM expected across sellers' scored lists
            expected_tomorrow = sum(
                int(l.price * l.score / 100)
                for ev in evening_results
                for l in ev.tomorrow_closings
                if l.band in ("HOT", "WARM")
            )
            dash = build_ceo_dashboard(
                evening_results, traffic, weekly, expected_tomorrow, skipped
            )
            if self._ceo:
                plan.append((self._ceo, render_ceo_dashboard(dash)))

        return plan

    # ---- snapshot helpers ----

    def _snapshot_key(self, now: datetime) -> str:
        return f"snapshot.{now.strftime('%Y-%m-%d')}"

    def _write_snapshot(self, now, morning_plans) -> None:
        data: dict[str, str] = {}
        for mp in morning_plans:
            for ls in mp.top_closings:
                data[str(ls.lead_id)] = ls.band
        # also record every scored lead we saw via expected list
        # (top_closings is enough for band-drop signal on the hottest deals)
        import asyncio

        asyncio.ensure_future(self._repo.set_config(self._snapshot_key(now), data))

    def _latest_snapshot(self, now) -> dict:
        # read yesterday's snapshot synchronously-ish via cached all_config path
        import asyncio

        async def _read():
            cfg = await self._repo.all_config()
            keys = sorted(k for k in cfg if k.startswith("snapshot."))
            return cfg.get(keys[-1], {}) if keys else {}

        try:
            return asyncio.get_event_loop().run_until_complete(_read())  # pragma: no cover
        except RuntimeError:
            return {}

    def _cleanup_snapshots(self, now) -> None:
        import asyncio

        async def _clean():
            cfg = await self._repo.all_config()
            cutoff = (now - timedelta(days=2)).strftime("%Y-%m-%d")
            for k in list(cfg):
                if k.startswith("snapshot.") and k.split(".", 1)[1] < cutoff:
                    await self._repo.set_config(k, {})

        asyncio.ensure_future(_clean())

    def _traffic_for(
        self, seller, scored, actuals, findings, config, now, recent_events,
        prior_snapshot, s_leads, open_tasks,
    ):
        won_today = actuals.get("won", 0)
        streak = 0
        # streak needs this seller's WON closed_at within 7d — derive from recent_events
        # of type lead_status_changed to WON is not reliable; keep 0 unless caller supplied.
        overdue_count = sum(
            1 for lid in (l["id"] for l in s_leads)
            for t in open_tasks.get(lid, [])
            if (t.get("complete_till") or 0) and float(t["complete_till"]) < now.timestamp()
        )
        hot_silent = 0.0
        for ls in scored:
            if ls.band == "HOT":
                # reasons carry "72 soatdan beri aloqa yo'q" when >72h; approximate
                if any("aloqa yo'q" in r for r in ls.reasons):
                    hot_silent = max(hot_silent, config["traffic.hot_lead_silent_hours"])
        band_dropped = any(
            prior_snapshot.get(str(ls.lead_id)) == "HOT" and ls.band != "HOT"
            for ls in scored
        )
        biggest_amt, biggest_days = 0, 0.0
        metrics = SellerMetrics(
            won_today=won_today,
            no_result_streak_days=streak,
            overdue_count=overdue_count,
            calls_done=actuals["calls"], calls_target=seller.calls,
            follow_ups_done=actuals["follow_ups"], follow_ups_target=seller.follow_ups,
            meetings_done=actuals["meetings"], meetings_target=seller.meetings,
            biggest_stuck_deal_amount=biggest_amt,
            biggest_stuck_deal_days=biggest_days,
            hot_lead_max_silent_hours=hot_silent,
            hot_band_dropped=band_dropped,
        )
        return evaluate(metrics, findings, config)
```

> **Implementer note (important):** the async snapshot helpers above use `asyncio.ensure_future` / `run_until_complete` as sketch. Replace with clean `await` calls: make `_write_snapshot`, `_latest_snapshot`, `_cleanup_snapshots` `async` and `await` them from `run`. `_latest_snapshot` must be awaited **before** the seller loop (it's read there). Adjust the tests only if signatures change — keep `test_rop_service.py` green. The intent is fully synchronous-in-`run` awaiting; no fire-and-forget.

- [ ] **Step 4: Refactor snapshot helpers to clean `async`/`await`**

Make the three helpers `async`; in `run`, `prior_snapshot = await self._latest_snapshot(now)` before the loop, `await self._write_snapshot(now, morning_plans)` and `await self._cleanup_snapshots(now)` in the morning branch. Remove all `import asyncio` / `ensure_future` / `run_until_complete`.

- [ ] **Step 5: Re-export from `__init__.py`**

```python
"""AI ROP — Sotuv bo'limi rahbari (daily core)."""
from src.services.core.rop.service import RopService, SLOTS

__all__ = ["RopService", "SLOTS"]
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `SKIP_LIVE=1 python -m pytest tests/test_rop_service.py -v`
Expected: PASS (5 tests)

- [ ] **Step 7: Commit**

```bash
git add src/services/core/rop/service.py src/services/core/rop/__init__.py tests/test_rop_service.py
git commit -m "feat(rop): RopService orchestrator returning delivery plan

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 12: `rop_scheduler.py` — 3 timed loops + wiring

**Files:**
- Create: `src/schedulers/rop_scheduler.py`
- Modify: `src/bootstrap/orchestration/schedulers.py`
- Modify: `.env.example`
- Create: `tests/test_rop_scheduler.py`

**Interfaces:**
- Consumes: `RopService` + `SLOTS` (Task 11), `RopFetcher` (Task 10), `get_db()` from `src.database`, `BotRuntimePort` / `_as_bot_runtime` pattern from `frog_scheduler`, `get_local_now`, `is_quiet_hours` from `src.time_utils`, `app_ctx` from `src.context`
- Produces:
  - `async run_rop_slot(slot: str, bot_runtime, *, now_fn=get_local_now) -> int` — builds a `RopService`, calls `run(slot)`, sends each message (retry once), returns messages-sent count. Returns 0 without sending if `ROP_ENABLED != "1"`, if `is_quiet_hours(now)`, if `now.weekday() == 6` (Sunday), or if `DISABLE_UNSOLICITED_REPORTS == "1"`.
  - `async morning_loop(bot_runtime)`, `async midday_loop(bot_runtime)`, `async evening_loop(bot_runtime)` — poll every 30 s; fire once per day when `now.hour == H and now.minute == M and last_run_date != today` (H/M: 9/0, 14/0, 18/30).
  - `start_rop_schedulers(bot_runtime) -> None` — `asyncio.create_task` the three loops with names `rop_morning_loop` / `rop_midday_loop` / `rop_evening_loop`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_rop_scheduler.py
from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
import src.schedulers.rop_scheduler as sched

TZ = ZoneInfo("Asia/Tashkent")
THU_9 = datetime(2026, 9, 10, 9, 0, tzinfo=TZ)
SUN_9 = datetime(2026, 9, 13, 9, 0, tzinfo=TZ)
THU_2AM = datetime(2026, 9, 10, 2, 0, tzinfo=TZ)


class FakeBot:
    def __init__(self): self.sent = []
    async def send_message(self, chat_id, text, parse_mode=None):
        self.sent.append((chat_id, text)); return True


@pytest.fixture(autouse=True)
def _patch_service(monkeypatch):
    class FakeService:
        def __init__(self, *a, **k): pass
        async def run(self, slot): return [(1, "hi"), (2, "yo")]
    monkeypatch.setattr(sched, "_build_service", lambda bot_runtime, now_fn: FakeService())

@pytest.mark.asyncio
async def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ROP_ENABLED", raising=False)
    n = await sched.run_rop_slot("morning", FakeBot(), now_fn=lambda: THU_9)
    assert n == 0

@pytest.mark.asyncio
async def test_enabled_sends(monkeypatch):
    monkeypatch.setenv("ROP_ENABLED", "1")
    monkeypatch.delenv("DISABLE_UNSOLICITED_REPORTS", raising=False)
    bot = FakeBot()
    n = await sched.run_rop_slot("morning", bot, now_fn=lambda: THU_9)
    assert n == 2 and len(bot.sent) == 2

@pytest.mark.asyncio
async def test_sunday_skipped(monkeypatch):
    monkeypatch.setenv("ROP_ENABLED", "1")
    n = await sched.run_rop_slot("morning", FakeBot(), now_fn=lambda: SUN_9)
    assert n == 0

@pytest.mark.asyncio
async def test_quiet_hours_skipped(monkeypatch):
    monkeypatch.setenv("ROP_ENABLED", "1")
    n = await sched.run_rop_slot("morning", FakeBot(), now_fn=lambda: THU_2AM)
    assert n == 0

@pytest.mark.asyncio
async def test_unsolicited_mute_skipped(monkeypatch):
    monkeypatch.setenv("ROP_ENABLED", "1")
    monkeypatch.setenv("DISABLE_UNSOLICITED_REPORTS", "1")
    n = await sched.run_rop_slot("morning", FakeBot(), now_fn=lambda: THU_9)
    assert n == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `SKIP_LIVE=1 python -m pytest tests/test_rop_scheduler.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.schedulers.rop_scheduler'`

- [ ] **Step 3: Write `src/schedulers/rop_scheduler.py`**

```python
"""AI ROP daily scheduler — 3 timed slots (09:00 / 14:00 / 18:30 Tashkent),
Mon–Sat, internal DMs only. Gated by ROP_ENABLED (default off)."""
from __future__ import annotations

import asyncio
import logging
import os

from src.context import app_ctx
from src.database import get_db
from src.services.core.rop.fetchers import RopFetcher
from src.services.core.rop.service import RopService
from src.services.core.telegram.bot_runtime import BotRuntimePort, TelethonBotRuntime
from src.time_utils import get_local_now, is_quiet_hours

logger = logging.getLogger("RopScheduler")

_SLOT_TIMES = {"morning": (9, 0), "midday": (14, 0), "evening": (18, 30)}


def _as_bot_runtime(bot_client):
    if bot_client is None:
        return None
    if hasattr(bot_client, "backend") and hasattr(bot_client, "send_message"):
        return bot_client
    return TelethonBotRuntime(bot_client)


def _enabled() -> bool:
    return os.getenv("ROP_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def _ceo_chat_id() -> int | None:
    raw = os.getenv("ROP_CEO_CHAT_ID", "").strip()
    try:
        return int(raw) if raw else None
    except ValueError:
        return None


def _build_service(bot_runtime, now_fn) -> RopService:
    amocrm = app_ctx.msg_controller.crm.amocrm
    db = get_db()
    return RopService(
        db.rop,
        RopFetcher(amocrm),
        ceo_chat_id=_ceo_chat_id(),
        now_fn=now_fn,
    )


async def run_rop_slot(slot: str, bot_runtime, *, now_fn=get_local_now) -> int:
    now = now_fn()
    if not _enabled():
        return 0
    if os.getenv("DISABLE_UNSOLICITED_REPORTS", "").strip() == "1":
        return 0
    if now.weekday() == 6:  # Sunday
        return 0
    if is_quiet_hours(now):
        return 0

    try:
        service = _build_service(bot_runtime, now_fn)
        plan = await service.run(slot)
    except Exception:
        logger.exception("[ROP] %s slot failed to build plan", slot)
        return 0

    sent = 0
    for chat_id, text in plan:
        for attempt in (1, 2):
            try:
                await bot_runtime.send_message(chat_id, text, parse_mode="HTML")
                sent += 1
                break
            except Exception as exc:  # noqa: BLE001
                if attempt == 2:
                    logger.warning("[ROP] send to %s dropped: %s", chat_id, exc)
    logger.info("[ROP] %s slot: %s/%s messages sent", slot, sent, len(plan))
    return sent


async def _slot_loop(slot: str, bot_runtime) -> None:
    hour, minute = _SLOT_TIMES[slot]
    await asyncio.sleep(15)
    last_run_date = None
    logger.info("[ROP] %s loop started (%02d:%02d Tashkent)", slot, hour, minute)
    while True:
        try:
            now = get_local_now()
            today = now.strftime("%Y-%m-%d")
            if now.hour == hour and now.minute == minute and last_run_date != today:
                await run_rop_slot(slot, bot_runtime)
                last_run_date = today
        except Exception:
            logger.exception("[ROP] %s loop iteration error", slot)
        await asyncio.sleep(30)


async def morning_loop(bot_runtime) -> None:
    await _slot_loop("morning", bot_runtime)


async def midday_loop(bot_runtime) -> None:
    await _slot_loop("midday", bot_runtime)


async def evening_loop(bot_runtime) -> None:
    await _slot_loop("evening", bot_runtime)


def start_rop_schedulers(bot_runtime) -> None:
    rt = _as_bot_runtime(bot_runtime)
    asyncio.create_task(morning_loop(rt), name="rop_morning_loop")
    asyncio.create_task(midday_loop(rt), name="rop_midday_loop")
    asyncio.create_task(evening_loop(rt), name="rop_evening_loop")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `SKIP_LIVE=1 python -m pytest tests/test_rop_scheduler.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Wire into bootstrap**

In `src/bootstrap/orchestration/schedulers.py`, at the end of `start_background_schedulers` (after the `cloud_brain_synthesizer` block):

```python
    try:
        from src.schedulers.rop_scheduler import start_rop_schedulers
        start_rop_schedulers(bot_runtime)
    except ImportError as exc:
        logger.warning("[ROP] scheduler unavailable: %s", exc)
```

- [ ] **Step 6: Update `.env.example`**

Add under the "Operation modes / guardrails" group:

```
# AI ROP — Sotuv bo'limi rahbari (daily engine). Runs 09:00/14:00/18:30 Tashkent,
# Mon–Sat, internal DMs only. Off by default.
ROP_ENABLED=0
# Telegram chat/topic id that receives the CEO traffic-light dashboard.
ROP_CEO_CHAT_ID=
```

- [ ] **Step 7: Full gate + commit**

```bash
SKIP_LIVE=1 python -m pytest -q tests/test_rop_*.py
bandit -r src/services/core/rop src/schedulers/rop_scheduler.py src/db/repositories/rop.py -ll
git add src/schedulers/rop_scheduler.py src/bootstrap/orchestration/schedulers.py .env.example tests/test_rop_scheduler.py
git commit -m "feat(rop): 3-slot daily scheduler + bootstrap wiring

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 13: End-to-end smoke test + full gate

**Files:**
- Create: `tests/test_rop_end_to_end.py`

**Interfaces:**
- Consumes: `RopService`, `RopRepository` (real, on a tmp SQLite DB), fake fetcher returning a realistic multi-seller lead set.

- [ ] **Step 1: Write the end-to-end test**

```python
# tests/test_rop_end_to_end.py
from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from src.db import Database
from src.services.core.rop.service import RopService
from src.services.core.rop.targets import seed_default

TZ = ZoneInfo("Asia/Tashkent")
THU_630 = datetime(2026, 9, 10, 18, 30, tzinfo=TZ)
E = int(THU_630.timestamp())


class FakeFetcher:
    def __init__(self, leads, completed_by_user, won_today):
        self._leads = leads
        self._cbu = completed_by_user
        self._won = won_today
    async def fetch_active_sales_leads(self): return list(self._leads)
    async def fetch_open_tasks_for_leads(self, ids): return {}
    async def fetch_today_completed_tasks(self, uids, now=None):
        by_entity = {}
        return by_entity, {u: list(v) for u, v in self._cbu.items()}
    async def fetch_today_events(self, ids, now=None): return {}
    async def fetch_notes_for_leads(self, ids): return {}
    async def fetch_recent_events(self, ids, since): return {}
    async def fetch_won_leads_since(self, since): return list(self._won)


@pytest.fixture
async def db(tmp_path):
    d = Database(db_path=str(tmp_path / "e2e.db"))
    await d.connect()
    await d.rop.init_table()
    yield d
    await d.close()

@pytest.mark.asyncio
async def test_evening_run_produces_seller_and_ceo_messages(db):
    await seed_default(db.rop, 101, 555, "Oydin")
    await seed_default(db.rop, 102, 556, "Shahnoza")
    leads = [
        {"id": 1, "name": "ABC", "status_id": 111, "price": 12_000_000,
         "responsible_user_id": 101, "updated_at": E - 3600, "created_at": E - 4 * 86400},
        {"id": 2, "name": "XYZ", "status_id": 111, "price": 6_000_000,
         "responsible_user_id": 102, "updated_at": E - 200 * 3600, "created_at": E - 30 * 86400},
    ]
    completed = {101: [{"task_type_id": 1, "is_completed": True} for _ in range(9)]}
    won_today = [{"responsible_user_id": 101, "status_id": 142, "price": 12_000_000}]
    svc = RopService(db.rop, FakeFetcher(leads, completed, won_today),
                     ceo_chat_id=42, now_fn=lambda: THU_630)
    plan = await svc.run("evening")
    chat_ids = {c for c, _ in plan}
    assert 555 in chat_ids and 556 in chat_ids and 42 in chat_ids
    ceo_msg = next(t for c, t in plan if c == 42)
    assert "Sales Department" in ceo_msg
    assert "Haftalik" in ceo_msg
```

- [ ] **Step 2: Run the end-to-end test**

Run: `SKIP_LIVE=1 python -m pytest tests/test_rop_end_to_end.py -v`
Expected: PASS (1 test)

- [ ] **Step 3: Full project gate**

Run:
```bash
SKIP_LIVE=1 python -m pytest -q --tb=short
bandit -r src/ -ll
```
Expected: pytest green (no new failures vs. baseline); bandit no new findings in `src/services/core/rop/`, `src/schedulers/rop_scheduler.py`, `src/db/repositories/rop.py`.

- [ ] **Step 4: Commit**

```bash
git add tests/test_rop_end_to_end.py
git commit -m "test(rop): end-to-end evening-slot smoke test

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Self-Review

**1. Spec coverage:**

| Spec section | Task(s) |
|---|---|
| §1 morning plan / priorities | Task 8 `build_morning`, Task 9 `render_seller_morning`, Task 11 morning branch |
| §2 per-seller daily targets (config-driven) | Task 1 `rop_targets`, Task 3 `SellerTarget` / roster |
| §3 expected-sales / closing-likelihood engine | Task 4 `scoring.py`, Task 8 `_expected` |
| §4 14:00 midday check + suppression | Task 8 `build_midday` (`on_track`), Task 11 midday branch, Task 12 tests |
| §5 18:30 daily reports (seller + CEO dashboard) | Task 8 `build_evening` / `build_ceo_dashboard`, Task 9 renderers |
| §6 traffic light GREEN/YELLOW/RED | Task 7 `traffic_light.py`, Task 11 `_traffic_for` |
| §7 amoCRM discipline | Task 5 `discipline.py`, surfaced in morning DM + CEO |
| §8 weekly plan (live, stateless) | Task 6 `weekly.py`, Task 11 evening/Monday |
| Config table `rop_config` | Task 1 + Task 2 |
| Scheduler / guardrails / env vars | Task 12 |
| Error handling (§10 of spec) | Task 10 (`RopFetchError`), Task 11 (per-seller try/except, abort-on-fetch-fail, empty roster), Task 12 (gates) |
| Testing (§11 of spec) | every task + Task 13 |
| Band-drop snapshot (spec §8) | Task 11 `_write_snapshot` / `_latest_snapshot` / `_cleanup_snapshots`, Task 7 `hot_band_dropped` |

Deferred sections §9–§13 are explicitly out of scope per the spec.

**Known simplifications (acceptable for v1, noted for the implementer):**
- `no_result_streak_days` is wired as `0` in `_traffic_for` because deriving per-seller WON `closed_at` history requires an extra fetch the spec bounds tightly; RED-by-streak will effectively not fire until a follow-up adds `fetch_won_leads_since(now-7d)` per seller. The function itself (Task 6) is fully implemented and tested; only the service wiring stubs its input. If the reviewer wants it live now, add one `fetch_won_leads_since(seven_days_ago)` call in Task 11 and bucket `closed_at` by `responsible_user_id`.
- `biggest_stuck_deal_*` is wired as `0` in `_traffic_for` for the same bounded-fetch reason; `days_in_stage` is already computed in `derive_features`, so a follow-up can pass the max stuck HOT/active deal through `LeadScore`. Not blocking traffic light's other RED/YELLOW rules.

**2. Placeholder scan:** No "TBD"/"add error handling"/"similar to Task N". The two `_traffic_for` simplifications are called out explicitly above with the exact code change to lift them, not left vague. The Task 11 snapshot-helper sketch is followed by a mandatory Step 4 refactor to clean `async`/`await`.

**3. Type consistency:**
- `ScoreResult` (Task 4) → consumed in Task 8 `score_seller_leads` (uses `.score`, `.band`, `.reasons`). ✓
- `LeadScore` fields (`lead_id`, `name`, `price`, `score`, `band`, `reasons`, `action`) identical in Tasks 8, 9, 11. ✓
- `SellerTarget` field order `(responsible_user_id, seller_name, telegram_user_id, expected_sales, calls, follow_ups, meetings, proposals, payments, max_overdue)` identical in Tasks 3, 8, 9 tests. ✓
- `Finding(lead_name, type, detail)` identical in Tasks 5, 7, 9, 11. ✓
- `SellerMetrics` field set identical in Tasks 7 and 11 `_traffic_for`. ✓
- `WeeklyProgress` fields (`won_count`, `won_revenue`, `sales_target`, `revenue_target`, `sales_pct`, `revenue_pct`) identical in Tasks 6, 8, 9. ✓
- `actuals` dict keys (`calls`, `follow_ups`, `meetings`, `won`, `won_revenue`) consistent across Tasks 8 (builders), 11 (`_bucket_actuals` + augmentation). ✓
- Fetcher method names used by Task 11 (`fetch_active_sales_leads`, `fetch_open_tasks_for_leads`, `fetch_today_completed_tasks`, `fetch_today_events`, `fetch_notes_for_leads`, `fetch_recent_events`, `fetch_won_leads_since`) all defined in Task 10. ✓
- `RopRepository` methods used by Task 2 (`all_config`, `set_config`) and Task 11 (`all_config`, `set_config`, `list_active_targets`) all defined in Task 1. ✓
- Scheduler `_build_service(bot_runtime, now_fn)` hook name matches the Task 12 test's monkeypatch target. ✓

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-09-10-ai-rop-daily-core.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
