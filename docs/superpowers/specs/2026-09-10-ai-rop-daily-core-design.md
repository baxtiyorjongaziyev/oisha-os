# AI ROP — Sotuv bo'limi rahbari (Daily Core) — Design

**Date:** 2026-09-10
**Status:** Approved (brainstorm), pending spec review
**Scope:** Sections §1–§8 of the AI ROP brief (daily execution core).
**Out of scope (separate specs later):** §9 team bonus, §10 non-material motivation / leaderboard,
§11 coaching layer, §12 Sales HR, §13 full Telegram command/button interface.

---

## 1. Purpose

AI ROP is an orchestration layer inside Oisha-OS that runs the sales team's daily rhythm off
AmoCRM as the single source of truth for sales execution. It does not babysit sellers; it
systematises regular output:

- Every working day it produces, per seller, a **morning priority plan**, a **midday
  plan-vs-fakt check** (only if the seller is behind), and an **evening result summary**.
- It computes a deterministic **closing-likelihood** per active deal and an **expected
  revenue** estimate for the day (always labelled as an estimate, never as fact).
- It enforces **amoCRM discipline** ("vazifasiz bitim — yo'qotilgan bitim"): every active
  lead must have a next task, no overdue tasks, no stagnation.
- It gives the CEO a **traffic-light** roll-up (🟢/🟡/🔴) so the CEO sees only exceptions,
  not day-to-day task noise.
- It tracks the **weekly team plan** (sales + revenue) live.

Interaction is internal-only: DMs to sellers and one CEO channel. No customer contact.

---

## 2. Architecture

### 2.1 Module layout

New pure-logic package `src/services/core/rop/` (no side effects except AmoCRM reads in
`fetchers.py`), plus one scheduler and one DB repository.

```
src/services/core/rop/
  __init__.py
  fetchers.py        # AmoCRM reads: active sales leads (paged), today's completed tasks,
                     #   today's events, recent WON events (<=7d), user-id -> name
  targets.py         # rop_targets load + roster (sellers == rows), default-seed helper
  config.py          # rop_config key-value load + default-seed (score weights, traffic
                     #   thresholds, weekly targets, band cutoffs, pace pct)
  scoring.py         # deterministic closing-likelihood: features -> {score, band, reasons}
  daily.py           # SellerMorningPlan / SellerMiddayCheck / SellerEveningResult builders
  discipline.py      # per-seller discipline findings
  traffic_light.py   # GREEN/YELLOW/RED per seller + team, from config thresholds
  weekly.py          # live weekly team progress from WON since Monday 00:00 Tashkent
  rop_messages.py    # Uzbek (Latin) HTML template builders for every message
  service.py         # RopService.run(slot) -> orchestrates fetch -> compute -> build
                     #   -> returns list[(chat_id, html_text)]

src/schedulers/rop_scheduler.py
                     # 3 asyncio loops: morning 09:00, midday 14:00, evening 18:30 (Tashkent)

src/db/repositories/rop.py
                     # RopRepository: rop_targets + rop_config CRUD, init_table()
```

### 2.2 Design-for-isolation notes

- `scoring.py`, `traffic_light.py`, `discipline.py`, `weekly.py`, and the `daily.py`
  builders are **pure functions** over plain dicts/dataclasses. No network, no DB, no clock
  except an injected `now`. This is what makes them unit-testable with fixture tables.
- `fetchers.py` is the only module that talks to AmoCRM. It returns plain structures.
- `rop_messages.py` only formats; it never computes thresholds or ordering.
- `service.py` is the only place that wires fetch → compute → format. It returns a
  **delivery plan** (`list[(chat_id, text)]`); it does not send. The scheduler sends.
- `rop_scheduler.py` owns timing, the `ROP_ENABLED` gate, quiet-hours safety, the Mon–Sat
  rule, bot sending, and audit logging.

Each unit answers: *what it does / how you call it / what it depends on* — kept small enough
to hold in context for reliable edits.

### 2.3 Wiring

- `src/db/__init__.py` facade: add `self.rop = RopRepository(self.conn_manager)` and
  `await self.rop.init_table()` in the existing boot init chain (same pattern as
  `GamificationRepository`).
- `src/boot.py`: register the three loops guarded by `ROP_ENABLED` (default **off**), same
  `asyncio.create_task(..., name=...)` pattern as `frog_scheduler` / `ai_autopilot_loop`.
- Bot delivery via the existing `BotRuntimePort` / `_as_bot_runtime` helper (messages come
  from the bot account, never the userbot — same as `frog_scheduler`).

### 2.4 Data flow per run

```
rop_scheduler slot fires (09:00 / 14:00 / 18:30 Tashkent, Mon–Sat, ROP_ENABLED=1,
    not inside quiet-hours)
  -> RopService.run(slot)
       -> targets.load_roster()            # sellers with an active rop_targets row
       -> config.load()                    # thresholds / weights / weekly targets
       -> fetchers.fetch_active_sales_leads()      # 1 paged call, SALES_PIPELINE_ID,
       ->                                          #   with=contacts, excl. WON/LOST
       -> fetchers.fetch_today_completed_tasks()   # 1 call, filter completed + today
       -> fetchers.fetch_today_events()            # 1 call, today's events
       -> fetchers.fetch_recent_won_events()       # 1 call, <=7d (evening + Monday only)
       -> per seller, in memory:
            scoring.score_lead() for each active lead
            daily.build_<slot>()             # morning / midday / evening model
            discipline.find()                # morning only (also feeds traffic light)
            traffic_light.evaluate()         # midday + evening
            weekly.progress()                # evening + Monday morning
       -> rop_messages.build_*()             # HTML per seller + CEO
  -> returns [(chat_id, text), ...]
scheduler sends each via bot runtime (retry once), then audit-logs the run
```

Bounded AmoCRM cost: ~3 requests/run (morning/midday), ~4–5/run (evening + Monday).

---

## 3. Database

Via `database_pool` / `RopRepository` with `CREATE TABLE IF NOT EXISTS` in `init_table()`
(the live repo pattern; the `MigrationRunner` class is currently unused elsewhere).

### 3.1 `rop_targets` — roster + per-seller daily targets

| column | type | notes |
|---|---|---|
| `responsible_user_id` | INTEGER PRIMARY KEY | AmoCRM user id |
| `seller_name` | TEXT | display name (cache; `fetchers` refreshes) |
| `telegram_user_id` | INTEGER | DM target; NULL ⇒ DM skipped, seller listed to CEO |
| `expected_sales` | INTEGER NOT NULL DEFAULT 1 | |
| `calls` | INTEGER NOT NULL DEFAULT 10 | |
| `follow_ups` | INTEGER NOT NULL DEFAULT 20 | |
| `meetings` | INTEGER NOT NULL DEFAULT 2 | |
| `proposals` | INTEGER NOT NULL DEFAULT 0 | KP/proposal count target (0 ⇒ not tracked) |
| `payments` | INTEGER NOT NULL DEFAULT 1 | |
| `max_overdue` | INTEGER NOT NULL DEFAULT 0 | |
| `active` | INTEGER NOT NULL DEFAULT 1 | 0 ⇒ excluded from roster |
| `updated_at` | TEXT NOT NULL | ISO-8601 UTC |

A seller **is** managed by AI ROP iff they have a row with `active = 1`. Enrolment = insert a
row. Editing UI is §13 (out of scope); for v1, rows are seeded/edited directly or via a
one-off script.

Default seed: none automatically (empty roster ⇒ run no-ops with one CEO notice). A helper
`targets.seed_default(responsible_user_id, telegram_user_id, name)` writes a row with the
brief's defaults.

### 3.2 `rop_config` — key/value tuning

| column | type |
|---|---|
| `key` | TEXT PRIMARY KEY |
| `value_json` | TEXT NOT NULL |
| `updated_at` | TEXT NOT NULL |

Seeded keys (defaults from the brief; `config.load()` fills any missing key on read):

| key | default | used by |
|---|---|---|
| `score.weights` | see §4.2 table | `scoring` |
| `score.stage_weights` | `{ "<status_id>": 0.0..1.0 }` (curated) | `scoring` |
| `score.band_cutoffs` | `{ "hot": 70, "warm": 40 }` | `scoring` |
| `score.objection_keywords` | `["qimmat","narx","budjet","keyin","o'ylab"]` | `scoring` |
| `score.payment_keywords` | `["to'lov","oplata","perevod","karta","hisob"]` | `scoring` |
| `discipline.stagnant_days` | `3` | `discipline` |
| `discipline.terminal_stage_ids` | `[]` (curated) | `discipline` |
| `traffic.red_no_result_days` | `3` | `traffic_light` |
| `traffic.red_overdue_count` | `5` | `traffic_light` |
| `traffic.red_discipline_count` | `8` | `traffic_light` |
| `traffic.big_deal_amount` | `10000000` | `traffic_light` |
| `traffic.stuck_deal_days` | `14` | `traffic_light` |
| `traffic.yellow_pace_pct` | `0.5` | `traffic_light` |
| `traffic.hot_lead_silent_hours` | `48` | `traffic_light` |
| `midday.pace_pct` | `0.4` | `daily.build_midday` (on-track test) |
| `weekly.sales_target` | `10` | `weekly` |
| `weekly.revenue_target` | `100000000` | `weekly` |

---

## 4. Closing-likelihood scoring (§3)

`scoring.score_lead(features: dict, config: dict, now: datetime) -> ScoreResult`

`ScoreResult = { score: int (0..100), band: "HOT"|"WARM"|"COLD", reasons: list[str] }`

### 4.1 Features derived per active lead

From the lead JSON + its tasks/events/notes already in memory:

| feature | derivation |
|---|---|
| `stage_weight` | `config["score.stage_weights"].get(str(status_id), 0.15)` |
| `last_interaction_hours` | `now - max(last event/task-completed/note time)` |
| `has_open_next_task` | any open (not-completed) task on the lead |
| `task_overdue` | any open task with `complete_till < now` |
| `proposal_sent` | stage at/after KP **or** a note/field marker |
| `meeting_held` | a completed meeting-type task exists |
| `objection_open` | note/field text matches `score.objection_keywords` and no later resolution marker |
| `payment_promised` | note/field text matches `score.payment_keywords` |
| `days_in_stage` | `now - last stage-change event` (fallback: `now - created_at`) |

### 4.2 Weighted sum (weights in `score.weights`, clamped to 0..100)

| signal | contribution |
|---|---|
| `stage_weight` | `+ round(stage_weight * 40)` |
| `has_open_next_task` | `+10` if true, else `-10` |
| `proposal_sent` | `+12` |
| `meeting_held` | `+12` |
| `payment_promised` | `+20` |
| `last_interaction_hours` | `0–24h: +8`, `24–72h: 0`, `>72h: -12` |
| `objection_open` | `-10` |
| `task_overdue` | `-12` |
| `days_in_stage` | `<=7: +5`, `8–21: 0`, `>21: -10` |

Bands: `HOT` if `score >= band_cutoffs.hot` (70), `WARM` if `>= band_cutoffs.warm` (40),
else `COLD`.

`reasons`: one short Uzbek string per non-zero contribution (e.g. `"KP yuborilgan"`,
`"72 soatdan beri aloqa yo'q"`, `"to'lov va'da qilingan"`). Rendered under an explicit
disclaimer line: **"AI bahosi (taxminiy), fakt emas."**

### 4.3 Expected revenue

Per seller: `expected_revenue = sum(lead.price * score/100 for lead in HOT + WARM)`.
Team: sum of seller values. Always rendered as `"Expected: X mln so'm (taxminiy)"`.

### 4.4 Tests

Table of synthetic feature dicts → assert `score` within an expected range and `band`.
No network, injected `now`.

---

## 5. Daily phases (§1, §2, §4, §5)

All models are dataclasses built in `daily.py`. One DM per active seller per slot (with the
midday suppression rule below); one CEO message per slot.

### 5.1 09:00 Morning — `SellerMorningPlan`

Per seller:

- `top_closings`: active leads sorted by `score` desc, top 3 — each `{name, band,
  reason (1 line), action}` where `action` ∈ {`"bugun qo'ng'iroq"`, `"follow-up"`,
  `"narx objection yop"`, `"uchrashuv belgila"`} chosen from the dominant reason.
- `today_targets`: the `rop_targets` row.
- `open_tasks_count`, `overdue_tasks`: `list[{lead_name, task_text}]`.
- `followup_due`: leads with a follow-up-type open task due today.
- `expected`: `list[{lead_name, revenue_est, score}]` for HOT+WARM, plus
  `expected_revenue_total`.
- `discipline_block`: up to 5 discipline findings (see §6), remainder as `"+N ta yana"`.

Message layout follows the brief's §1/§3 example (Uzbek, HTML).

**CEO 09:00** — team roll-up: `total_expected_sales`, `total_expected_revenue`,
`total_overdue`, `seller_count`, sellers with missing `telegram_user_id`.
**Monday only:** prepend a weekly recap block — last ISO week actual sales/revenue vs
`weekly.*` targets.

### 5.2 14:00 Midday — `SellerMiddayCheck`

- `plan` = `expected_sales` target; `fakt` = WON leads for this seller today.
- `done` vs `target` for `calls` / `follow_ups` / `meetings` — actuals from **completed
  tasks today bucketed by task type**.
- `hot_not_touched`: HOT-band leads with no task/event/note today (`list[name]`).
- `priority_now`: top 3 not-yet-touched-today leads by `score`.
- `on_track: bool` — **true** iff every tracked bucket `done >= midday.pace_pct * target`
  **and** `hot_not_touched == []`.

**Suppression:** if `on_track` is true, **no DM is sent** to that seller (brief: "hammasi
normada bo'lsa, ortiqcha notification yuborma").

**CEO 14:00** — only sellers **not** on track (name + the failing bucket), plus a team
traffic-light line if any seller is YELLOW/RED. If everyone is on track: a single
`"🟢 Sales Department — hammasi rejada"` line.

### 5.3 18:30 Evening — `SellerEveningResult`

- `sales` done/target; `revenue` won today.
- `calls` / `follow_ups` / `meetings` done/target; `overdue` end-of-day count.
- `tomorrow_closings`: top 2–3 leads by `score` for the next working day.

Always sent to the seller.

**CEO 18:30 — `CeoDashboard`** (brief §5):

- Team: `Plan` / `Fakt` / `Revenue` / `Expected tomorrow` / `Overdue`.
- Weekly: `won_this_week / weekly.sales_target` + pct (live from `weekly.progress()`).
- Per-seller traffic-light line (🟢/🟡/🔴); only 🟡/🔴 carry a one-line reason.
- **No** individual task detail (brief: "CEOga mayda tasklar kerak emas").

---

## 6. amoCRM discipline (§7)

`discipline.find(seller_leads, seller_tasks, seller_events, config, now) -> list[Finding]`
`Finding = { lead_name: str, type: str, detail: str }`

| type | condition |
|---|---|
| `NO_NEXT_TASK` | active lead with no open task |
| `OVERDUE_TASK` | active lead with an open task past `complete_till` |
| `STAGNANT` | no interaction for `> discipline.stagnant_days` |
| `NO_OWNER` | active lead with null `responsible_user_id` (team-level → surfaced to CEO) |
| `WRONG_STAGE` | WON/LOST but has an open task, **or** active in a `discipline.terminal_stage_ids` stage |
| `IMPORTANT_NO_NOTE` | a call/meeting-type task completed **today** with no note added to the lead |

Morning DM shows the seller's findings (max 5 lines + `"+N ta yana"`). `NO_OWNER` findings
go to the CEO 09:00 message, not to a seller. Finding counts feed `traffic_light`.

Per the brief: after any completed task, if the lead has no next task →
`"⚠️ <lead> — keyingi task yo'q."`

---

## 7. Traffic light (§6)

`traffic_light.evaluate(seller_metrics, discipline_findings, config, now) -> {level, reasons}`
`level ∈ {"GREEN","YELLOW","RED"}`, `reasons: list[str]` (Uzbek, 1 line each).

**RED** if any:

- `won_today == 0` **and** `no_result_streak_days >= traffic.red_no_result_days` (3)
- `overdue_count >= traffic.red_overdue_count` (5)
- a lead with `price >= traffic.big_deal_amount` stuck `>= traffic.stuck_deal_days` (14)
- `len(discipline_findings) >= traffic.red_discipline_count` (8)

**YELLOW** (if not RED) if any:

- by evening, any tracked bucket `done < traffic.yellow_pace_pct * target` (0.5)
- `follow_ups_done < 0.5 * follow_ups_target`
- a HOT lead silent `>= traffic.hot_lead_silent_hours` (48)
- a lead that was HOT earlier today dropped a band (needs the morning snapshot — see §8)

**GREEN** otherwise.

`no_result_streak_days`: computed live — count consecutive prior **working** days (Mon–Sat)
with zero WON for that seller, scanning `fetch_recent_won_events()` (≤7d). No stored counter.

---

## 8. Weekly plan (§8)

`weekly.progress(won_events_since_monday, config, now) -> { won_count, won_revenue,
sales_target, revenue_target, sales_pct, revenue_pct, per_day: list[(date, cumulative)] }`

- `sales_target` / `revenue_target` from `rop_config` (`weekly.sales_target` = 10,
  `weekly.revenue_target` = 100_000_000).
- Progress computed live each run from AmoCRM WON leads with `closed_at >= Monday 00:00
  Tashkent`. **Stateless** — no `rop_weekly` table, no reset job, no drift on downtime.
- Rendered in the CEO 18:30 dashboard (current pct) and the CEO Monday 09:00 message
  (previous week's final numbers vs target).

### Band-drop detection (small stored state)

To support the YELLOW "previously-HOT lead dropped a band" rule, the morning run writes a
lightweight per-day snapshot to `rop_config` under key `snapshot.<YYYY-MM-DD>` =
`{ "<lead_id>": band }`. Midday/evening read it; a nightly-free cleanup drops snapshots
older than 2 days at the start of each morning run. (Kept in `rop_config` to avoid a third
table; value is small.)

---

## 9. Scheduler (`rop_scheduler.py`)

Three `async def *_loop()` functions, each: sleep until the next Tashkent slot time →
run → sleep ~60s past the slot to avoid double-fire → repeat.

Gates before each run:

- `ROP_ENABLED == "1"` (env; default off) — else the loop sleeps a slot and rechecks.
- Weekday is Mon–Sat (`get_local_now().weekday() != 6`) — Sunday skipped.
- Not inside quiet-hours (23:00–07:00 Tashkent) — safety no-op; the three slots are all
  inside working hours so this only bites if the clock is wrong.
- `DISABLE_UNSOLICITED_REPORTS != "1"` (respect the existing global mute, like
  `frog_scheduler`).

Run:

```
plan = await RopService.run(slot)          # [(chat_id, html), ...]
for chat_id, text in plan:
    ok = await bot_runtime.send_message(chat_id, text)   # retry once on failure
    if not ok: audit-log a drop
audit-log the run (slot, seller_count, messages_sent, skipped_sellers)
```

No customer chat ids are ever in `plan` (roster is `telegram_user_id`s + `ROP_CEO_CHAT_ID`),
so `auto_reply_gate` is not involved.

### New env vars (`.env.example`)

```
ROP_ENABLED=0                 # master switch for AI ROP daily loops
ROP_CEO_CHAT_ID=              # Telegram chat/topic id for the CEO dashboard
```

---

## 10. Error handling

| failure | behaviour |
|---|---|
| any AmoCRM fetch in a run raises | log, **abort that slot's run** (no partial DMs), retry next slot |
| per-seller compute raises | skip that seller, still send the rest, add `"N sotuvchi o'tkazib yuborildi"` to the CEO message |
| bot `send_message` fails | retry once; then audit-log a drop, continue |
| `rop_targets` empty / no active rows | run no-ops; one CEO line: `"ROP: hech qanday sotuvchi sozlanmagan"` |
| `telegram_user_id` NULL on a row | skip that DM; list the seller in the CEO 09:00 message |
| Turso/DB unavailable | scheduler loop catches, logs, sleeps to next slot |
| `ROP_CEO_CHAT_ID` unset | seller DMs still go out; CEO message skipped with a WARN log |

---

## 11. Testing

`SKIP_LIVE=1 python -m pytest -q` must stay green; `bandit -r src/ -ll` clean.

| test module | covers |
|---|---|
| `tests/test_rop_scoring.py` | feature-table → score range + band; disclaimer text present |
| `tests/test_rop_traffic_light.py` | metrics/findings fixtures → expected level + reasons |
| `tests/test_rop_discipline.py` | lead/task fixtures → expected finding types (incl. `NO_OWNER`, `IMPORTANT_NO_NOTE`) |
| `tests/test_rop_weekly.py` | fake WON events → `won_count` / revenue / pct / `no_result_streak_days` |
| `tests/test_rop_daily.py` | fixture lead sets → `top_closings` ordering, `on_track` logic, **midday suppression**, `tomorrow_closings` |
| `tests/test_rop_messages.py` | snapshot each template against a fixture model — Uzbek Latin strings, valid HTML, no LLM |
| `tests/test_rop_fetchers.py` | mocked AmoCRM HTTP: request count bounded (≤5/run), parsing of leads/tasks/events |
| `tests/test_rop_scheduler.py` | slot-time gate, `ROP_ENABLED=0` no-op, Sunday skip, quiet-hours no-op, empty-roster CEO notice |
| `tests/test_rop_repository.py` | `init_table` idempotent, `rop_targets` / `rop_config` CRUD, missing-key defaulting |

---

## 12. Explicitly deferred (not in this spec)

- §9 500k team bonus tracking and progress bar.
- §10 leaderboard / best-closer / streak awards / non-material motivation.
- §11 coaching layer, call-transcript SPIN/objection scoring.
- §12 Sales HR (vacancy pipeline, interview scoring, onboarding, ramp-up).
- §13 full Telegram command/button interface and admin settings screen. (v1 edits
  `rop_targets` / `rop_config` via a one-off script or direct DB.)
- Any LLM-generated prose. All v1 messages are deterministic templates.
