# Smart Attendance audit — 2026-10-22

Scope: fetched `origin/main`, commit `d681b930b5fd314e1244e449e702877d6612e80b`
(PRs #935 and #936). Read-only application/security review; no app fixes, merge,
deployment, employee/location changes or live attack attempts.

Conclusion: corrections and confirmed attendance totals are not reliable enough
for unattended payroll use until the P1 findings below are fixed. A working page
and passing existing tests do not establish transaction or reporting correctness.

## Standards / safety boundary findings

### S1 — P1: confirmation can succeed without a persisted attendance event

Source: `src/services/core/attendance/service.py:184-210`,
`src/database_pool.py:99-119,146-168`, `src/services/core/attendance/kiosk.py:28-35`.

Session update, event insertion and audit are separate awaited operations on the
shared singleton connection. Other callers can commit/rollback the same
connection. A commit after state becomes confirmed, followed by event-write
failure, leaves a confirmed session without event. Retry returns
`already_confirmed=True` without repairing the missing event. Isolated fault
injection reproduced zero events with an ON_TIME/already_confirmed response.
This models a possible interleaving; it does not claim observed production loss.

Fix: connection-owned atomic unit for state + event + audit, with rollback and
safe idempotent recovery. Every caller using that connection must respect its
transaction ownership; locking only this function is insufficient.

### S2 — P2: QR redemption survives a failed verification transition

Source: `src/services/core/attendance/qr_tokens.py:105-115`,
`src/services/core/attendance/service.py:161-174`.

`redeem()` commits before verification/state advance. Injected transient failure
on session advance leaves the session in location_ok but redemption committed.
A fresh QR cannot recover it because session_id is unique in qr_redemptions;
retry returns qr_replayed. Employee must restart the entire session.

Fix: redemption, verification and transition in one transaction, with retries
returning the existing successful result for identical input.

## Spec / behavior findings

### F1 — P1: individual overnight shift cannot check out after midnight

Source: `src/services/core/attendance/service.py:98-107`.

Session creation resolves work_date using default 10:00–19:00 `self.shift`, not
the assigned employee shift. Reproduction: assign 22:00–06:00; confirm check-in
Oct 22 at 22:00; attempt checkout Oct 23 at 02:00. Result: check_in_required 409,
because service looks for Oct 23 check-in. Load assignment/open shift before
resolving work date and bind session/event to that assignment.

### F2 — P1: PENDING_REVIEW durations enter worked-hour totals

Source: `src/services/core/attendance/summary.py:61-79`.

The summary increments pending_review but still adds worked/overtime duration.
Synthetic mocked-location IN 10:00 and OUT 19:00 produce pending_review=1 and
worked_minutes=540. This is the module's documented HR/payroll source. Distinguish
observed pending duration from approved worked/payroll totals; approval must
explicitly control which totals downstream consumers may use. No actual wage
payment or payroll consumer was exercised or found in this review.

### F3 — P2: failed GPS is recorded as gps=true

Source: `src/services/core/attendance/service.py:192-201`.

Mock-location verification has passed=False and needs_review=True. Confirmation
correctly chooses PENDING_REVIEW but writes verification_summary.gps=True
unconditionally. Reproduction reads gps=true from the stored event. Preserve
actual verification outcomes and review reasons, rather than inventing success.

### F4 — P2: an ABSENT correction still counts the employee present

Source: `src/services/core/attendance/reports.py:10-24`,
`src/services/core/attendance/summary.py:61-79`,
`src/services/core/attendance/admin.py:42-51`.

HR changes check-in status to ABSENT; report presence is based solely on the
existence of kind=check_in. Synthetic corrected event remains present=1. The
summary also continues to count its paired duration. Apply one effective
correction model consistently across dashboard, summaries and payroll sources.

### F5 — P2: approved leave is ignored by live dashboard

Source: `src/services/core/attendance/reports.py:29-39`,
`src/services/core/attendance/summary.py:91-94`.

Day-level APPROVED_LEAVE corrections are read by period summary but not the
dashboard. With two synthetic employees and one approved leave, dashboard
reports absent=2 instead of excluding the approved absence. Load persisted
leave/day-off information into the same per-employee calendar for all views.

## Additional static observations (not included in reproduced count)

- `admin.py:42-51` validates correction event ID/employee but not supplied date;
  mismatched work_date can record a different day from the changed event.
- `linking.py:45-67` final approval does not claim pending state atomically;
  concurrent rejection can be overwritten. Needs transactional race coverage.
- Face explicitly returns 501; plan records a later owner choice of GPS+QR.
  This audit does not independently establish that owner's conversation and does
  not call the disabled face endpoint a completed biometric integration.
- Single-office configuration and static UI differ from the original broad
  nine-section/multi-branch proposal. Payroll summary exists; integration into
  existing salary payment flow, encrypted face provider and native-device E2E
  are not demonstrated.
- Earlier identity-collision concern was not proven exploitable here. An absent
  explicit CSRF token alone is also not treated as an established exploit.

## Verification evidence and limits

Exported only 34 relevant tracked files from the pinned commit into a temporary
directory. No environment, credential or Telegram session files were exported.
Existing synthetic SQLite fixtures enforce foreign keys and use no network.

Baseline: 69 passed, 4 deselected, 1.33s. The four exclusions depend on omitted
full auth/runtime sources (`api_employee_flow`, `kiosk_token_revocation`,
`login_redirect`, `qr_secret_derived`); they are not claimed as passing or product
failures. An initial partial-harness run had 69 passes and a secret-derivation
failure caused by missing settings source, then was narrowed explicitly.

Audit reproduction suite: 7 tests failed as expected against incorrect product
behavior, 0.72s. Five ordinary synthetic scenarios plus two deliberate database
failure/interleaving injections. These tests were never run on production.

Reproduction files and pinned snapshot at review time:
`C:/Users/baxti/AppData/Local/Temp/oisha-attendance-audit-1sfo1jq7/`.
`tests/test_audit_repros.py` contains all seven tests; fixture source is the
pinned `tests/test_attendance_flow.py`.
Durable source copy: `docs/audits/smart_attendance_repros_20261022.py`.
Copy it into the isolated snapshot's tests directory as test_audit_repros.py
before running. Do not run it against the dirty checkout or operational database.

Commands within that temporary directory:

```powershell
rtk proxy python -m pytest tests/test_attendance_schema.py tests/test_attendance_gps_qr.py tests/test_attendance_rules.py tests/test_attendance_reports.py tests/test_attendance_flow.py -q --tb=short -k "not api_employee_flow and not kiosk_token_revocation and not login_redirect and not qr_secret_derived"
rtk proxy python -m pytest tests/test_audit_repros.py -q --tb=line
```

Full repository pre-flight, real Turso concurrency, authenticated production
flow and actual Android/iOS camera/location tests were not run. Existing dirty
checkout was preserved. Repository additions for this audit are documentation
and synthetic reproduction source only. Obsidian capture attempted separately; its result must
not be assumed successful.

Counts: Standards/safety — 2 reproduced findings (worst P1, atomic confirmation).
Spec/behavior — 5 reproduced findings (worst P1, overnight and pending totals).
