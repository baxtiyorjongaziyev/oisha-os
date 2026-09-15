# Jamoa Malakasi — Training Advice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hardcoded fake AI-advisor text on the Analitika page's "Jamoa malakasi" tab with a real, cached, daily-generated training recommendation for the lowest-scoring sales manager.

**Architecture:** A new `training_advice` table (added to the existing `IntelligenceRepository`, alongside `call_analyses`) stores one row per manager: their latest AI-generated training tip. A new daily scheduler loop (`src/schedulers/training_advice_scheduler.py`, registered in `src/bootstrap/orchestration/schedulers.py` next to the other scheduler registrations) finds the manager(s) with the lowest `average_score` from the existing `manager-cards` data, builds a prompt naming their weakest playbook stage (reusing `_compute_weak_stages` from the "Sifat nazorati" work), and calls the project's `FreeAIProviderRouter` once a day — never at request time. A new `GET /api/sales-quality/training-advice` route only reads the cached row. The frontend's "AI tavsiyasini yangilash" button re-fetches that cached endpoint instead of running a fake `setTimeout` animation.

**Tech Stack:** FastAPI (Python 3.11), pytest + pytest-asyncio, `src.services.utils.free_ai_router.FreeAIProviderRouter`, Next.js/React (TypeScript), existing `src/api/rbac.py` permission system.

## Global Constraints

- Production Python files must not exceed 400 lines (AGENTS.md rule 6).
- Every function must be small (20-60 lines), single-purpose.
- `SKIP_LIVE=1 python -m pytest -q` and `bandit -r src/ -ll` must pass before considering any task done.
- No secrets, tokens, or session strings ever appear in code, logs, or commit messages.
- Never present fake/sample data as real — missing data always returns `{"available": false}`, never a fabricated number or placeholder advice string.
- SELLER-role principals must only see their own manager's data — every new endpoint that returns manager-scoped rows applies `scope_owned_rows(principal, records, owner_field="manager_id")` for `Role.SELLER`, mirroring `src/services/sales_quality/helpers.py` (`_build_sales_quality_payload`, `_build_manager_cards_payload`) and the fix already applied to the sibling `weak-stages` route in `src/services/sales_quality/router.py`. This was the one Critical finding from the previous sub-project's final review — do not repeat the gap here.
- AI generation must never run inside a request/response cycle — only inside the daily scheduler loop, matching the spec's explicit requirement ("runtime'da AI chaqirilmaydi").
- Commit messages end with `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`.

---

## File Structure

- **Modify:** `src/db/repositories/intelligence.py` — add `training_advice` table DDL to `IntelligenceRepository.init_tables()`, plus two new repository methods: `upsert_training_advice(manager_id, manager_name, advice_text) -> None` and `get_training_advice(manager_id: int | None) -> list[dict]`.
- **Create:** `src/schedulers/training_advice_scheduler.py` — daily loop: fetch manager-cards data, pick the lowest-scoring manager(s), build a prompt using their weakest stage (via `_compute_weak_stages`), call `FreeAIProviderRouter.generate_text`, write via the repository.
- **Modify:** `src/bootstrap/orchestration/schedulers.py` — register the new loop inside `start_background_schedulers`, following the existing `try/except ImportError` + `asyncio.create_task(..., name=...)` pattern used for `cloud_brain_synthesizer_loop`.
- **Modify:** `src/services/sales_quality/router.py` — add `GET /api/sales-quality/training-advice` route (read-only, DB-only, RBAC + SELLER-scoped).
- **Modify:** `src/api/routes/sales_quality.py` (facade) — re-export the new route function, matching the existing `__all__` style.
- **Test:** `tests/test_training_advice.py` — new file: repository upsert/get tests, scheduler manager-selection + prompt-building tests (AI call mocked), route tests (DB-missing, RBAC, SELLER-scoping).
- **Modify:** `apps/web/src/app/(dashboard)/analytics/page.tsx` — replace the hardcoded `aiAdviceText` state and fake `handleRefreshAi` `setTimeout` in the `"training"` tab with a real fetch to a new proxy route.
- **Create:** `apps/web/src/app/api/oisha/training-advice/route.ts` — Next.js proxy route, following the exact pattern in `apps/web/src/app/api/oisha/weak-stages/route.ts`.

## Interfaces

**Repository methods** (new, in `src/db/repositories/intelligence.py`):
```python
async def upsert_training_advice(
    self, manager_id: int, manager_name: str, advice_text: str
) -> None:
    """Writes or replaces the single cached advice row for one manager."""

async def get_training_advice(self, manager_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Returns cached advice rows, optionally filtered to one manager_id.
    Each row: {"manager_id": int, "manager_name": str, "advice_text": str,
    "generated_at": str}."""
```

**Scheduler entrypoint** (new, in `src/schedulers/training_advice_scheduler.py`):
```python
async def run_training_advice_cycle() -> None:
    """One cycle: picks the lowest-scoring manager(s), generates and stores advice."""

async def training_advice_loop() -> None:
    """Runs run_training_advice_cycle() once every 24 hours."""
```

**Route** (new, in `router.py`):
```python
@router.get("/api/sales-quality/training-advice")
async def get_sales_quality_training_advice(
    manager_id: int | None = None,
    principal: Principal = require_permissions(Permission.DASHBOARD_READ),
) -> dict:
    """Returns {"available": bool, "advice": list[dict]}"""
```

---

### Task 1: `training_advice` table + repository read/write methods

**Files:**
- Modify: `src/db/repositories/intelligence.py`
- Test: `tests/test_training_advice.py`

**Interfaces:**
- Consumes: `BaseRepository._execute(sql, params)` (existing, `src/db/repositories/base.py:40-43`), `BaseRepository._get_conn()` (existing, same file)
- Produces: `IntelligenceRepository.upsert_training_advice(manager_id, manager_name, advice_text)` and `IntelligenceRepository.get_training_advice(manager_id=None)`, used by Task 2 (scheduler) and Task 3 (route)

- [ ] **Step 1: Write the failing test**

Create `tests/test_training_advice.py`:

```python
"""Tests for the training_advice table repository methods, scheduler, and route."""
import pytest


@pytest.mark.asyncio
async def test_upsert_and_get_training_advice_round_trip():
    from src.db.repositories.intelligence import IntelligenceRepository
    from src.db.connection import ConnectionManager

    conn_manager = ConnectionManager(backend="sqlite", db_path=":memory:")
    repo = IntelligenceRepository(conn_manager)
    await repo.init_tables()

    await repo.upsert_training_advice(
        manager_id=7,
        manager_name="Test Manager",
        advice_text="E'tirozlar bosqichini mustahkamlang.",
    )

    rows = await repo.get_training_advice()

    assert len(rows) == 1
    assert rows[0]["manager_id"] == 7
    assert rows[0]["manager_name"] == "Test Manager"
    assert rows[0]["advice_text"] == "E'tirozlar bosqichini mustahkamlang."
    assert rows[0]["generated_at"]  # non-empty timestamp


@pytest.mark.asyncio
async def test_upsert_training_advice_replaces_existing_row_for_same_manager():
    from src.db.repositories.intelligence import IntelligenceRepository
    from src.db.connection import ConnectionManager

    conn_manager = ConnectionManager(backend="sqlite", db_path=":memory:")
    repo = IntelligenceRepository(conn_manager)
    await repo.init_tables()

    await repo.upsert_training_advice(manager_id=7, manager_name="Test Manager", advice_text="Old advice")
    await repo.upsert_training_advice(manager_id=7, manager_name="Test Manager", advice_text="New advice")

    rows = await repo.get_training_advice()

    assert len(rows) == 1
    assert rows[0]["advice_text"] == "New advice"


@pytest.mark.asyncio
async def test_get_training_advice_filters_by_manager_id():
    from src.db.repositories.intelligence import IntelligenceRepository
    from src.db.connection import ConnectionManager

    conn_manager = ConnectionManager(backend="sqlite", db_path=":memory:")
    repo = IntelligenceRepository(conn_manager)
    await repo.init_tables()

    await repo.upsert_training_advice(manager_id=1, manager_name="Manager One", advice_text="Advice for 1")
    await repo.upsert_training_advice(manager_id=2, manager_name="Manager Two", advice_text="Advice for 2")

    rows = await repo.get_training_advice(manager_id=1)

    assert len(rows) == 1
    assert rows[0]["manager_id"] == 1


@pytest.mark.asyncio
async def test_get_training_advice_empty_when_no_rows():
    from src.db.repositories.intelligence import IntelligenceRepository
    from src.db.connection import ConnectionManager

    conn_manager = ConnectionManager(backend="sqlite", db_path=":memory:")
    repo = IntelligenceRepository(conn_manager)
    await repo.init_tables()

    rows = await repo.get_training_advice()

    assert rows == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `SKIP_LIVE=1 python -m pytest tests/test_training_advice.py -v`
Expected: FAIL — either `AttributeError: 'IntelligenceRepository' object has no attribute 'upsert_training_advice'`, or a "no such table: training_advice" error, depending on test order.

If `ConnectionManager(backend="sqlite", db_path=":memory:")` does not match the real constructor signature, first read `src/db/connection.py`'s `ConnectionManager.__init__` and adjust the test's construction call to match — do not guess; the class exists in this codebase and its exact signature must be read, not assumed.

- [ ] **Step 3: Write the implementation**

In `src/db/repositories/intelligence.py`, add the new table DDL inside `init_tables()` (after the existing `call_analyses` table creation):

```python
        await self._execute("""
            CREATE TABLE IF NOT EXISTS training_advice (
                manager_id INTEGER PRIMARY KEY,
                manager_name TEXT,
                advice_text TEXT,
                generated_at DATETIME
            )
        """)
```

Then add the two new methods (after `init_tables`, before `get_user_intelligence`):

```python
    async def upsert_training_advice(
        self, manager_id: int, manager_name: str, advice_text: str
    ) -> None:
        """Menejer uchun eng so'nggi AI tavsiyasini yozadi (eskisini almashtiradi)."""
        from datetime import datetime, timezone

        await self._execute(
            """
            INSERT OR REPLACE INTO training_advice
                (manager_id, manager_name, advice_text, generated_at)
            VALUES (?, ?, ?, ?)
            """,
            (manager_id, manager_name, advice_text, datetime.now(timezone.utc).isoformat()),
        )

    async def get_training_advice(
        self, manager_id: Optional[int] = None
    ) -> list[Dict[str, Any]]:
        """Keshlangan tavsiyalarni o'qiydi, ixtiyoriy manager_id bo'yicha filtrlaydi."""
        if manager_id is not None:
            cursor = await self._execute(
                "SELECT manager_id, manager_name, advice_text, generated_at "
                "FROM training_advice WHERE manager_id = ?",
                (manager_id,),
            )
        else:
            cursor = await self._execute(
                "SELECT manager_id, manager_name, advice_text, generated_at "
                "FROM training_advice ORDER BY generated_at DESC"
            )
        rows = await cursor.fetchall()
        results = []
        for row in rows:
            if isinstance(row, dict):
                results.append(dict(row))
            else:
                results.append({
                    "manager_id": row[0],
                    "manager_name": row[1],
                    "advice_text": row[2],
                    "generated_at": row[3],
                })
        return results
```

If `cursor.fetchall()` in this codebase's `_execute` return type does not behave this way (check `_fetch_one`'s handling of `SmartRow`/dict rows a few lines below in `base.py` — it already branches on `isinstance(row, dict)`), match that same branching exactly rather than inventing a new row-shape assumption.

- [ ] **Step 4: Run tests to verify they pass**

Run: `SKIP_LIVE=1 python -m pytest tests/test_training_advice.py -v`
Expected: PASS (all 4 tests)

- [ ] **Step 5: Check file line count**

Run: `wc -l src/db/repositories/intelligence.py`

If the result is 400 or more, split `upsert_training_advice`/`get_training_advice` into a `TrainingAdviceMixin` in a new file `src/db/repositories/training_advice.py`, imported and mixed into `IntelligenceRepository` (check how other repositories in this package compose mixins, if any — `src/db/repositories/rop.py` or `src/db/repositories/gamification.py` may already show the pattern; if none do, a plain second class with its own `_execute`/`_get_conn` via `BaseRepository` inheritance, registered as a second attribute on `Database` in `src/db/__init__.py`, is the correct fallback — but only do this if you actually cross 400 lines).

- [ ] **Step 6: Commit**

```bash
git add src/db/repositories/intelligence.py tests/test_training_advice.py
git commit -m "$(cat <<'EOF'
feat(training-advice): add training_advice table and repository methods

Stores one cached AI-generated training tip per manager, written by a
future daily scheduler and read by a future HTTP route — never
generated inside a request.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Daily scheduler — pick weakest manager, generate advice, store it

**Files:**
- Create: `src/schedulers/training_advice_scheduler.py`
- Modify: `src/bootstrap/orchestration/schedulers.py`
- Test: `tests/test_training_advice.py` (append)

**Interfaces:**
- Consumes: `IntelligenceRepository.upsert_training_advice` (Task 1), `_build_manager_cards_payload`/`_fetch_manager_card_rows` (existing, `src/services/sales_quality/helpers.py:256-368` — gives `{"managers": [{"manager_id": int, "name": str, "qualified_leads": int, ...}]}` but NOT `average_score`/`overall_score` per manager — re-check: use `_fetch_call_analysis_rows` + `_build_sales_quality_payload` instead, whose `managers` list has `{"name": str, "avatar": str, "total_calls": int, "average_score": float, "risk_level": str}`, sorted descending by `average_score` — see `src/services/sales_quality/helpers.py:179-195`), `_compute_weak_stages` (existing, `src/services/sales_quality/weak_stages.py`), `get_db()` (existing, `src/database.py`), `FreeAIProviderRouter` + `.generate_text(prompt, max_tokens=..., temperature=...)` (existing, `src/services/utils/free_ai_router.py`)
- Produces: `run_training_advice_cycle()` and `training_advice_loop()`, registered by Task 2's own bootstrap change; no other task depends on these function names directly

**Important interface correction before starting:** `_build_sales_quality_payload`'s `managers` list entries do NOT include a `manager_id` field — only `name` (built from `manager_name` or a `f"Manager-{manager_id}"` fallback). To get both the manager's name AND their numeric `manager_id` AND their `average_score` in one place, call `_fetch_call_analysis_rows()` yourself (same function the payload builder uses) and replicate the small aggregation inline (group by `manager_id`, average `overall_score`) rather than trying to extract `manager_id` back out of the payload's `name` string. This is a deliberate, minimal duplication — reusing `_build_sales_quality_payload` for this internal scheduler purpose would require parsing its display-only `name` field, which is fragile.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_training_advice.py`:

```python
@pytest.mark.asyncio
async def test_run_training_advice_cycle_generates_advice_for_lowest_scoring_manager(monkeypatch):
    from src.schedulers import training_advice_scheduler

    async def fake_fetch_rows():
        return [
            {
                "manager_id": 1,
                "manager_name": "High Scorer",
                "overall_score": 90,
                "scores": '{"etirozlar": 85}',
                "weaknesses": "[]",
            },
            {
                "manager_id": 2,
                "manager_name": "Low Scorer",
                "overall_score": 40,
                "scores": '{"etirozlar": 20}',
                "weaknesses": '["Narx e\'tiroziga tayyor javob yo\'q"]',
            },
        ]

    monkeypatch.setattr(
        "src.schedulers.training_advice_scheduler._fetch_call_analysis_rows",
        fake_fetch_rows,
    )

    captured_prompt = {}

    class FakeProviderResult:
        text = "Sizga E'tirozlar bosqichida mashq tavsiya etiladi."

    class FakeRouter:
        async def generate_text(self, prompt, **kwargs):
            captured_prompt["value"] = prompt
            return FakeProviderResult()

    monkeypatch.setattr(
        "src.schedulers.training_advice_scheduler.FreeAIProviderRouter",
        lambda: FakeRouter(),
    )

    written = {}

    class FakeRepo:
        async def upsert_training_advice(self, manager_id, manager_name, advice_text):
            written["manager_id"] = manager_id
            written["manager_name"] = manager_name
            written["advice_text"] = advice_text

    class FakeDb:
        intelligence = FakeRepo()

    monkeypatch.setattr(
        "src.schedulers.training_advice_scheduler.get_db",
        lambda: FakeDb(),
    )

    await training_advice_scheduler.run_training_advice_cycle()

    assert written["manager_id"] == 2
    assert written["manager_name"] == "Low Scorer"
    assert written["advice_text"] == "Sizga E'tirozlar bosqichida mashq tavsiya etiladi."
    assert "Low Scorer" in captured_prompt["value"]
    assert "etirozlar" in captured_prompt["value"].lower() or "E'tirozlar" in captured_prompt["value"]


@pytest.mark.asyncio
async def test_run_training_advice_cycle_skips_when_no_call_analyses(monkeypatch):
    from src.schedulers import training_advice_scheduler

    async def fake_fetch_rows():
        return []

    monkeypatch.setattr(
        "src.schedulers.training_advice_scheduler._fetch_call_analysis_rows",
        fake_fetch_rows,
    )

    write_calls = []

    class FakeRepo:
        async def upsert_training_advice(self, *args, **kwargs):
            write_calls.append((args, kwargs))

    class FakeDb:
        intelligence = FakeRepo()

    monkeypatch.setattr(
        "src.schedulers.training_advice_scheduler.get_db",
        lambda: FakeDb(),
    )

    await training_advice_scheduler.run_training_advice_cycle()

    assert write_calls == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `SKIP_LIVE=1 python -m pytest tests/test_training_advice.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.schedulers.training_advice_scheduler'`

- [ ] **Step 3: Write the implementation**

Create `src/schedulers/training_advice_scheduler.py`:

```python
"""Kunlik AI trening tavsiyasi scheduleri.

Eng past `overall_score`li menejerni topib, uning eng zaif playbook
bosqichi bo'yicha (`_compute_weak_stages`) AI orqali qisqa tavsiya
generatsiya qiladi va `training_advice` jadvaliga yozadi. AI so'rov
faqat shu kunlik siklda yuboriladi — HTTP so'rov davomida hech qachon
chaqirilmaydi (`/api/sales-quality/training-advice` faqat DB'dan o'qiydi).
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, Dict, List

from src.database import get_db
from src.services.sales_quality.helpers import _fetch_call_analysis_rows, _safe_json_dict
from src.services.sales_quality.weak_stages import _compute_weak_stages, STAGE_LABELS
from src.services.utils.free_ai_router import FreeAIProviderRouter

logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE = """
Sen Jon Branding agentligi uchun sotuv menejerlarini o'qitish bo'yicha AI murabbiysan.

Menejer: {manager_name}
Eng zaif bosqich: {weak_stage_label} (o'rtacha ball: {weak_stage_rate})

Shu menejerga 2-3 gapdan iborat, aniq va amaliy tavsiya yoz — nima ustida
ishlashi kerakligini va qanday qilib yaxshilashi mumkinligini tushuntir.
Javobni FAQAT o'zbek tilida yoz, inglizcha so'zlardan foydalanma.
"""


def _pick_lowest_scoring_manager(rows: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    """Har bir manager_id bo'yicha o'rtacha ball hisoblab, eng pastini qaytaradi."""
    by_manager: Dict[Any, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        manager_id = row.get("manager_id")
        if manager_id is None:
            continue
        by_manager[manager_id].append(row)

    if not by_manager:
        return None

    best_manager_id = None
    best_avg = None
    best_rows: List[Dict[str, Any]] = []
    for manager_id, manager_rows in by_manager.items():
        scores = [r.get("overall_score", 0) for r in manager_rows]
        avg = sum(scores) / len(scores)
        if best_avg is None or avg < best_avg:
            best_avg = avg
            best_manager_id = manager_id
            best_rows = manager_rows

    manager_name = next(
        (r.get("manager_name") for r in best_rows if r.get("manager_name")),
        f"Manager-{best_manager_id}",
    )
    return {"manager_id": best_manager_id, "manager_name": manager_name, "rows": best_rows}


async def run_training_advice_cycle() -> None:
    """Bitta sikl: eng past ballli menejerni topib, tavsiya yozadi."""
    try:
        rows = await _fetch_call_analysis_rows()
    except Exception as exc:
        logger.warning("[TRAINING-ADVICE] Failed to fetch call_analyses: %s", exc)
        return

    if not rows:
        logger.info("[TRAINING-ADVICE] No call_analyses rows yet — skipping cycle.")
        return

    target = _pick_lowest_scoring_manager(rows)
    if target is None:
        logger.info("[TRAINING-ADVICE] No manager_id found in rows — skipping cycle.")
        return

    weak_stage_records = [
        {"scores": r.get("scores"), "weaknesses": r.get("weaknesses")}
        for r in target["rows"]
    ]
    weak_stages = _compute_weak_stages(weak_stage_records, limit=1)
    if not weak_stages:
        logger.info(
            "[TRAINING-ADVICE] No stage data for manager %s — skipping cycle.",
            target["manager_id"],
        )
        return

    weakest = weak_stages[0]
    prompt = _PROMPT_TEMPLATE.format(
        manager_name=target["manager_name"],
        weak_stage_label=weakest["label"],
        weak_stage_rate=weakest["rate"],
    )

    try:
        router = FreeAIProviderRouter()
        result = await router.generate_text(prompt=prompt, max_tokens=400, temperature=0.4)
        advice_text = (result.text or "").strip()
    except Exception as exc:
        logger.warning("[TRAINING-ADVICE] AI generation failed: %s", exc)
        return

    if not advice_text:
        logger.info("[TRAINING-ADVICE] AI returned empty advice — skipping write.")
        return

    db = get_db()
    await db.intelligence.upsert_training_advice(
        manager_id=target["manager_id"],
        manager_name=target["manager_name"],
        advice_text=advice_text,
    )
    logger.info("[TRAINING-ADVICE] Wrote advice for manager_id=%s", target["manager_id"])


async def training_advice_loop() -> None:
    """Har 24 soatda bir marta ishlaydigan orqa fon sikli."""
    await asyncio.sleep(120)  # Boot delay
    logger.info("[TRAINING-ADVICE] Daily loop started.")
    while True:
        try:
            await run_training_advice_cycle()
        except Exception as exc:
            logger.error("[TRAINING-ADVICE] Error in loop: %s", exc)
        await asyncio.sleep(86400)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `SKIP_LIVE=1 python -m pytest tests/test_training_advice.py -v`
Expected: PASS (all 6 tests)

- [ ] **Step 5: Register the loop in the bootstrap scheduler**

In `src/bootstrap/orchestration/schedulers.py`, add after the existing `cloud_brain_synthesizer_loop` block (after line 77's `except ImportError` block, before the `rop_scheduler` block):

```python
    try:
        from src.schedulers.training_advice_scheduler import training_advice_loop
        asyncio.create_task(training_advice_loop(), name="training_advice_loop")
    except ImportError as exc:
        logger.warning("[TRAINING-ADVICE] Daily advice loop unavailable: %s", exc)
```

- [ ] **Step 6: Check file line count**

Run: `wc -l src/schedulers/training_advice_scheduler.py src/bootstrap/orchestration/schedulers.py`

Both should be well under 400 lines. If `schedulers.py` crosses 400 after this addition, that is a pre-existing large file being modified, not something this task should restructure unilaterally — flag it in the commit message as `DONE_WITH_CONCERNS` territory rather than attempting a split, since other schedulers' registrations also live in that same block and a partial split would be inconsistent.

- [ ] **Step 7: Commit**

```bash
git add src/schedulers/training_advice_scheduler.py src/bootstrap/orchestration/schedulers.py tests/test_training_advice.py
git commit -m "$(cat <<'EOF'
feat(training-advice): add daily scheduler that generates and caches advice

Picks the manager with the lowest average call-quality score, finds
their weakest playbook stage via the existing weak-stages aggregation,
and asks the free-AI router for a short training tip once a day.
Registered in start_background_schedulers alongside the other loops.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: `GET /api/sales-quality/training-advice` route (read-only, SELLER-scoped)

**Files:**
- Modify: `src/services/sales_quality/router.py`
- Modify: `src/api/routes/sales_quality.py` (facade)
- Test: `tests/test_training_advice.py` (append)

**Interfaces:**
- Consumes: `IntelligenceRepository.get_training_advice` (Task 1) via `get_db().intelligence.get_training_advice(...)`, `require_permissions`, `Permission.DASHBOARD_READ`, `Role`, `scope_owned_rows` (existing, `src/api/rbac.py` — already imported in `router.py` after the previous sub-project's Critical-finding fix)
- Produces: `get_sales_quality_training_advice` route function, consumed by Task 4 (frontend) via the HTTP endpoint `/api/sales-quality/training-advice`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_training_advice.py`:

```python
@pytest.mark.asyncio
async def test_training_advice_route_returns_unavailable_when_no_rows(monkeypatch):
    from src.services.sales_quality.router import get_sales_quality_training_advice

    class FakeRepo:
        async def get_training_advice(self, manager_id=None):
            return []

    class FakeDb:
        intelligence = FakeRepo()

    monkeypatch.setattr(
        "src.services.sales_quality.router.get_db",
        lambda: FakeDb(),
    )

    result = await get_sales_quality_training_advice()

    assert result["available"] is False
    assert result["advice"] == []


@pytest.mark.asyncio
async def test_training_advice_route_returns_cached_rows(monkeypatch):
    from src.services.sales_quality.router import get_sales_quality_training_advice

    class FakeRepo:
        async def get_training_advice(self, manager_id=None):
            return [
                {
                    "manager_id": 2,
                    "manager_name": "Low Scorer",
                    "advice_text": "E'tirozlar bosqichini mustahkamlang.",
                    "generated_at": "2026-09-15T00:00:00+00:00",
                }
            ]

    class FakeDb:
        intelligence = FakeRepo()

    monkeypatch.setattr(
        "src.services.sales_quality.router.get_db",
        lambda: FakeDb(),
    )

    result = await get_sales_quality_training_advice()

    assert result["available"] is True
    assert result["advice"][0]["manager_name"] == "Low Scorer"


@pytest.mark.asyncio
async def test_training_advice_route_scopes_rows_for_seller_principal(monkeypatch):
    from src.services.sales_quality.router import get_sales_quality_training_advice
    from src.api.rbac import Principal, Role

    class FakeRepo:
        async def get_training_advice(self, manager_id=None):
            return [
                {"manager_id": 1, "manager_name": "Manager One", "advice_text": "A", "generated_at": "t"},
                {"manager_id": 2, "manager_name": "Manager Two", "advice_text": "B", "generated_at": "t"},
            ]

    class FakeDb:
        intelligence = FakeRepo()

    monkeypatch.setattr(
        "src.services.sales_quality.router.get_db",
        lambda: FakeDb(),
    )

    seller = Principal(subject="1", role=Role.SELLER)

    result = await get_sales_quality_training_advice(principal=seller)

    assert result["available"] is True
    assert len(result["advice"]) == 1
    assert result["advice"][0]["manager_id"] == 1
```

If `Principal`'s constructor does not accept `subject`/`role` as shown (check the exact field names used in the existing `test_weak_stages_route_scopes_rows_for_seller_principal` test added during the "Sifat nazorati" sub-project, in this same `tests/test_sales_quality_weak_stages.py` file, and copy its construction call verbatim rather than guessing).

- [ ] **Step 2: Run tests to verify they fail**

Run: `SKIP_LIVE=1 python -m pytest tests/test_training_advice.py -v`
Expected: FAIL with `ImportError: cannot import name 'get_sales_quality_training_advice'`

- [ ] **Step 3: Write the implementation**

In `src/services/sales_quality/router.py`, add the import (extend the existing `from src.database import get_db` if already present from a prior task in this same file, otherwise add it near the other imports at the top):

```python
from src.database import get_db
```

Then add the route (after `get_sales_quality_weak_stages`, before `ingest_sales_quality_analysis`):

```python
@router.get("/api/sales-quality/training-advice")
async def get_sales_quality_training_advice(
    manager_id: int | None = None,
    principal: Principal = require_permissions(Permission.DASHBOARD_READ),
):
    try:
        db = get_db()
        rows = await db.intelligence.get_training_advice(manager_id=manager_id)
    except Exception as exc:
        logger.error("[TRAINING-ADVICE] Read failed: %s", exc)
        return {
            "timestamp": get_local_now().isoformat(),
            "available": False,
            "advice": [],
        }

    if isinstance(principal, Principal) and principal.role is Role.SELLER:
        rows = list(scope_owned_rows(principal, rows, owner_field="manager_id"))

    return {
        "timestamp": get_local_now().isoformat(),
        "available": bool(rows),
        "advice": rows,
    }
```

Note: the SELLER scoping runs AFTER the DB read here (unlike `weak-stages`, which scopes before its own `manager_id` filter) because this route's `manager_id` parameter is a simple pass-through to the repository's own filter, not a second in-memory filter — scoping the already-filtered result is correct and equivalent, since a seller passing another manager's `manager_id` will already get an empty `rows` list from the repository, and `scope_owned_rows` on an empty list returns an empty list regardless.

- [ ] **Step 4: Run tests to verify they pass**

Run: `SKIP_LIVE=1 python -m pytest tests/test_training_advice.py -v`
Expected: PASS (all 9 tests)

- [ ] **Step 5: Re-export from facade**

Read `src/api/routes/sales_quality.py` (already contains re-exports for `get_sales_quality_weak_stages` from the prior sub-project). Add `get_sales_quality_training_advice` to both the import block and `__all__`, in the same style.

- [ ] **Step 6: Run full sales-quality + training-advice test suite**

Run: `SKIP_LIVE=1 python -m pytest tests/test_training_advice.py tests/test_sales_quality_weak_stages.py tests/test_sales_quality_dashboard.py tests/test_sales_quality_coach.py -v`
Expected: PASS, no regressions

- [ ] **Step 7: Commit**

```bash
git add src/services/sales_quality/router.py src/api/routes/sales_quality.py tests/test_training_advice.py
git commit -m "$(cat <<'EOF'
feat(training-advice): add GET /api/sales-quality/training-advice route

Read-only endpoint over the cached training_advice table, RBAC-gated
(DASHBOARD_READ) with SELLER row-scoping to the caller's own
manager_id. Never triggers AI generation — that only happens in the
daily scheduler.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Pytest + bandit gate

**Files:** none (verification only)

**Interfaces:**
- Consumes: everything from Task 1-3
- Produces: nothing new — this is a gate before touching the frontend

- [ ] **Step 1: Run the full pre-flight checklist**

Run: `SKIP_LIVE=1 python -m pytest -q --tb=short`
Expected: PASS, 0 failures (existing suite + new tests)

- [ ] **Step 2: Run bandit**

Run: `bandit -r src/ -ll`
Expected: 0 issues

- [ ] **Step 3: If either fails, fix before proceeding**

No separate commit for this task — it's a checkpoint.

---

### Task 5: Frontend — wire the "Jamoa malakasi" tab to real advice + real "weakest manager" card

**Files:**
- Modify: `apps/web/src/app/(dashboard)/analytics/page.tsx`
- Create: `apps/web/src/app/api/oisha/training-advice/route.ts`

**Interfaces:**
- Consumes: `GET /api/sales-quality/training-advice` (Task 3) — response shape `{available: boolean, advice: Array<{manager_id: number, manager_name: string, advice_text: string, generated_at: string}>}`; `GET /api/sales-quality/manager-cards` — already wired nowhere on this page yet, needed to render the "who needs training now" card with a real name instead of the hardcoded "Baxtiyorjon Gaziyev (Sotuvchi)" block
- Produces: nothing consumed by later tasks (last task in this plan)

- [ ] **Step 1: Create the Next.js proxy route**

Read `apps/web/src/app/api/oisha/weak-stages/route.ts` in full (it already exists from the prior sub-project) and copy its exact structure into a new file `apps/web/src/app/api/oisha/training-advice/route.ts`, changing only the target backend path (`/api/sales-quality/training-advice`) and the error-fallback body shape (`{available: false, advice: [], message: ...}`).

- [ ] **Step 2: Add state and fetch in the page component**

In `apps/web/src/app/(dashboard)/analytics/page.tsx`, find the existing hardcoded state:

```typescript
const [aiRefreshing, setAiRefreshing] = useState(false);
const [aiAdviceText, setAiAdviceText] = useState(
  "Menejer Baxtiyorjon Gaziyevning mijoz ehtiyojlarini aniqlash (B1-B3) bosqichidagi ko'rsatkichlari 38% ga tushib ketgan. ..."
);

const handleRefreshAi = () => {
  setAiRefreshing(true);
  setTimeout(() => {
    setAiRefreshing(false);
    setAiAdviceText("Yangi baholangan 12 ta qo'ng'iroq tahlilidan so'ng: ...");
  }, 1500);
};
```

Replace it with:

```typescript
interface TrainingAdvice {
  manager_id: number;
  manager_name: string;
  advice_text: string;
  generated_at: string;
}

interface TrainingAdviceResponse {
  available: boolean;
  advice: TrainingAdvice[];
}

const [trainingAdvice, setTrainingAdvice] = useState<TrainingAdvice[] | null>(null);
const [aiRefreshing, setAiRefreshing] = useState(false);

const fetchTrainingAdvice = () => {
  setAiRefreshing(true);
  fetch("/api/oisha/training-advice")
    .then((res) => res.json())
    .then((data: TrainingAdviceResponse) => {
      setTrainingAdvice(data.available ? data.advice : []);
    })
    .catch(() => {
      setTrainingAdvice([]);
    })
    .finally(() => {
      setAiRefreshing(false);
    });
};

useEffect(() => {
  fetchTrainingAdvice();
}, []);

const handleRefreshAi = () => {
  fetchTrainingAdvice();
};
```

Place the `TrainingAdvice`/`TrainingAdviceResponse` interfaces near the other interface declarations (after `WeakStagesResponse` from the prior sub-project), and the `useState`/`useEffect` calls near the other tab-specific state blocks (after the `weakStages` block).

- [ ] **Step 3: Replace the hardcoded advice text and manager card in the training tab**

Find the `activeTab === "training"` block. Replace:

```jsx
<p className="text-xs text-text leading-relaxed">
  {aiAdviceText}
</p>
```

with:

```jsx
<p className="text-xs text-text leading-relaxed">
  {aiRefreshing
    ? "Yuklanmoqda..."
    : trainingAdvice && trainingAdvice.length > 0
      ? trainingAdvice[0].advice_text
      : "Hozircha tavsiya mavjud emas — kunlik tahlil hali ishlamagan."}
</p>
```

Replace the hardcoded manager name/initials block:

```jsx
<div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-brand text-white font-bold text-sm">
  BG
</div>
<div>
  <div className="text-xs font-bold text-text">Baxtiyorjon Gaziyev (Sotuvchi)</div>
  <div className="text-[10px] text-text-muted mt-0.5">Focus: Ehtiyojni aniqlash va qiymat tushuntirish</div>
</div>
```

with a version driven by `trainingAdvice?.[0]`:

```jsx
<div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-brand text-white font-bold text-sm">
  {trainingAdvice && trainingAdvice.length > 0
    ? trainingAdvice[0].manager_name
        .trim()
        .split(" ")
        .map((part) => part[0])
        .slice(0, 2)
        .join("")
        .toUpperCase()
    : "--"}
</div>
<div>
  <div className="text-xs font-bold text-text">
    {trainingAdvice && trainingAdvice.length > 0 ? trainingAdvice[0].manager_name : "Ma'lumot yo'q"}
  </div>
</div>
```

Drop the hardcoded `Focus: Ehtiyojni aniqlash va qiymat tushuntirish` line entirely — there is no backend field for a short "focus" summary distinct from the full `advice_text`, and inventing one would violate the project's no-fake-data rule.

- [ ] **Step 4: Manual verification**

Run: `pnpm run dev` and open the Analitika page's "Jamoa malakasi" tab. Confirm: with the backend running and a `training_advice` row present, the real manager name and advice text render; with no rows, the "Hozircha tavsiya mavjud emas" message shows; clicking "AI tavsiyasini yangilash" re-fetches (shows "Yuklanmoqda..." briefly) rather than running the old fake 1.5s timeout.

If this environment has no `node_modules` installed (check with `ls node_modules` at the repo root and in `apps/web`), state that plainly in the task report as a known environment limitation — do not fabricate a browser-check result. Read the JSX changes carefully for balanced tags and correct field references instead, as was done for the prior sub-project's frontend task.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/app/api/oisha/training-advice/route.ts "apps/web/src/app/(dashboard)/analytics/page.tsx"
git commit -m "$(cat <<'EOF'
feat(web): wire Jamoa malakasi tab to real cached training advice

Replaces the hardcoded fake AI-advisor text and manager card with a
real fetch to the cached training-advice endpoint. The refresh button
re-fetches the cache instead of running a fake setTimeout animation.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review Notes

- **Spec coverage**: implements the spec's "2. Jamoa malakasi tab" section in full — `manager-cards` reuse (via the frontend's existing pattern, extended with `training-advice`), the new `training_advice` table, the daily scheduler using `OishaBrain`-equivalent free-text generation (corrected from the spec's stale `brain.generate_response` reference, which does not exist on `OishaBrain` — verified by reading `src/services/core/agent_brain.py` and `src/schedulers/daily_analytics_reporter.py`, which calls a method that was never defined; the actually-working, already-used-elsewhere pattern is `FreeAIProviderRouter.generate_text`, confirmed working in `src/schedulers/cloud_brain_synthesizer.py`), the read-only `training-advice` endpoint, and the frontend button behavior change.
- **Spec deviation flagged**: the spec named `daily_analytics_reporter.py`'s pattern as the model to follow; that file's `brain.generate_response(prompt)` call does not correspond to any method on `OishaBrain` as it exists in this codebase today (verified via `grep -n "def generate_response" src/services/core/agent_brain.py` returning no matches). This plan uses `cloud_brain_synthesizer.py`'s `FreeAIProviderRouter.generate_text` pattern instead, which is verified working code with an existing caller. This is a correction, not a design choice — flagging it explicitly here so a reviewer checking against the spec text understands why the referenced pattern differs from what's implemented.
- **Type consistency**: `upsert_training_advice(manager_id, manager_name, advice_text)` / `get_training_advice(manager_id=None) -> list[dict]` (Task 1) match the route's usage in Task 3 and the scheduler's usage in Task 2 exactly. The route's response shape (`{available, advice: [{manager_id, manager_name, advice_text, generated_at}]}`) matches the frontend's `TrainingAdviceResponse`/`TrainingAdvice` interfaces in Task 5.
- **RBAC consistency carried forward**: Task 3's route applies the same `scope_owned_rows` SELLER guard that was the one Critical finding in the prior sub-project's final review — built in from the start this time, not discovered after the fact.
- **No placeholders**: every step has literal code, not descriptions.
