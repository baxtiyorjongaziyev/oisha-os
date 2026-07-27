# Oisha Real Finance Source Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace finance API 503 placeholders with verified values from the existing Hisobchi Google Sheets store while preserving fail-closed behavior and RBAC.

**Architecture:** Add a small `FinanceSource` protocol and normalized Pydantic domain models. Wrap `HisobchiGsheetStore` in `GoogleSheetsFinanceSource`, validate sheet schema and monetary values, and inject the configured source into finance routes. The API never reads worksheets directly.

**Tech Stack:** Python 3.11, FastAPI, Pydantic, Decimal, gspread, pytest.

## Global Constraints

- No demo or fabricated finance values.
- All monetary calculations use `Decimal`.
- Default finance access is owner/admin through `finance:read` and `finance:write`.
- Missing configuration returns `503 finance_source_not_configured`.
- Source outage returns `503 finance_source_unavailable`.
- Invalid schema/data returns `502 finance_source_invalid`.
- Stale values are marked `freshness: stale` and never described as current.
- Service account credentials stay in the secret store and are never committed.

---

## File Structure

- Create `src/services/core/finance/models.py`: normalized snapshot/transaction models.
- Create `src/services/core/finance/source.py`: source protocol and typed exceptions.
- Create `src/services/core/finance/gsheets_source.py`: Hisobchi adapter.
- Modify `src/services/core/hisobchi_gsheets.py`: safe read-only record methods.
- Modify `src/api/routes/finance_dashboard.py`: dependency injection and response mapping.
- Modify `src/settings.py` and `.env.example`: source configuration.
- Modify `apps/web/src/app/(dashboard)/finance/page.tsx`: real freshness/error states.
- Create unit, route, and staging contract tests.

---

### Task 1: Define finance domain models and source contract

**Files:**
- Create: `src/services/core/finance/models.py`
- Create: `src/services/core/finance/source.py`
- Test: `tests/test_finance_source_contract.py`

**Interfaces:**
- Produces: `FinanceSnapshot`, `FinanceTransaction`, `FinanceSource`, `FinanceSourceNotConfigured`, `FinanceSourceUnavailable`, `FinanceSourceInvalid`.
- Consumes: none.

- [ ] **Step 1: Write failing model tests**

```python
from decimal import Decimal
from src.services.core.finance.models import FinanceSnapshot, FinanceTransaction


def test_snapshot_uses_decimal_and_explicit_freshness():
    snapshot = FinanceSnapshot(
        balance=Decimal("125000.50"),
        monthly_income=Decimal("200000"),
        monthly_expense=Decimal("74999.50"),
        currency="UZS",
        calculated_at="2026-07-26T12:00:00+00:00",
        source_updated_at="2026-07-26T11:59:00+00:00",
        freshness="fresh",
    )
    assert snapshot.balance == Decimal("125000.50")
    assert snapshot.freshness == "fresh"


def test_transaction_rejects_unknown_direction():
    with pytest.raises(ValueError):
        FinanceTransaction(
            id="tx-1", direction="other", amount=Decimal("1"),
            currency="UZS", description="x", occurred_at="2026-07-26T12:00:00+00:00",
            category="Other",
        )
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/test_finance_source_contract.py -q`
Expected: FAIL because models do not exist.

- [ ] **Step 3: Implement models and protocol**

```python
from decimal import Decimal
from typing import Literal, Protocol
from pydantic import BaseModel


class FinanceSnapshot(BaseModel):
    balance: Decimal
    monthly_income: Decimal
    monthly_expense: Decimal
    currency: str
    calculated_at: str
    source_updated_at: str
    freshness: Literal["fresh", "stale"]


class FinanceTransaction(BaseModel):
    id: str
    direction: Literal["income", "expense"]
    amount: Decimal
    currency: str
    description: str
    occurred_at: str
    category: str


class FinanceSource(Protocol):
    async def get_snapshot(self) -> FinanceSnapshot: ...
    async def list_transactions(self, *, limit: int, offset: int) -> list[FinanceTransaction]: ...
```

Define three typed exceptions with stable `code` values.

- [ ] **Step 4: Verify pass**

Run: `pytest tests/test_finance_source_contract.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/services/core/finance/models.py src/services/core/finance/source.py tests/test_finance_source_contract.py
git commit -m "feat(finance): define real source contract"
```

---

### Task 2: Add safe read-only methods to Hisobchi store

**Files:**
- Modify: `src/services/core/hisobchi_gsheets.py`
- Test: `tests/test_hisobchi_gsheets_read_api.py`

**Interfaces:**
- Produces: `read_records(sheet_name)`, `read_source_updated_at(sheet_name)`.
- Consumes: existing worksheet cache and header mappings.

- [ ] **Step 1: Write failing store tests with fake worksheets**

```python

def test_read_records_normalizes_headers(fake_store):
    fake_store._worksheets["Pul oqimi"] = FakeWorksheet([
        {"#": "1", "Sana": "2026-07-26", "Yonalish": "Kirim", "Summa": "125000", "Valyuta": "UZS"}
    ])
    rows = fake_store.read_records("Pul oqimi")
    assert rows[0]["direction"] == "Kirim"
    assert rows[0]["amount"] == "125000"


def test_read_records_rejects_unknown_sheet(fake_store):
    with pytest.raises(KeyError):
        fake_store.read_records("Unknown")
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/test_hisobchi_gsheets_read_api.py -q`
Expected: FAIL because public read methods do not exist.

- [ ] **Step 3: Implement read-only methods**

```python
def read_records(self, sheet_name: str) -> list[dict[str, Any]]:
    if sheet_name not in SHEET_HEADER_TO_KEY:
        raise KeyError(sheet_name)
    worksheet = self._worksheets.get(sheet_name)
    if worksheet is None:
        raise RuntimeError(f"worksheet unavailable: {sheet_name}")
    return [
        {_h2k(sheet_name, header): value for header, value in row.items()}
        for row in worksheet.get_all_records()
    ]
```

`read_source_updated_at()` uses the newest valid `updated_at`, `date`, or transaction timestamp and returns an aware UTC datetime. It must not mutate sheets.

- [ ] **Step 4: Verify pass**

Run: `pytest tests/test_hisobchi_gsheets_read_api.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/services/core/hisobchi_gsheets.py tests/test_hisobchi_gsheets_read_api.py
git commit -m "feat(finance): expose safe Hisobchi read API"
```

---

### Task 3: Implement GoogleSheetsFinanceSource

**Files:**
- Create: `src/services/core/finance/gsheets_source.py`
- Test: `tests/test_google_sheets_finance_source.py`

**Interfaces:**
- Consumes: `HisobchiGsheetStore.read_records()` and finance models.
- Produces: `GoogleSheetsFinanceSource`.

- [ ] **Step 1: Write failing adapter tests**

```python
from decimal import Decimal


async def test_snapshot_reconciles_balance_and_month_totals(fake_store):
    source = GoogleSheetsFinanceSource(fake_store, timezone="Asia/Tashkent", currency="UZS", stale_after_seconds=900)
    snapshot = await source.get_snapshot()
    assert snapshot.balance == Decimal("500000")
    assert snapshot.monthly_income == Decimal("800000")
    assert snapshot.monthly_expense == Decimal("300000")


async def test_invalid_amount_raises_source_invalid(fake_store_with_bad_amount):
    source = GoogleSheetsFinanceSource(fake_store_with_bad_amount, timezone="Asia/Tashkent", currency="UZS", stale_after_seconds=900)
    with pytest.raises(FinanceSourceInvalid):
        await source.get_snapshot()
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/test_google_sheets_finance_source.py -q`
Expected: FAIL because adapter does not exist.

- [ ] **Step 3: Implement strict parsing**

```python
def parse_amount(value: object) -> Decimal:
    normalized = str(value).replace(" ", "").replace(",", ".").strip()
    try:
        return Decimal(normalized)
    except Exception as exc:
        raise FinanceSourceInvalid("invalid_amount") from exc
```

Mapping:

```text
Kirim -> income
Chiqim -> expense
Pul oqimi rows -> transactions and monthly totals
Kassa/Balans rows -> total active balance
newest source timestamp -> freshness
```

Reject missing required columns, mixed unsupported currencies, negative amount where schema forbids it, and invalid dates. Use `asyncio.to_thread()` around blocking gspread reads.

- [ ] **Step 4: Verify pass**

Run: `pytest tests/test_google_sheets_finance_source.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/services/core/finance/gsheets_source.py tests/test_google_sheets_finance_source.py
git commit -m "feat(finance): adapt Hisobchi Google Sheets"
```

---

### Task 4: Configure and inject the source

**Files:**
- Modify: `src/settings.py`
- Modify: `.env.example`
- Create: `src/services/core/finance/factory.py`
- Test: `tests/test_finance_source_factory.py`

**Interfaces:**
- Produces: `get_finance_source() -> FinanceSource`.
- Consumes: settings and adapter.

- [ ] **Step 1: Write failing configuration tests**

```python

def test_missing_spreadsheet_configuration_fails_closed(monkeypatch):
    monkeypatch.delenv("HISOBCHI_SPREADSHEET_ID", raising=False)
    with pytest.raises(FinanceSourceNotConfigured):
        get_finance_source()


def test_factory_builds_gsheets_source(monkeypatch, tmp_path):
    monkeypatch.setenv("HISOBCHI_SPREADSHEET_ID", "sheet-id")
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_FILE", str(tmp_path / "service.json"))
    assert isinstance(get_finance_source(), GoogleSheetsFinanceSource)
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/test_finance_source_factory.py -q`
Expected: FAIL because factory does not exist.

- [ ] **Step 3: Implement exact environment contract**

```dotenv
FINANCE_SOURCE=google_sheets
HISOBCHI_SPREADSHEET_ID=
GOOGLE_SERVICE_ACCOUNT_FILE=/run/secrets/oisha_google_service_account.json
FINANCE_TIMEZONE=Asia/Tashkent
FINANCE_DEFAULT_CURRENCY=UZS
FINANCE_STALE_AFTER_SECONDS=900
```

The factory validates required configuration before constructing the store. Do not log credential paths with secret contents.

- [ ] **Step 4: Verify pass**

Run: `pytest tests/test_finance_source_factory.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/settings.py .env.example src/services/core/finance/factory.py tests/test_finance_source_factory.py
git commit -m "feat(finance): configure finance source"
```

---

### Task 5: Wire the finance API and RBAC

**Files:**
- Modify: `src/api/routes/finance_dashboard.py`
- Modify: `tests/test_finance_dashboard_source.py`
- Create: `tests/test_finance_dashboard_permissions.py`

**Interfaces:**
- Consumes: `get_finance_source()`, `require_permissions(Permission.FINANCE_READ)`.
- Produces: real `/api/finance/dashboard` and `/api/finance/transactions` responses.

- [ ] **Step 1: Replace placeholder tests with real-source tests**

```python

def test_dashboard_returns_normalized_snapshot(client, owner_cookie, fake_source):
    response = client.get("/api/finance/dashboard", cookies=owner_cookie)
    assert response.status_code == 200
    assert response.json()["currency"] == "UZS"
    assert response.json()["freshness"] in {"fresh", "stale"}


def test_missing_source_returns_stable_503(client, owner_cookie):
    response = client.get("/api/finance/dashboard", cookies=owner_cookie)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "finance_source_not_configured"


def test_seller_is_forbidden(client, seller_cookie):
    assert client.get("/api/finance/dashboard", cookies=seller_cookie).status_code == 403
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/test_finance_dashboard_source.py tests/test_finance_dashboard_permissions.py -q`
Expected: FAIL because endpoints still always return 503.

- [ ] **Step 3: Implement route mapping**

```python
@router.get("/api/finance/dashboard")
async def finance_dashboard(
    principal: Principal = require_permissions(Permission.FINANCE_READ),
    source: FinanceSource = Depends(get_finance_source),
):
    return await source.get_snapshot()
```

Map typed source exceptions to the approved 502/503 contracts. Audit finance reads without amounts.

- [ ] **Step 4: Verify pass**

Run: `pytest tests/test_finance_dashboard_source.py tests/test_finance_dashboard_permissions.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/api/routes/finance_dashboard.py tests/test_finance_dashboard_source.py tests/test_finance_dashboard_permissions.py
git commit -m "feat(finance): serve verified finance data"
```

---

### Task 6: Update the finance web page

**Files:**
- Modify: `apps/web/src/app/(dashboard)/finance/page.tsx`
- Create: `apps/web/src/app/(dashboard)/finance/page.test.tsx`

**Interfaces:**
- Consumes: finance API response and 502/503 codes.
- Produces: honest fresh/stale/unavailable UI states.

- [ ] **Step 1: Write failing UI tests**

```tsx
it('labels stale data visibly', async () => {
  render(<FinancePage initialData={{ ...snapshot, freshness: 'stale' }} />);
  expect(screen.getByText(/ma'lumot eskirgan/i)).toBeInTheDocument();
});

it('does not render zeroes when source is unavailable', async () => {
  render(<FinancePage initialError="finance_source_unavailable" />);
  expect(screen.queryByText('0 UZS')).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Verify failure**

Run: `pnpm --filter web test -- finance/page.test.tsx`
Expected: FAIL because explicit states are not implemented.

- [ ] **Step 3: Implement states**

Show source timestamp and freshness. For 502/503, show an unavailable panel and retry control; never substitute `0` values.

- [ ] **Step 4: Verify web checks**

Run: `pnpm run typecheck && pnpm run lint && pnpm run test && pnpm run build`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add 'apps/web/src/app/(dashboard)/finance/page.tsx' 'apps/web/src/app/(dashboard)/finance/page.test.tsx'
git commit -m "feat(web): display real finance source state"
```

---

### Task 7: Staging fixture reconciliation and final verification

**Files:**
- Create: `docs/security/finance-source-runbook.md`
- Create: `tests/fixtures/finance/pul_oqimi.json`
- Create: `tests/fixtures/finance/kassa.json`

**Interfaces:**
- Consumes all previous tasks.
- Produces repeatable staging acceptance evidence.

- [ ] **Step 1: Add deterministic fixture data**

Fixtures must reconcile to exact expected balance, monthly income, and monthly expense. Use synthetic names and IDs only.

- [ ] **Step 2: Run finance suite**

```bash
pytest tests/test_finance_source_contract.py \
  tests/test_hisobchi_gsheets_read_api.py \
  tests/test_google_sheets_finance_source.py \
  tests/test_finance_source_factory.py \
  tests/test_finance_dashboard_source.py \
  tests/test_finance_dashboard_permissions.py -q
```

Expected: PASS.

- [ ] **Step 3: Run full checks**

```bash
pytest -q --tb=short
pnpm run typecheck
pnpm run lint
pnpm run test
pnpm run build
```

Expected: PASS.

- [ ] **Step 4: Validate staging test sheet**

Compare API totals to the controlled sheet manually and record:

```text
source_updated_at
expected balance / API balance
expected monthly income / API monthly income
expected monthly expense / API monthly expense
freshness result
```

- [ ] **Step 5: Commit**

```bash
git add docs/security/finance-source-runbook.md tests/fixtures/finance
git commit -m "docs(finance): add source verification runbook"
```

- [ ] **Step 6: Open PR**

PR title: `feat(finance): connect Oisha to verified Hisobchi data`
