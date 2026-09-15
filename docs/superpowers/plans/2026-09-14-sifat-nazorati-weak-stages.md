# Sifat nazorati — Weak Stages Endpoint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hardcoded fake "weak criteria" cards on the Analitika
page's "Sifat nazorati" tab with a real backend endpoint computed from
`call_analyses.scores`.

**Architecture:** A new pure function in `src/services/sales_quality/helpers.py`
computes per-stage average scores and weak-call counts from already-fetched
`call_analyses` rows. A new route in `src/services/sales_quality/router.py`
wires it to `GET /api/sales-quality/weak-stages`, reusing the existing
`_fetch_call_analysis_rows()` fetcher and RBAC pattern. The frontend tab
replaces its hardcoded array with a `fetch` call following the same
loading/available pattern already used by the Overview tab.

**Tech Stack:** FastAPI (Python 3.11), pytest + pytest-asyncio, Next.js/React
(TypeScript), existing `src/api/rbac.py` permission system.

## Global Constraints

- Production Python files must not exceed 400 lines (AGENTS.md rule 6);
  `helpers.py` is currently 369 lines — new function must fit or the file
  needs splitting (check line count after Task 1, split if it crosses 400).
- Every function must be small (20-60 lines), single-purpose.
- `SKIP_LIVE=1 python -m pytest -q` and `bandit -r src/ -ll` must pass before
  considering any task done.
- No secrets, tokens, or session strings ever appear in code, logs, or
  commit messages.
- Never present fake/sample data as real — missing data always returns
  `{"available": false}`, never a fabricated number.
- Commit messages end with `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`.

---

## File Structure

- **Modify:** `src/services/sales_quality/helpers.py` — add
  `_compute_weak_stages(records: list[dict]) -> list[dict]` pure function
  (no I/O, testable in isolation) and a `STAGE_LABELS` dict mapping the 6
  playbook stage keys to Uzbek display labels.
- **Modify:** `src/services/sales_quality/router.py` — add
  `GET /api/sales-quality/weak-stages` route.
- **Modify:** `src/services/sales_quality/__init__.py` (if it re-exports
  router symbols — check first) and `src/api/routes/sales_quality.py`
  (facade) — re-export the new route function so the facade pattern stays
  consistent with the rest of the file.
- **Test:** `tests/test_sales_quality_weak_stages.py` — new file, unit tests
  for `_compute_weak_stages` and an integration-style test for the route
  function (following the pattern in `tests/test_sales_quality_dashboard.py`).
- **Modify:** `apps/web/src/app/(dashboard)/analytics/page.tsx` — replace the
  hardcoded 4-item array in the `"quality"` tab (lines ~320-362) with a
  `useEffect` fetch + state, matching the `overview`/`crmReport` pattern
  already in the file.

## Interfaces

**`_compute_weak_stages`** (new, in `helpers.py`):
```python
def _compute_weak_stages(records: list[dict], limit: int = 4) -> list[dict]:
    """records: list of call_analyses row-dicts (already have 'scores' and
    'weaknesses' as raw JSON string or already-parsed).
    Returns up to `limit` stage dicts sorted by ascending average rate:
    [{"stage_key": str, "label": str, "rate": float, "count": int,
      "weak_example": str}]
    """
```

**Route** (new, in `router.py`):
```python
@router.get("/api/sales-quality/weak-stages")
async def get_sales_quality_weak_stages(
    manager_id: int | None = None,
    principal: Principal = require_permissions(Permission.DASHBOARD_READ),
) -> dict:
    """Returns {"available": bool, "timestamp": str, "stages": list[dict]}"""
```

---

### Task 1: `_compute_weak_stages` pure function + unit tests

**Files:**
- Modify: `src/services/sales_quality/helpers.py`
- Test: `tests/test_sales_quality_weak_stages.py`

**Interfaces:**
- Consumes: `_safe_json_dict` (existing, line 31), `_safe_json_list`
  (existing, line 19) from the same file
- Produces: `_compute_weak_stages(records, limit=4) -> list[dict]` and
  `STAGE_LABELS: dict[str, str]` module-level constant, used by Task 2

- [ ] **Step 1: Write the failing test**

Create `tests/test_sales_quality_weak_stages.py`:

```python
"""Tests for the weak-stages aggregation used by the Sifat nazorati tab."""
from src.services.sales_quality.helpers import _compute_weak_stages, STAGE_LABELS


def test_compute_weak_stages_empty_records_returns_empty_list():
    assert _compute_weak_stages([]) == []


def test_compute_weak_stages_ranks_lowest_average_first():
    records = [
        {
            "scores": '{"salomlashish": 90, "etirozlar": 40}',
            "weaknesses": '["Etiroz javobi kech berildi"]',
        },
        {
            "scores": '{"salomlashish": 80, "etirozlar": 30}',
            "weaknesses": '["Narx e\'tiroziga tayyor javob yo\'q"]',
        },
    ]

    result = _compute_weak_stages(records, limit=4)

    assert result[0]["stage_key"] == "etirozlar"
    assert result[0]["label"] == "E'tirozlar"
    assert result[0]["rate"] == 35.0
    assert result[0]["count"] == 2  # both calls scored below SCORE_AVERAGE (60)
    assert result[0]["weak_example"] == "Etiroz javobi kech berildi"
    assert result[1]["stage_key"] == "salomlashish"
    assert result[1]["rate"] == 85.0
    assert result[1]["count"] == 0  # neither call scored below 60 on this stage


def test_compute_weak_stages_respects_limit():
    records = [
        {
            "scores": (
                '{"salomlashish": 50, "ehtiyojlar": 55, "qiymat": 60, '
                '"etirozlar": 45, "yakunlash": 70, "muloqot_sifati": 65}'
            ),
            "weaknesses": "[]",
        },
    ]

    result = _compute_weak_stages(records, limit=4)

    assert len(result) == 4
    assert result[0]["rate"] <= result[1]["rate"] <= result[2]["rate"] <= result[3]["rate"]


def test_compute_weak_stages_ignores_rows_with_no_scores():
    records = [
        {"scores": None, "weaknesses": None},
        {"scores": "{}", "weaknesses": "[]"},
    ]

    assert _compute_weak_stages(records) == []


def test_compute_weak_stages_weak_example_blank_when_no_weaknesses():
    records = [
        {"scores": '{"qiymat": 20}', "weaknesses": "[]"},
    ]

    result = _compute_weak_stages(records)

    assert result[0]["stage_key"] == "qiymat"
    assert result[0]["weak_example"] == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `SKIP_LIVE=1 python -m pytest tests/test_sales_quality_weak_stages.py -v`
Expected: FAIL with `ImportError: cannot import name '_compute_weak_stages'`

- [ ] **Step 3: Write the implementation**

In `src/services/sales_quality/helpers.py`, add near the bottom of the file
(after `RADAR_AXES`, before `_MANAGER_CARD_COLUMNS`):

```python
# Playbook bosqich kalitlari (sales_playbook.STAGE_WEIGHTS bilan bir xil) ->
# foydalanuvchiga ko'rinadigan o'zbekcha nom. Yangi bosqich qo'shilsa
# sales_playbook.py va shu lug'at birga yangilanadi.
STAGE_LABELS: Dict[str, str] = {
    "salomlashish": "Salomlashish",
    "ehtiyojlar": "Ehtiyojlarni aniqlash",
    "qiymat": "Qiymat taqdimoti",
    "etirozlar": "E'tirozlar",
    "yakunlash": "Yakunlash",
    "muloqot_sifati": "Muloqot sifati",
}

_WEAK_STAGE_THRESHOLD = 60  # sales_playbook.SCORE_AVERAGE bilan bir xil


def _compute_weak_stages(records: list, limit: int = 4) -> list:
    """`call_analyses` qatorlaridagi `scores` dict'idan har bosqich bo'yicha
    o'rtacha ballni hisoblab, eng past `limit` tasini qaytaradi.

    records: har biri "scores" (JSON dict string yoki dict) va "weaknesses"
    (JSON list string yoki list) kalitlariga ega dict.
    """
    stage_scores: Dict[str, list] = defaultdict(list)
    stage_weak_examples: Dict[str, str] = {}

    for record in records:
        scores = _safe_json_dict(record.get("scores"))
        if not scores:
            continue
        weaknesses = _safe_json_list(record.get("weaknesses"))
        first_weakness = weaknesses[0] if weaknesses else ""

        for stage_key, score in scores.items():
            if stage_key not in STAGE_LABELS or not isinstance(score, (int, float)):
                continue
            stage_scores[stage_key].append(float(score))
            if score < _WEAK_STAGE_THRESHOLD and stage_key not in stage_weak_examples:
                stage_weak_examples[stage_key] = first_weakness

    stages = []
    for stage_key, scores in stage_scores.items():
        rate = sum(scores) / len(scores)
        weak_count = sum(1 for s in scores if s < _WEAK_STAGE_THRESHOLD)
        stages.append({
            "stage_key": stage_key,
            "label": STAGE_LABELS[stage_key],
            "rate": round(rate, 1),
            "count": weak_count,
            "weak_example": stage_weak_examples.get(stage_key, ""),
        })

    stages.sort(key=lambda s: s["rate"])
    return stages[:limit]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `SKIP_LIVE=1 python -m pytest tests/test_sales_quality_weak_stages.py -v`
Expected: PASS (all 5 tests)

- [ ] **Step 5: Check file line count, split if needed**

Run: `wc -l src/services/sales_quality/helpers.py`

If the result is under 400, continue. If 400 or over, stop and split
`STAGE_LABELS` + `_compute_weak_stages` + `_WEAK_STAGE_THRESHOLD` into a new
file `src/services/sales_quality/weak_stages.py`, importing
`_safe_json_dict`/`_safe_json_list` from `helpers.py`, and update the test
file's import path to match. Re-run Step 4 after moving.

- [ ] **Step 6: Commit**

```bash
git add src/services/sales_quality/helpers.py tests/test_sales_quality_weak_stages.py
git commit -m "$(cat <<'EOF'
feat(sales-quality): add weak-stages aggregation over call_analyses.scores

Computes per-playbook-stage average score and weak-call count from
already-fetched call_analyses rows, ranked ascending by average rate.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: `GET /api/sales-quality/weak-stages` route + facade re-export

**Files:**
- Modify: `src/services/sales_quality/router.py`
- Modify: `src/api/routes/sales_quality.py` (facade)
- Test: `tests/test_sales_quality_weak_stages.py` (append)

**Interfaces:**
- Consumes: `_compute_weak_stages`, `STAGE_LABELS` (Task 1),
  `_fetch_call_analysis_rows()` (existing, `helpers.py:93`),
  `require_permissions`, `Permission.DASHBOARD_READ` (existing,
  `src/api/rbac.py`)
- Produces: `get_sales_quality_weak_stages` route function, used by Task 4
  (frontend) via the HTTP endpoint `/api/sales-quality/weak-stages`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_sales_quality_weak_stages.py`:

```python
import pytest
from src.api.routes.state import api_state


@pytest.mark.asyncio
async def test_weak_stages_route_returns_unavailable_when_db_missing(monkeypatch):
    from src.services.sales_quality.router import get_sales_quality_weak_stages

    monkeypatch.setattr(api_state, "db_instance", None)

    result = await get_sales_quality_weak_stages()

    assert result["available"] is False
    assert result["stages"] == []


@pytest.mark.asyncio
async def test_weak_stages_route_filters_by_manager_id(monkeypatch):
    from src.services.sales_quality.router import get_sales_quality_weak_stages

    async def fake_fetch_rows():
        return [
            {
                "manager_id": 1,
                "scores": '{"qiymat": 20}',
                "weaknesses": "[]",
            },
            {
                "manager_id": 2,
                "scores": '{"qiymat": 95}',
                "weaknesses": "[]",
            },
        ]

    monkeypatch.setattr(
        "src.services.sales_quality.router._fetch_call_analysis_rows",
        fake_fetch_rows,
    )

    result = await get_sales_quality_weak_stages(manager_id=1)

    assert result["available"] is True
    assert result["stages"][0]["rate"] == 20.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `SKIP_LIVE=1 python -m pytest tests/test_sales_quality_weak_stages.py -v`
Expected: FAIL with `ImportError: cannot import name 'get_sales_quality_weak_stages'`

- [ ] **Step 3: Write the implementation**

In `src/services/sales_quality/router.py`, add the import and route. First
update the existing import block near the top:

```python
from src.services.sales_quality.helpers import (
    _build_empty_sales_quality,
    _build_manager_cards_payload,
    _build_sales_quality_payload,
    _compute_weak_stages,
    _fetch_call_analysis_rows,
    _fetch_manager_card_rows,
)
```

Then add the route (after `get_sales_quality_manager_cards`, before
`ingest_sales_quality_analysis`):

```python
@router.get("/api/sales-quality/weak-stages")
async def get_sales_quality_weak_stages(
    manager_id: int | None = None,
    principal: Principal = require_permissions(Permission.DASHBOARD_READ),
):
    try:
        rows = await _fetch_call_analysis_rows()
    except Exception as exc:
        logger.error("[SALES QUALITY] Weak-stages read failed: %s", exc)
        return {
            "timestamp": get_local_now().isoformat(),
            "available": False,
            "stages": [],
        }

    records = [
        {"manager_id": getattr(r, "manager_id", None) if not isinstance(r, dict) else r.get("manager_id"),
         "scores": getattr(r, "scores", None) if not isinstance(r, dict) else r.get("scores"),
         "weaknesses": getattr(r, "weaknesses", None) if not isinstance(r, dict) else r.get("weaknesses")}
        for r in rows
    ]
    if manager_id is not None:
        records = [r for r in records if r.get("manager_id") == manager_id]

    stages = _compute_weak_stages(records)
    return {
        "timestamp": get_local_now().isoformat(),
        "available": bool(stages),
        "stages": stages,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `SKIP_LIVE=1 python -m pytest tests/test_sales_quality_weak_stages.py -v`
Expected: PASS (all 7 tests)

- [ ] **Step 5: Re-export from facade**

Read `src/api/routes/sales_quality.py` first (already read during spec —
it re-exports names from `router.py` via `__all__`). Add
`get_sales_quality_weak_stages` to both the `from src.services.sales_quality.router
import (...)` block and the `__all__` list, matching the existing style for
`get_sales_quality_overview`.

- [ ] **Step 6: Run full sales-quality test suite**

Run: `SKIP_LIVE=1 python -m pytest tests/test_sales_quality_weak_stages.py tests/test_sales_quality_dashboard.py tests/test_sales_quality_coach.py -v`
Expected: PASS, no regressions

- [ ] **Step 7: Commit**

```bash
git add src/services/sales_quality/router.py src/api/routes/sales_quality.py tests/test_sales_quality_weak_stages.py
git commit -m "$(cat <<'EOF'
feat(sales-quality): add GET /api/sales-quality/weak-stages route

Exposes the weak-stages aggregation over HTTP with RBAC (DASHBOARD_READ)
and an optional manager_id filter. Fails closed (available: false) when
the database is unreachable.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Bandit + full backend test suite check

**Files:** none (verification only)

**Interfaces:**
- Consumes: everything from Task 1 and Task 2
- Produces: nothing new — this is a gate before touching the frontend

- [ ] **Step 1: Run the full pre-flight checklist**

Run: `SKIP_LIVE=1 python -m pytest -q --tb=short`
Expected: PASS, 0 failures (existing suite + new tests)

- [ ] **Step 2: Run bandit**

Run: `bandit -r src/ -ll`
Expected: 0 issues (the new code has no subprocess/eval/SQL-string-format
patterns, so this should pass cleanly)

- [ ] **Step 3: If either fails, fix before proceeding**

Do not start Task 4 until both commands above pass clean. There is no
separate commit for this task — it's a checkpoint.

---

### Task 4: Frontend — wire the Sifat nazorati tab to the real endpoint

**Files:**
- Modify: `apps/web/src/app/(dashboard)/analytics/page.tsx`

**Interfaces:**
- Consumes: `GET /api/sales-quality/weak-stages` (Task 2) — response shape
  `{available: boolean, timestamp: string, stages: Array<{stage_key: string,
  label: string, rate: number, count: number, weak_example: string}>}`
- Produces: nothing consumed by later tasks (this is the last task in this
  plan)

- [ ] **Step 1: Check how the Next.js API proxy layer works**

Read `apps/web/src/app/api/oisha/dashboard-overview/route.ts` (already
confirmed to exist during spec research) to see the exact proxy pattern used
for `/api/oisha/dashboard-overview` — same pattern must be replicated for
this new endpoint before the frontend page can call it.

- [ ] **Step 2: Add the Next.js proxy route**

Create `apps/web/src/app/api/oisha/weak-stages/route.ts` with the same
structure as `dashboard-overview/route.ts` (forwarding to the backend's
`/api/sales-quality/weak-stages`, same auth header handling). Copy the
existing file's structure exactly — do not introduce a new pattern.

- [ ] **Step 3: Add state and fetch in the page component**

In `apps/web/src/app/(dashboard)/analytics/page.tsx`, add near the other
`interface` declarations (after `CrmReport`):

```typescript
interface WeakStage {
  stage_key: string;
  label: string;
  rate: number;
  count: number;
  weak_example: string;
}

interface WeakStagesResponse {
  available: boolean;
  stages: WeakStage[];
}
```

Add state near the other `useState` declarations (after `crmReportError`):

```typescript
const [weakStages, setWeakStages] = useState<WeakStage[] | null>(null);
const [weakStagesLoading, setWeakStagesLoading] = useState(true);
```

Add a `useEffect` near the existing `dashboard-overview` fetch effect:

```typescript
useEffect(() => {
  let cancelled = false;
  fetch("/api/oisha/weak-stages")
    .then((res) => res.json())
    .then((data: WeakStagesResponse) => {
      if (!cancelled) setWeakStages(data.available ? data.stages : []);
    })
    .catch(() => {
      if (!cancelled) setWeakStages([]);
    })
    .finally(() => {
      if (!cancelled) setWeakStagesLoading(false);
    });
  return () => {
    cancelled = true;
  };
}, []);
```

- [ ] **Step 4: Replace the hardcoded array in the quality tab**

Find the `activeTab === "quality"` block (currently around line 313-364).
Replace the hardcoded array:

```typescript
{ code: "A2", name: "Murojaat manbasini aniqlash", rate: 16, count: 24, weakDesc: "...", hint: "..." },
```

with a render driven by `weakStages` state. Replace the `.map((item) => (...))`
block's data source from the hardcoded array to `weakStages`, and adjust the
field names used inside the JSX (`item.code` → `item.stage_key`, `item.name`
→ `item.label`, `item.rate` → `item.rate`, `item.count` → `item.count`,
`item.weakDesc` → `item.weak_example`, drop `item.hint` — there is no hint
field from the backend, remove that line from the JSX). Add a loading state
(`weakStagesLoading ? <p>Yuklanmoqda...</p> : ...`) and an empty state when
`weakStages` is an empty array (`<div>Ma'lumot yetarli emas</div>` matching
the empty-state style already used elsewhere on the page, e.g. the
`crmReportError` block).

- [ ] **Step 5: Manual verification**

Run: `pnpm run dev` (from repo root or `apps/web`, per existing `package.json`
scripts) and open the Analitika page's "Sifat nazorati" tab in a browser.
Confirm: with backend running and `call_analyses` rows present, real stage
names and rates render; with backend down, the page shows the empty state
instead of a fetch error crashing the tab.

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/app/api/oisha/weak-stages/route.ts apps/web/src/app/\(dashboard\)/analytics/page.tsx
git commit -m "$(cat <<'EOF'
feat(web): wire Sifat nazorati tab to real weak-stages endpoint

Replaces the hardcoded A1-E3 fake criteria cards with real per-stage
averages computed from call_analyses.scores.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review Notes

- **Spec coverage**: Task 1-2 implement the "Sifat nazorati tab" backend
  section of the spec (renamed `weak-criteria` → `weak-stages` to match the
  corrected stage-based data model). Task 4 implements the corresponding
  frontend section. The spec's other 4 sections (Jamoa malakasi, Mijoz
  tahlili, Lid analitikasi, Marketing ROI) are out of scope for this plan —
  each gets its own plan per the spec's "Amalga oshirish tartibi".
- **Type consistency**: `_compute_weak_stages` return shape
  (`stage_key`/`label`/`rate`/`count`/`weak_example`) is used identically in
  Task 2's route response and Task 4's TypeScript interface.
- **No placeholders**: every step has literal code, not descriptions.
