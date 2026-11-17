# Community Contact Sync (PR-1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Daily two-way sync of "Tadbirkorlar" folder members across Google Contacts, Telegram contacts and AmoCRM via a canonical Turso store with per-system snapshots.

**Architecture:** Package `src/services/core/community_sync/`. Pure core (models, cohorts, merge) + `store` (DatabasePool) + adapters with `read_all()`/`apply()` + `runner` that plans, gates (quiet hours, dry-run, bulk approval) and applies. PR-2 (Airtable, Obsidian, GitHub) is out of scope.

**Tech Stack:** Python 3.11 asyncio, Telethon (Hetzner userbot via `app_ctx`), Google People API (`gcontacts.py`), AmoCRM v4 (`crm/amocrm/contacts.py`), Turso via `database_pool.DatabasePool`, pytest.

**Spec:** `docs/superpowers/specs/2026-11-17-community-contact-sync-design.md`

## Global Constraints

- Every production file ≤400 lines, every function ≤60 lines.
- DB access only through `src/database_pool.py` (`DatabasePool().execute(sql, params)`).
- Never start a Telegram client; take the existing one from `app_ctx`. Tests mock it.
- Uzbek strings in double quotes only; apostrophes `ʻ` (U+02BB) / `ʼ` (U+02BC).
- Config via `getattr(settings, NAME, default)`: `COMMUNITY_SYNC_ENABLED=False`, `COMMUNITY_SYNC_DRY_RUN=True`, `COMMUNITY_SYNC_FOLDER_ID=13`, `COMMUNITY_SYNC_TG_DAILY_LIMIT=120`, `COMMUNITY_SYNC_BULK_THRESHOLD=20`. Do not edit `settings.py`/`boot.py`.
- Name format `"Ism Familya <suffix>"`; suffix `"TN<n> Gr"` (TEZ NATIJA n), `"3K<n> Gr"` (3 kunlik intensiv n). Google label `"TEZ NATIJA <n>"` / `"3K<n>"`.
- Never delete anything in any system. Empty value never overwrites non-empty.
- Tests: all external APIs mocked; `SKIP_LIVE=1 python -m pytest -q` green; `bandit -r src/ -ll` clean.

## Review Focus

1. Contact already named `"Ali Valiyev TN4 Gr"` joins TN7 → name unchanged, label `TEZ NATIJA 7` added. (Task 2 test `test_existing_other_suffix_kept`)
2. Same person in 3 groups, phone only in one intro post → one Person, 3 cohorts, phone set. (Task 3 `test_merge_across_groups`)
3. Google edited name AND AmoCRM edited name differently → conflict row, no write to either. (Task 3 `test_conflict_two_systems`)
4. FloodWait 3600s mid-drip → remaining queue kept, `wait_until` stored, run continues other systems. (Task 6 `test_floodwait_defers`)
5. Run at 23:30 Tashkent → no writes, report says quiet hours. (Task 8 `test_quiet_hours_blocks`)

---

### Task 1: Intro parser extension

**Files:** Modify `src/services/core/contact_intro_parser.py`; Test `tests/test_contact_intro_parser_cyrillic.py`

**Interfaces:** Produces unchanged `parse_contact_intro(text, source_chat="") -> Optional[ContactIntro]` now accepting Cyrillic labels and `isim`.

- [ ] Step 1: tests:
```python
def test_cyrillic_labels():
    c = parse_contact_intro("Исм: Али\nФамилия: Валиев\nТелефон: +998 90 123 45 67\nКомпания: Nur")
    assert (c.first_name, c.last_name, c.phone, c.brand) == ("Али", "Валиев", "998901234567", "Nur")
def test_isim_variant():
    assert parse_contact_intro("Isim: Ali\nFamilya: Valiyev").first_name == "Ali"
```
- [ ] Step 2: run `python -m pytest tests/test_contact_intro_parser_cyrillic.py -v` → FAIL.
- [ ] Step 3: add aliases to `_FIELD_ALIASES`: first_name `isim, исм, исми, имя`; last_name `фамилия, фамилияси`; phone `телефон, тел, рақам`; brand `компания, бренд`; activity `фаолият, соҳа`; region `ҳудуд, шаҳар, город`. Lower-case compare already applied; verify `_normalize_label` lowercases Cyrillic.
- [ ] Step 4: run tests + existing parser tests → PASS.
- [ ] Step 5: commit `feat(community-sync): cyrillic intro labels`.

### Task 2: Models, cohorts, naming

**Files:** Create `src/services/core/community_sync/__init__.py`, `models.py`, `cohorts.py`; Test `tests/test_community_sync_models.py`

**Interfaces — Produces:**
- `SYNC_FIELDS = ("first_name","last_name","phone","username","company","activity","region")`
- `@dataclass Person: key: str; tg_id: int|None; username: str; first_name: str; last_name: str; phone: str; company: str; activity: str; region: str; cohorts: set[str]; ext: dict[str,str]` (`ext` = system → external id)
- `Cohort(code: str, suffix: str|None, label: str)`; `cohort_for_group(title: str) -> Cohort|None`
- `display_name(p: Person, existing: str = "") -> str`; `labels_for(p: Person) -> list[str]`

- [ ] Step 1: tests:
```python
def test_cohort_tn(): assert cohort_for_group("TEZ NATIJA 7") == Cohort("TN7","TN7 Gr","TEZ NATIJA 7")
def test_cohort_3k(): assert cohort_for_group("3 kunlik intensiv 7").suffix == "3K7 Gr"
def test_sector_group(): assert cohort_for_group("Toshkent 7").suffix is None
def test_display_name(): assert display_name(person(first="Ali", last="Valiyev", cohorts={"TN7"})) == "Ali Valiyev TN7 Gr"
def test_oldest_cohort_suffix(): assert display_name(person(cohorts={"TN7","TN4"})).endswith("TN4 Gr")
def test_existing_other_suffix_kept(): assert display_name(person(cohorts={"TN7"}), existing="Ali Valiyev TN4 Gr") == "Ali Valiyev TN4 Gr"
```
- [ ] Step 2: run → FAIL.
- [ ] Step 3: implement. `cohort_for_group`: regex `tez\s*natija\s*(\d+)` → TN; `(3\s*kunlik|intensiv|3k)\D*(\d+)` → 3K; else sector cohort with code = slug of title, suffix None, label = title. Existing suffix detection regex `\b(TN|3K)\d+ Gr$`. Oldest = lowest number, TN before 3K on tie.
- [ ] Step 4: run → PASS. Step 5: commit `feat(community-sync): person model and cohort naming`.

### Task 3: Identity resolution and 3-way merge

**Files:** Create `community_sync/merge.py`; Test `tests/test_community_sync_merge.py`

**Interfaces — Produces:**
- `resolve(people: list[Person], incoming: Person) -> Person|None` (match tg_id → phone → username)
- `@dataclass Change(system: str, key: str, field: str, value: str)`; `@dataclass Conflict(key: str, field: str, values: dict[str,str])`
- `merge_field(base: dict[str,str], current: dict[str,str]) -> tuple[str|None, Conflict-like dict|None]` — base/current keyed by system
- `plan(canonical: dict[str,Person], snapshots: dict[str,dict[str,dict[str,str]]], reads: dict[str,dict[str,dict[str,str]]]) -> tuple[list[Change], list[Conflict]]` (snapshots/reads: system → key → field → value)

- [ ] Step 1: tests:
```python
def test_merge_across_groups(): # 3 incomings same tg_id, phone in one -> 1 person, 3 cohorts, phone set
def test_one_system_changed(): assert merge_field({"g":"Ali","a":"Ali"}, {"g":"Aliy","a":"Ali"}) == ("Aliy", None)
def test_no_change(): assert merge_field({"g":"Ali"}, {"g":"Ali"}) == (None, None)
def test_same_change_two_systems(): assert merge_field({"g":"A","a":"A"},{"g":"B","a":"B"}) == ("B", None)
def test_conflict_two_systems(): v, c = merge_field({"g":"A","a":"A"},{"g":"B","a":"C"}); assert v is None and c == {"g":"B","a":"C"}
def test_empty_never_overwrites(): assert merge_field({"g":"A"}, {"g":""}) == (None, None)
def test_plan_propagates(): # google changed phone -> Change rows for amocrm and telegram, none for google
```
- [ ] Step 2: run → FAIL. Step 3: implement (pure functions, no I/O). Step 4: PASS. Step 5: commit `feat(community-sync): identity and three-way merge`.

### Task 4: Store

**Files:** Create `community_sync/store.py`; Test `tests/test_community_sync_store.py` (sqlite tmp via DatabasePool fallback or mocked `execute`)

**Interfaces — Produces** `class SyncStore` with async: `ensure_schema()`, `load_people() -> dict[str,Person]`, `upsert_person(p)`, `load_snapshots() -> dict[str,dict[str,dict[str,str]]]`, `save_snapshot(system, key, fields: dict)`, `enqueue_tg(key, username, phone)`, `due_tg(limit:int, now) -> list[dict]`, `mark_tg(key, status, wait_until=None)`, `add_conflict(Conflict)`, `open_conflicts() -> list[Conflict]`, `resolve_conflict(key, field, value)`.
Tables: `community_people(key PK, data JSON, updated_at)`, `community_snapshots(system,key,data JSON, PK(system,key))`, `community_tg_queue(key PK, username, phone, status, wait_until, added_at)`, `community_conflicts(key, field, values JSON, status, PK(key,field))`. Parameterised SQL only.

- [ ] Steps: test round-trip person, snapshot overwrite, `due_tg` respects `wait_until` and limit, conflict open→resolved → FAIL → implement → PASS → commit `feat(community-sync): turso store`.

### Task 5: Collector

**Files:** Create `community_sync/collector.py`; Test `tests/test_community_sync_collector.py`

**Interfaces:** Consumes `cohort_for_group`, `parse_contact_intro`, `Person`. Produces `async collect(client, folder_id: int, history_limit: int = 3000) -> list[Person]`.
Uses `functions.messages.GetDialogFiltersRequest()`, picks filter `id == folder_id`, iterates `include_peers`; per chat `client.iter_participants(chat)` (skip bots, deleted) and `client.iter_messages(chat, limit=history_limit)` → `parse_contact_intro`; intro attached to sender id. One Person per (tg_id) per group with that group's cohort.

- [ ] Steps: test with fake client (2 chats, 1 bot, 1 intro in Cyrillic) → 2 persons non-bot, intro fields on right sender, cohorts set; FAIL → implement → PASS → commit.

### Task 6: Adapters (Google, Telegram, AmoCRM)

**Files:** Create `community_sync/adapters/__init__.py`, `base.py`, `google.py`, `telegram.py`, `amocrm.py`; Modify `src/services/core/gcontacts.py` (add `update_contact(resource_name, first_name, last_name, phones) -> bool`, `add_to_group(resource_name, group_name, create_if_missing=True) -> bool`); Tests `tests/test_community_sync_adapters.py`

**Interfaces — Produces** `class Adapter(Protocol): name: str; async read_all(people: dict[str,Person]) -> dict[str,dict[str,str]]; async apply(changes: list[Change], people: dict[str,Person]) -> dict` (returns `{"ok":n,"failed":n,"deferred":n}`).
- Google: read via `list_all_contacts`, map by `ext["google"]` then phone; apply creates (name via `display_name`, labels via `labels_for`, `create_if_missing=True`) or updates. Name write uses `display_name(p, existing)`.
- Telegram: read contacts via `client.get_contacts()` (`functions.contacts.GetContactsRequest`); apply = enqueue into store; `drip(store, client, limit)` adds by username (`AddContactRequest` with resolved user) else phone `ImportContactsRequest`; `FloodWaitError` → `mark_tg(key,"deferred",now+e.seconds)` and stop drip.
- AmoCRM: read by `ext["amocrm"]`/`get_contact_by_phone`; apply `create_contact`/update name+phone, tag `community` + cohort codes. Sync client calls wrapped in `asyncio.to_thread`.

- [ ] Steps: tests per adapter with mocks: google create uses label `"TEZ NATIJA 7"`; google keeps `TN4 Gr` name; `test_floodwait_defers`; amocrm skips person without phone and name; FAIL → implement → PASS → commit `feat(community-sync): google telegram amocrm adapters`.

### Task 7: Approval

**Files:** Create `community_sync/approval.py`; Test inside `tests/test_community_sync_runner.py`

**Interfaces — Produces** `async request_bulk_approval(bot, owner_id, summary: dict[str,int]) -> str` (stores pending id in `agent_state` key `community_sync:pending`), `async is_approved(store_or_db, plan_id) -> bool`, `async send_conflict(bot, owner_id, Conflict)` with inline buttons `cs:pick:<key>:<field>:<system>`; callback handler `handle_callback(data, store)` resolving conflict. Message text Uzbek, double quotes.

- [ ] Steps: test callback parsing and resolve; FAIL → implement → PASS → commit.

### Task 8: Runner + schedule hook

**Files:** Create `community_sync/runner.py`, `scripts/community_sync_run.py` (manual CLI: `--dry-run/--apply`, runs only on Hetzner, refuses if `ALLOW_LOCAL_RUN` falsy and not `RUNNING_ON_SERVER`); Test `tests/test_community_sync_runner.py`; Modify `docs/agents/handoff-log.md`.

**Interfaces — Produces** `async run_once(ctx, *, dry_run: bool|None = None, now=None) -> dict` returning `{"status": "quiet_hours"|"dry_run"|"awaiting_approval"|"applied"|"disabled", "plan": {system: n}, "conflicts": n}`; `async scheduled_job(ctx)`.
Flow: enabled? → `is_quiet_hours(now)` → collect → resolve/upsert → reads → `plan` → conflicts stored+sent → dry_run? report → any system count > threshold and not approved → request approval → apply each adapter (errors isolated per adapter) → save snapshots → tg drip → owner report.
Scheduler wiring into `boot.py` is NOT done here; handoff-log notes the one-line registration for Coordinator (daily 10:00 Tashkent).

- [ ] Steps: tests `test_disabled`, `test_quiet_hours_blocks`, `test_dry_run_no_writes`, `test_bulk_needs_approval`, `test_adapter_failure_isolated`, `test_idempotent_second_run_no_changes`; FAIL → implement → PASS → commit.

### Task 9: Gates + PR

- [ ] `SKIP_LIVE=1 python -m pytest -q --tb=short` → all pass.
- [ ] `bandit -r src/ -ll` → no new issues.
- [ ] `python scripts/check_uzbek_text.py --staged` → ok.
- [ ] handoff-log entry; push branch `feat/community-contact-sync`; `gh pr create`.
