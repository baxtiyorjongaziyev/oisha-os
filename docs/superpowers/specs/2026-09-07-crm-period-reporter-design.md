# CRM Period Reporter — Yagona kunlik/haftalik/oylik hisobot

**Sana:** 2026-09-07
**Status:** Approved (dizayn)
**Muallif:** Oisha-OS / Claude

## Maqsad

amoCRM ko'rsatgichlarini uch davr (kunlik, haftalik, oylik) bo'yicha **bitta
reporterdan** shakllantirish. Har davr:

- Sotuv bo'limi Telegram guruhiga yuboriladi (`-1003854308552`, topic `115`).
- Oisha Dashboard `/analytics` sahifasida "CRM Hisobot" tabida ko'rinadi.
- Telegram matni va dashboard raqamlari **bir manbadan** (`CRMPeriodReporter.build()`)
  keladi — hech qachon ikki joyda hisoblanmaydi.

## Hozirgi holat (nega kerak)

- `src/services/core/crm/daily_report/` paketida kunlik (`CRMStats`) va haftalik
  (`CRMWeeklyStats`) ikki alohida model + kod yo'li bor.
- `src/schedulers/main_loop/periodic_reports.py:122` `reporter.get_weekly_report()`
  ni chaqiradi — **bu metod mavjud emas**, haftalik hisobot ishga tushganda
  crash bo'ladi.
- Oylik hisobot umuman yo'q.
- Kunlik format `contacted`, `qualified`, `avg_response_sec` kabi **proxy**
  (o'rnini bosuvchi taxmin) metrikalarni ko'rsatadi — soxta aniqlik.
- Dashboardда faqat `/api/dashboard/overview` pipeline kartasi (`leads_total`,
  `pipeline_value`, `avg_deal`) bor; to'liq CRM hisobot yo'q.

## Yechim — arxitektura

`src/services/core/crm/daily_report/` paketini **period-agnostic** qilib qayta
yig'ish. Paket nomi o'zgarmaydi (20+ joyda import qilingan). Uch davr bitta
kod yo'lidan o'tadi.

### Modul chegaralari

| Modul | Bitta vazifasi | Kirish interfeysi | Bog'liqligi |
|---|---|---|---|
| `models.py` | Ma'lumot shakli + vaqt diapazoni matematikasi | `PeriodType`, `PeriodMetrics`, `ManagerRow`, `period_range()`, `previous_range()`, `compute_deltas()` | yo'q (sof Python) |
| `fetcher.py` | amoCRM'dan raqamlarni yig'ish | `fetch_metrics(ptype, anchor) -> PeriodMetrics` | amoCRM client |
| `formatter.py` | `PeriodMetrics` -> o'zbekcha Telegram matn | `format_report(ptype, current, previous) -> str` | yo'q |
| `history_db.py` | Snapshot saqlash/yuklash | `save_snapshot()`, `load_snapshot(ptype, period_start)`, `list_snapshots()` | `db_pool` |
| `reporter.py` | Orkestr: fetch -> load prev -> format -> save | `CRMPeriodReporter.build(ptype, anchor=None) -> ReportResult` | yuqoridagi mixinlar |

**Sinov qulayligi:** `formatter` sof funksiya (mock `PeriodMetrics`);
`models.period_range` sana matematikasi (API kerak emas); `fetcher` mock
amoCRM javoblari bilan.

**Bir manba qoidasi:** Telegram scheduler VA API endpoint faqat
`CRMPeriodReporter.build()` ni chaqiradi.

### `ReportResult` (reporter chiqishi)

```python
@dataclass
class ReportResult:
    period_type: PeriodType
    period_start: date
    period_end: date
    metrics: PeriodMetrics          # hozirgi davr
    previous: PeriodMetrics | None  # oldingi davr (delta uchun)
    deltas: dict[str, float]        # {"won_count": +3, "won_amount": -500000, ...}
    telegram_text: str             # tayyor o'zbekcha matn
    fetch_ok: bool = True          # amoCRM javob berdimi
```

### Eski API taqdiri (backward-compat)

- `CRMStats`, `CRMWeeklyStats` -> `PeriodMetrics` ga birlashadi. Eski nomlar
  `models.py` da alias sifatida qoladi; `.total_leads`, `.won`, `.lost`,
  `.revenue`, `.date_label` atributlari `@property` orqali map qilinadi (8+
  chaqiruvchi fayl buzilmasin).
- `fetch_stats()`, `fetch_weekly_stats()`, `format_report(stats, prev)`,
  `format_weekly_report_uz()` -> yupqa wrapperlar, ichkarida `build()` ga
  yo'naltiradi (deprecatsiya izohi bilan).
- Buzuq `get_weekly_report()` -> `CRMPeriodReporter.build(WEEKLY).telegram_text`.

## Ma'lumot modeli

```python
class PeriodType(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"

@dataclass
class ManagerRow:
    user_id: int
    name: str
    won_count: int = 0
    won_amount: float = 0.0
    open_tasks: int = 0
    overdue_tasks: int = 0

@dataclass
class PeriodMetrics:
    period_type: PeriodType
    period_start: date
    period_end: date

    # Bitimlar (davr ichida yaratilgan / yopilgan)
    new_leads: int = 0
    won_count: int = 0
    won_amount: float = 0.0
    lost_count: int = 0
    lost_amount: float = 0.0

    # Snapshot (hozirgi holat, davrdan qat'i nazar)
    active_count: int = 0
    active_amount: float = 0.0
    pipeline_value: float = 0.0
    stagnated_count: int = 0        # ochiq + 3+ kun updated_at tegilmagan

    # Hosila (models.py hisoblaydi, formatter emas)
    win_rate: float = 0.0          # won / (won + lost) * 100
    avg_won_deal: float = 0.0     # won_amount / won_count

    # Odamlar / aloqa
    new_contacts: int = 0
    new_companies: int = 0
    incoming_calls: int = 0

    # Zadachalar
    tasks_created: int = 0
    tasks_completed: int = 0
    tasks_open: int = 0           # snapshot
    tasks_overdue: int = 0        # snapshot: is_completed=0 AND complete_till < now
    leads_without_task: int = 0   # ochiq lead, faol zadacha yo'q

    # Menejerlar (top 5, won_amount desc)
    managers: list[ManagerRow] = field(default_factory=list)

    def to_dict(self) -> dict: ...        # snapshot JSON (date -> isoformat)
    @classmethod
    def from_dict(cls, d) -> "PeriodMetrics": ...

    # backward-compat aliaslar
    @property
    def total_leads(self) -> int: return self.new_leads
    @property
    def won(self) -> int: return self.won_count
    @property
    def lost(self) -> int: return self.lost_count
    @property
    def revenue(self) -> float: return self.won_amount
    @property
    def date_label(self) -> str: return self.period_end.strftime("%b %d, %Y")
```

### Vaqt diapazoni

```python
def period_range(ptype, anchor: date) -> tuple[date, date]:
    DAILY   -> (anchor, anchor)
    WEEKLY  -> (dushanba, yakshanba)  # anchor qaysi haftada bo'lsa
    MONTHLY -> (oyning 1-kuni, oyning oxirgi kuni)

def previous_range(ptype, anchor) -> tuple[date, date]:
    DAILY   -> kecha
    WEEKLY  -> o'tgan hafta
    MONTHLY -> o'tgan oy

def compute_deltas(cur, prev) -> dict[str, float]:
    # prev=None -> {}
    # aks holda har raqamli maydon: cur - prev
```

### Ataylab tushirilgan (proxy metrikalar)

`contacted`, `qualified`, `avg_response_sec` — hisoblanmaydi, ko'rsatilmaydi.
Sabab: aniq ma'lumot yo'q, boshqa raqamdan taxmin qilinadi, hisobotga soxta
aniqlik beradi.

## Fetcher — amoCRM'dan yig'ish

`fetch_metrics(ptype, anchor) -> PeriodMetrics`:

1. `start, end = period_range(ptype, anchor)`; `t_from/t_to` = Unix.
2. Parallel (`asyncio.gather`) amoCRM so'rovlari (mavjud
   `_fetch_amocrm_collection()` helper — pagination + 401 refresh bor):
   - `leads_all` — barcha leadlar (limit=250, max 20 sahifa) -> active/won/lost/
     pipeline/stagnation snapshot
   - `leads_created` — `filter[created_at][from..to]` -> `new_leads`
   - `leads_closed` — `filter[closed_at][from..to]` -> won/lost soni+summa (davr)
   - `contacts_new` — `contacts?filter[created_at]` -> `new_contacts`
   - `companies_new` — `companies?filter[created_at]` -> `new_companies`
   - `calls` — `calls?filter[created_at]` -> `incoming_calls`
   - `tasks_all` — `tasks?filter[is_completed]=0` (sahifalab) -> `tasks_open`,
     `tasks_overdue`, `leads_without_task`
   - `tasks_created` — `tasks?filter[created_at]` -> `tasks_created`
   - `tasks_done` — `tasks?filter[is_completed]=1&filter[updated_at][from..to]`
     -> `tasks_completed`
   - `users` — id->name map (cache) -> manager nomlari
3. Agregatsiya:
   - `WON_STATUS=142`, `LOST_STATUS=143` (reporter sinf konstantasi)
   - `stagnated`: status not in {won,lost} AND `(now - updated_at) > 3*86400`
   - `leads_without_task`: `leads_all` ochiqlaridan, `tasks_all` `entity_id`
     to'plamida yo'qlari
   - `managers`: `leads_closed` won bo'yicha guruhlash -> `ManagerRow`;
     `tasks_all` ochiq/overdue qo'shish -> `won_amount` desc, top 5
   - `win_rate`, `avg_won_deal` -> `models.py`
4. `PeriodMetrics` qaytaradi.

### Xatolarga chidamlilik

- Har so'rov `try/except` — biror endpoint yiqilsa o'sha maydon `0`, qolgani
  ishlaydi.
- 401 -> `refresh_token()` bir marta, qayta urinish.
- amoCRM butunlay javob bermasa -> `PeriodMetrics` barcha nol +
  `ReportResult.fetch_ok=False`. API `available:false`, Telegram "AmoCRM javob
  bermadi".

## Formatter — Telegram matn

`format_report(ptype, current, previous) -> str`. Uch davr bitta shablon.

```
📊 AmoCRM {SARLAVHA} | {davr}
────────────────────────────
🎯 BITIMLAR
  Yangi bitimlar: 12  ▲ +3
  Faol bitimlar: 47 (231 000 000 so'm)
  Yutilgan: 5 (45 000 000 so'm)  ▲ +2
  Yutqazilgan: 2 (8 000 000 so'm)  ▼ -1
  Win rate: 71%  ▲ +12%
  O'rtacha yutilgan bitim: 9 000 000 so'm
  Pipeline qiymati: 231 000 000 so'm
  ⚠️ Stagnatsiya (3+ kun): 8

📞 ALOQA
  Yangi kontaktlar: 15  ▲ +4
  Yangi kompaniyalar: 3
  Kiruvchi qo'ng'iroqlar: 22  ▼ -5

✅ ZADACHALAR
  Yaratilgan: 30  ▲ +6
  Bajarilgan: 25
  Ochiq: 18
  🔴 Muddati o'tgan: 4
  🚨 Zadachasiz ochiq bitimlar: 6

🏆 MENEJERLAR (yutilgan bo'yicha)
  🥇 Oydin — 3 ta / 27 000 000 so'm
  🥈 Jasur — 2 ta / 18 000 000 so'm
     └ ochiq zadacha: 7 | muddati o'tgan: 2
  🥉 Nodira — 0 ta / 0 so'm
     └ 🚨 5 ta ochiq zadacha 24 soatdan beri qarovsiz

────────────────────────────
🔗 AmoCRM'da ochish:
  [Yangi bitimlar](url) · [Yutilgan](url) · [Yutqazilgan](url)

Oisha-OS orqali yuborilgan
```

### Davr farqlari

| Period | SARLAVHA | davr | Delta bazasi | Linklar |
|---|---|---|---|---|
| DAILY | `KUNLIK HISOBOT` | `07.09.2026` | kecha | created/won/lost bugun filter |
| WEEKLY | `HAFTALIK HISOBOT` | `01.09 - 07.09.2026` | o'tgan hafta | hafta filter |
| MONTHLY | `OYLIK HISOBOT` | `Sentyabr 2026` | o'tgan oy | oy filter |

### Qoidalar

- Delta: `▲ +N` / `▼ -N` / `—`; `previous=None` bo'lsa umuman ko'rsatilmaydi.
- Summalar: `1 234 567 so'm` (probel), mavjud `_fmt_money`.
- Bo'sh bo'lim ham ko'rsatiladi ("0" bilan) — izchillik.
- Oddiy matn (hozirgi kod kabi); linklar Markdown `[text](url)`.
- AmoCRM link generatori: mavjud `_weekly_report_links()` umumlashtiriladi ->
  `_period_links(ptype, start, end)`.

### Backward-compat

`format_report(stats, prev)` eski imzo (2 pozitsion arg) -> default `DAILY`;
`stats.period_type` bo'lsa o'shani ishlatadi.

## Snapshot DB

Yangi jadval (`report_history.db` da, `db_pool` orqali sync SQLite):

```sql
CREATE TABLE IF NOT EXISTS crm_report_snapshots (
    period_type   TEXT NOT NULL,       -- 'daily' | 'weekly' | 'monthly'
    period_start  TEXT NOT NULL,       -- ISO date, diapazon boshi
    period_end    TEXT NOT NULL,
    metrics_json  TEXT NOT NULL,       -- PeriodMetrics.to_dict()
    created_at    TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (period_type, period_start)
);
```

### Metodlar (`HistoryDBMixin`)

- `_ensure_db()` — `daily_stats` (eski) + `crm_report_snapshots` (yangi),
  `CREATE IF NOT EXISTS`. Reporter konstruktorida chaqiriladi (migratsiya
  skripti yo'q).
- `save_snapshot(m)` — `INSERT OR REPLACE`.
- `load_snapshot(ptype, period_start)` -> `PeriodMetrics | None`.
- `list_snapshots(ptype, limit=12)` -> `list[PeriodMetrics]` (dashboard tarix
  grafigi uchun, kelajak).

### Eski `daily_stats`

Qoladi (buzmaymiz), yangi kod yozmaydi. `_save_stats()`, `_load_prev_stats()`,
`get_history()` -> deprecatsiya izohi, ichkarida yangi
`save_snapshot`/`load_snapshot(DAILY, ...)`/`list_snapshots(DAILY, ...)` ga
yo'naltiriladi. `get_history(7)` `PeriodMetrics` qaytaradi (aliaslar tufayli
`commands/dashboard.py:107` buzilmaydi).

### Delta oqimi

```
build(WEEKLY):
  cur_start, cur_end = period_range(WEEKLY, today)
  prev_start, _      = previous_range(WEEKLY, today)
  current  = fetch_metrics(WEEKLY, today)
  previous = load_snapshot(WEEKLY, prev_start)
             or fetch_metrics(WEEKLY, prev_anchor)   # birinchi marta
  deltas   = compute_deltas(current, previous)
  text     = format_report(WEEKLY, current, previous)
  save_snapshot(current)
  return ReportResult(...)
```

## Telegram yetkazish (scheduler)

### Yangi sozlamalar (`src/settings.py`)

```python
CRM_SALES_REPORT_GROUP_ID: Optional[int] = -1003854308552
CRM_SALES_REPORT_TOPIC_ID: Optional[int] = 115
```

`.env.example` ga izohli qator. Ikkalasi bo'sh bo'lsa -> hisobot yuborilmaydi
(log warning; fake guruhga ketmaydi).

### `periodic_reports.py` — qayta yozish

```python
async def _send_period_report(ptype, now, task) -> None:
    key = f"crm_{ptype.value}_report_{now:%Y-%m-%d}"
    if _is_job_sent(task, key):
        return
    from src.services.core.crm.daily_report import CRMPeriodReporter
    from src.services.core.crm.crm_service import CRMService
    crm = CRMService()
    if not crm.amocrm:
        return
    result = await CRMPeriodReporter(amocrm=crm.amocrm).build(ptype)
    group = settings.CRM_SALES_REPORT_GROUP_ID
    topic = settings.CRM_SALES_REPORT_TOPIC_ID
    bot_rt = getattr(m, "bot_runtime", None) or getattr(m, "bot_client", None)
    if group and bot_rt:
        kw = {"message_thread_id": topic} if topic else {}
        await bot_rt.send_message(group, result.telegram_text, **kw)
```

### Jadval

| Period | Shart | Vaqt |
|---|---|---|
| DAILY | har kuni | 19:30 |
| WEEKLY | `now.weekday() == 0` | 09:00 |
| MONTHLY | `now.day == 1` | 09:00 |

`run_periodic_reports()`:

```python
if _is_due(now, 19, 30):                              _send_period_report(DAILY)
if now.weekday()==0 and _is_due(now, 9, 0):           _send_period_report(WEEKLY)
if now.day==1 and _is_due(now, 9, 0):                 _send_period_report(MONTHLY)
```

### Eski yo'nalish

- 18:00 efficiency hisobot (`enterprise_reporter`, Hisobchi guruh) — **tegilmaydi**.
- 19:30 eski CRM daily (TN5) — **o'chiriladi**, o'rniga yangi (sotuv guruh).
- Dushanba 9:00 eski weekly (buzuq `get_weekly_report()`) — **almashtiriladi**.
- `bg_monitor/jobs_crm.py:198-218` parallel weekly path -> yangi
  `CRMPeriodReporter.build(WEEKLY)` ga yo'naltiriladi (ikki xil weekly kod yo'q).

### Qo'lda ishga tushirish (Telegram komandalar, `src/commands/dashboard.py`)

- `/report` -> `build(DAILY).telegram_text`
- `/report_week` -> `build(WEEKLY)` (yangi)
- `/report_month` -> `build(MONTHLY)` (yangi)
- `/stats` -> qisqa joriy holat (yangi `PeriodMetrics` maydonlari bilan)
- `/history` -> `list_snapshots(DAILY, 7)`

## API endpoint

### `src/api/routes/crm_reports.py` (yangi)

```python
router = APIRouter(prefix="/api/crm", tags=["crm-reports"])

@router.get("/reports")
async def crm_reports(
    period: Literal["daily", "weekly", "monthly"] = "daily",
    principal: Principal = require_permissions(Permission.DASHBOARD_READ),
):
    amocrm = api_state.amocrm_instance or _get_amocrm_instance()
    if not amocrm:
        return {"available": False, "period": period}
    ptype = PeriodType(period)
    result = await CRMPeriodReporter(amocrm=amocrm).build(ptype)
    return {
        "available": result.fetch_ok,
        "period": period,
        "period_start": result.period_start.isoformat(),
        "period_end": result.period_end.isoformat(),
        "metrics": result.metrics.to_dict(),
        "previous": result.previous.to_dict() if result.previous else None,
        "deltas": result.deltas,
        "telegram_text": result.telegram_text,
    }
```

- `src/services/api_server/core.py` — `include_router(crm_reports_router)`
  (line ~139 yonida, `crm_dashboard_router` bilan birga).
- RBAC: `DASHBOARD_READ` (sotuv jamoasi hisoboti; `FINANCE_READ` shart emas).

## Frontend

### Proxy: `apps/web/src/app/api/oisha/crm-reports/route.ts` (yangi)

Mavjud `dashboard-overview/route.ts` nusxasi, `/api/crm/reports${search}` ga
forward (query string uzatiladi).

### UI: `apps/web/src/app/(dashboard)/analytics/page.tsx`

- Tab ro'yxatiga `"crm-report"` -> `"CRM Hisobot"`.
- Tab ichida period tugmalari: `Kunlik | Haftalik | Oylik` (alohida
  `reportPeriod` state).
- `fetch('/api/oisha/crm-reports?period=' + reportPeriod)`, `useEffect`
  `reportPeriod` ga bog'liq.
- Ko'rinish: 4 karta guruhi — **Bitimlar / Aloqa / Zadachalar / Menejerlar**.
  Raqam yonida delta rangli (`▲` yashil, `▼` qizil).
- Menejerlar — kichik jadval (nom, yutilgan, summa, ochiq zadacha, muddati
  o'tgan).
- `available:false` -> "AmoCRM ulanmagan" placeholder (fake raqam yo'q).
- TS interface `CrmReport` — backend `to_dict()` shakliga mos.
- Collapsible "Xabar matni" bloki -> `telegram_text` (dashboard = Telegram
  isboti).

## Testlar

| Fayl | Nima sinaydi |
|---|---|
| `tests/test_crm_period_models.py` | `period_range`/`previous_range` uch period × chegara sanalar (oy oxiri, yil oxiri, dushanba); `compute_deltas` (prev=None, musbat, manfiy) |
| `tests/test_crm_period_fetcher.py` | mock amoCRM javoblari -> agregatsiya (won/lost/stagnation/tasks/leads_without_task/managers); endpoint yiqilsa graceful |
| `tests/test_crm_period_formatter.py` | `format_report` uch period — sarlavha, davr yorlig'i, delta belgilari, bo'sh bo'lim "0" |
| `tests/test_crm_period_snapshot.py` | `save_snapshot`/`load_snapshot` round-trip; `list_snapshots` tartib; eski `get_history` backward-compat |
| `tests/test_crm_reports_api.py` | `/api/crm/reports?period=` — 3 period, `available:false`, RBAC |
| Backward-compat | mavjud `test_crm_daily_report*.py` yashil qoladi (aliaslar) |

Gate: `SKIP_LIVE=1 python -m pytest -q` + `bandit -r src/ -ll`.

## Aniq bo'lmagan / kelajak (scope tashqarisi)

- Sales cycle time (bitim yaratilgandan yopilgungacha o'rtacha kun) — keyingi
  iteratsiya.
- Bosqichma-bosqich konversiya (stage-by-stage funnel) — keyingi iteratsiya.
- Forecast / prognoz — yo'q.
- Dashboard tarix grafigi (`list_snapshots` dan trend chizish) — infratuzilma
  tayyor, UI keyin.
- LTV — alohida `ltv_predictor`, bu spec tegmaydi.

## O'zgaradigan fayllar (xulosa)

**Python — yangi:**
- `src/api/routes/crm_reports.py`
- `tests/test_crm_period_{models,fetcher,formatter,snapshot}.py`,
  `tests/test_crm_reports_api.py`

**Python — o'zgartiriladi:**
- `src/services/core/crm/daily_report/{models,fetcher,formatter,history_db,reporter}.py`
- `src/services/core/crm/daily_report/__init__.py` (yangi eksportlar:
  `CRMPeriodReporter`, `PeriodType`, `PeriodMetrics`, `ReportResult`)
- `src/services/core/crm/crm_daily_report.py` (facade — yangi nomlar)
- `src/settings.py` (`CRM_SALES_REPORT_GROUP_ID`, `CRM_SALES_REPORT_TOPIC_ID`)
- `src/schedulers/main_loop/periodic_reports.py`
- `src/schedulers/bg_monitor/jobs_crm.py`
- `src/commands/dashboard.py` (`/report_week`, `/report_month`, `/stats`,
  `/history`)
- `src/services/api_server/core.py` (router mount)
- `.env.example`

**TypeScript — yangi:**
- `apps/web/src/app/api/oisha/crm-reports/route.ts`

**TypeScript — o'zgartiriladi:**
- `apps/web/src/app/(dashboard)/analytics/page.tsx`

**Tegmaydi (backward-compat aliaslar bilan ishlaydi):**
- `src/services/core/admin_bot/reports.py`
- `src/services/core/dispatcher/handlers_crm_coach.py`
- `src/handlers/msg_pipeline/admin_commands.py`
- `src/services/reporter/plans.py`
- `src/services/core/crm/daily_report/reporter.py::ReportBot`
