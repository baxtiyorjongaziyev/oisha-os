# Smart Attendance — repository audit and architecture proposal

Date: 2026-10-22. Status: PROPOSED; owner architecture approval pending.
Evidence: local source inspection only. No production database, deployment,
provider account, employee record, location or biometric data was accessed.
No attendance implementation, migration execution or deployment has occurred.

Scope correction (2026-10-22): the preceding statement describes work by Codex
in this checkout only. Subsequent branch inspection found Claude's attendance
implementation in `origin/claude/smart-attendance-module-uy87g8`, head `779c5292`,
open PR https://github.com/baxtiyorjongaziyev/oisha-os/pull/935. It includes GPS/QR,
employee/kiosk/admin static screens, schedules, reports, XLSX/PDF export and tests.
Face verification explicitly returns 501 (disabled); payroll export integration
is not present among the inspected attendance modules. Its plan states owner
chose GPS+QR without face; that owner decision was not independently verified in
this chat. This proposed design must be reconciled with that implementation
before writing competing code. No deployment success was verified. PR test job
was still in progress at inspection. PR title/body were stale (documentation-only)
despite implementation files being present.

## 1. Verified repository findings

| Concern | Inspected source | Finding |
|---|---|---|
| Backend | `src/services/api_server/core.py`, `src/api_server.py` | Python/FastAPI; core mounts modular routers; public facade re-exports APIs. |
| Frontend | `apps/web/package.json`, `src/components/Sidebar.tsx` under that app | Next.js 16 / React 19 / TypeScript; root workspace app, separate from `salescoach-ai`. |
| Design | `apps/web/src/app/globals.css` | Existing surface, text, border, accent and dark theme variables; reuse them and existing layout. |
| Authentication | `src/api/security.py`, `src/api/auth_service.py`, `src/services/api_server/oauth.py` | Signed `oisha_token` cookie, trusted proxy and service bearer mechanisms. |
| Authorization | `src/api/rbac.py` | owner/admin/seller/targetolog/viewer/service; dedicated attendance permissions do not yet exist. |
| Web identities | `src/api/web_auth_store.py` | Email/Google web users use a separate SQLite auth store; Telegram login also exists. |
| Employee master | `src/services/core/finance/erp_schema.py`, `src/services/core/hr_engine.py` | `employees` with integer ID, optional unique telegram_id, active flag, name, role, salary; no verified web-user mapping. |
| HR routes | `src/api/routes/erp_routes.py` | HR summary endpoint; no attendance flow found in inspected HR sources. |
| Payroll | `src/services/core/hr_engine.py`, `src/services/core/finance/erp_dashboard.py` | Base-salary sum and KPI reporting; period is currently unused by monthly salary sum. No attendance payroll posting contract found. |
| Storage | `src/database_pool.py`, `src/services/core/finance/erp_schema.py` | libsql/Turso pool and SQLite-compatible DDL, not PostgreSQL for this HR subsystem. |
| Transactions | `src/database_pool.py` | Shared connection; statement retries and separate commit. Not a safe attendance multi-statement transaction boundary as written. |
| Frontend proxy | `apps/web/src/app/api/oisha/dashboard-overview/route.ts`, `apps/web/src/lib/apiClient.ts` | Existing helpers can attach owner service secret. Reusing that pattern for employee attendance would lose caller identity. |

The checkout is on `feat/crm-parity` with extensive existing unrelated tracked
and untracked changes. Preserve all of them. Existing locks include auth store
and OAuth routes. Before implementation, use an isolated feature worktree and
coordinate any required auth edits; do not copy environment/session files.

Required handoff resume script ran read-only using process-scoped PowerShell
execution-policy bypass after the default policy rejected script execution.
The referenced `.agents/skills/skill-evolution/SKILL.md` is missing; scoped skill
inventory did not locate a replacement. Obsidian `brain_context` returned tool
unavailable; vault capture remains open, with this document as repository record.

## 2. Architecture alternatives

1. **Recommended: extend existing FastAPI HR + existing Next.js UI.** Add a
   modular attendance domain and additive Turso/SQLite migrations. Keep employee
   master and salary calculations intact. Add a transaction capability in the
   database pool, needed for correctness rather than introduce a second database.
2. Separate PostgreSQL attendance service: stronger independent scaling, but
   adds service operation, employee replication and consistency work. Defer until
   measured volume or organizational isolation requires it.
3. Native-only mobile attendance: stronger device attestation options but adds
   app distribution and mobile maintenance. Keep as an optional high-assurance
   client over the same API, alongside the browser implementation.

## 3. Identity and access boundaries

- All employee operations resolve employee ID server-side from a verified,
  active identity mapping. Never accept an arbitrary employee ID as self identity.
- Add `attendance_employee_identities` mapping employee to an explicitly
  namespaced authenticated subject. Telegram IDs and web-user IDs can overlap;
  naked JWT `sub` is insufficient. Introduce a verified identity-source claim
  through coordinated auth changes. Legacy ambiguous sessions must reauthenticate.
- Self-service: active mapped employees may operate/read their own records.
  Separate permissions: `attendance:admin`, `attendance:review`,
  `attendance:kiosk`, `attendance:payroll:read`. Grant owner/admin deliberately;
  do not reinterpret sales roles as HR authority. Branch grants restrict kiosk
  and delegated HR access. Service credentials cannot impersonate employees.
- Same-origin Next.js proxy forwards the actual session, never injects owner
  credentials. Validate Origin and CSRF token on cookie-authenticated mutations.
  Backend enforces every permission independently. No tokens in localStorage.
- Rate limits by authenticated subject, device/session and route, stored in
  shared storage for multiple workers. Bound request body sizes and pagination.

## 4. Domain and database

Add versioned, forward-only, repeatable migrations. Never drop current tables.
Employee IDs reference existing `employees`; add branch/department assignment
metadata without duplicating employee or salary master data.

| Entity | Responsibility / constraints |
|---|---|
| `attendance_branches` | Explicit branch ID, timezone, active state; no invented real locations. |
| `attendance_employee_identities` | Unique identity-source/subject mapping, employee FK, active state. |
| `attendance_policies` | Versioned policy: accuracy, age, grace, session/step TTLs, retention, evidence requirements. |
| `geofences` | Branch FK, circle coordinates/radius, version, active dates, checked coordinate ranges. |
| `attendance_shifts` | Shift definition, timezone, breaks, authorized overtime policy. |
| `shift_assignments` | Employee/branch, absolute UTC start/end, local work date, schedule version; prevent overlapping assignments. |
| `attendance_calendar` | Branch holidays, day off and approved leave provenance; override order explicitly defined. |
| `attendance_sessions` | Employee, assignment, action IN/OUT, device binding, expiry, policy version and state. |
| `attendance_events` | Immutable confirmed event, server UTC time, work date, session FK; unique employee/assignment/action. |
| `attendance_verifications` | Session FK, step, outcome, expiry, evidence reference, provider response metadata; no raw face/GPS by default. |
| `qr_challenges` | Branch/kiosk session, signed nonce, audience, issue/expiry, revocation state. |
| `attendance_qr_redemptions` | Unique challenge/employee/action; prevents personal replay while allowing multiple employees to scan one monitor. |
| `face_enrollments` | Employee, encrypted provider reference/template, key version, consent version, revocation state. |
| `attendance_consents` | Purpose, notice version, legal basis, grant/revocation timestamps, employee linkage. |
| `attendance_corrections` | Append-only request/approval, reason, old/new effective values, reviewer, revision, evidence. |
| `attendance_audit_logs` | Actor, action, target, outcome, server timestamp, request ID; redact secrets and biometric content. |
| `attendance_idempotency` | Unique actor/route/key, request hash, committed result reference and expiry. |
| `attendance_payroll_outbox` | Versioned approved summaries, unique employee/period/revision, delivery/ack state. |

Indexes cover employee/work date, branch/time, pending reviews, expiry and outbox
state. Use FK enforcement and CHECK constraints in addition to validation.
Add database triggers or equivalent guards preventing mutation/deletion of event
and audit history by application paths. Retention deletion is separately scoped.

**Transaction requirement:** add an isolated connection/transaction context in
`database_pool.py`, with `BEGIN IMMEDIATE` for SQLite-compatible writes, commit
and rollback, and no unsafe automatic retry of partially executed transactions.
Existing unrelated pool callers must not share that transaction connection.
Confirmation, duplicate guard, event, audit, idempotency result and outbox changes
commit atomically. Unique constraints arbitrate races across workers; Python locks
alone are insufficient. Lost response retries return the committed result.
Turso transaction behavior must be integration-tested against a dedicated test
database before deployment; never run these tests on operational records.

## 5. Employee verification flow

1. Create IN/OUT session for the server-resolved employee and valid assignment.
   Server supplies random session nonce, policy version and expiry. OUT requires
   an open matching IN; no fabricated start time for a missing check-in.
2. Request location once with explicit browser permission. Validate coordinate
   bounds, accuracy, capture age, future-clock tolerance and server receipt time.
   Conservative containment requires distance + accuracy <= configured radius.
   Stale, inaccurate, outside or suspicious input never passes automatically.
   Keep only outcome/distance band and short-lived minimized evidence by policy.
3. Branch kiosk requests a server-signed challenge rotating every 30 seconds.
   Claims bind branch, kiosk session, random nonce, audience, issue/expiry and key
   version. Validate signature with fixed allowed algorithm, TTL, active kiosk,
   employee branch, session and redemption uniqueness. Store token hash, not token.
   A monitor QR is shared: globally consuming it on first scan would block all
   other employees. Per-employee redemption is therefore deliberate. Screenshots
   can still be relayed inside TTL; browser flow cannot promise relay prevention.
4. Server starts a provider liveness/1:1 verification transaction bound to
   employee enrollment and attendance session. Accept only authenticated
   server-to-server evidence, bound nonce, success thresholds and fresh result;
   never accept browser-supplied `face_passed=true`. Verify signed callbacks,
   reject duplicate callbacks and expired/revoked enrollments. Provider outage
   returns unavailable; no production mock or success fallback.
5. Confirm rechecks employee active state, assignment, consent, policy,
   unexpired successful steps and revocation inside the transaction. Persist
   server timestamp, action, assignment/branch and evidence references once.

Alternative verification: explicit request -> PENDING_REVIEW -> separately
authorized HR reviewer with step-up authentication and reason/evidence. No
self-approval; a second reviewer for sensitive corrections by policy. Alternative
identity checks do not silently bypass location or QR requirements; exceptional
missing evidence is recorded as an approved manual correction, not a verified scan.

No internet: show unconfirmed state. Retry with the same idempotency key only
while evidence remains valid; otherwise start a fresh session. Never confirm an
offline local timestamp automatically. Stop camera tracks on completion/cancel.

## 6. Rules, reports and payroll

- Persist UTC instants; calculate shift work date in branch IANA timezone.
  Overnight assignments span two dates but one shift. Assignment overrides
  calendar day off/holiday only when explicitly approved; leave provenance is kept.
- Separate workflow state from attendance classification: ON_TIME, LATE,
  EARLY_LEAVE, ABSENT, APPROVED_LEAVE, DAY_OFF, PENDING_REVIEW. Late and early leave
  can coexist as metrics even if the UI shows one primary status.
- Grace period affects classification; preserve actual late minutes separately.
  ABSENT only after scheduled shift end plus the policy reconciliation window,
  after leave/day-off resolution; missing schedule is unknown, not absent.
- Worked duration requires a valid confirmed IN/OUT pair. Subtract only recorded
  or policy-approved breaks. Missing OUT remains incomplete. Overtime is split
  into observed versus approved payable overtime; no automatic wage penalties.
- Dashboard metrics use scheduled eligible employees as attendance-rate
  denominator, expose period/timezone/generated_at/source status, and use null
  for undefined averages/rates. Filters: branch, department, employee, date, shift.
- Initially poll visible dashboard every 15 seconds with cancellation/backoff;
  label refresh timestamp. Do not claim streaming real-time delivery.
- XLSX/PDF exports run server-side with the same RBAC/filters; escape spreadsheet
  formulas, paginate source reads and record export audit. Fonts support Uzbek.
- Expose a read-only monthly summary contract through HREngine and a durable,
  versioned outbox for a future payroll consumer. Current salary sum remains
  unchanged. Delivery is not marked successful without consumer acknowledgment.

## 7. API and UI scope

Backend prefix `/api/attendance`, matching current `/api/...` conventions;
document this mapping from the requested `/attendance` conceptual routes.
Employee routes: POST sessions; POST sessions/{id}/location, /qr, /face, /confirm;
GET today/history. Add consent, enrollment and alternative-review request routes.
Admin routes: dashboard/reports, corrections, branches/geofences, policies,
shifts/assignments, consent/enrollment administration and payroll summaries.
Dedicated scoped kiosk endpoints issue QR challenges. Provider callbacks have
signature verification, no employee-cookie dependency, and strict replay guards.

UI: `HR Management -> Smart Attendance` in the existing Sidebar. Nine sections:
Dashboard, Live Attendance, Employees Attendance, QR Code Management, Locations
& Geofencing, Face Verification, Shift Management, Attendance Reports, Settings
& Security. Employee mobile flow includes today, guided verification, result,
check-out and history. Reuse theme/layout and accessible keyboard/focus patterns.
Every page needs real empty, loading, unavailable and permission-denied states.

QR encoding/scanning uses maintained dependencies after current official
documentation/security review. Native browser BarcodeDetector alone is not an
iOS compatibility strategy. Provide a camera scanner fallback; manual token
entry, if allowed, must not weaken server verification. No external QR web service.

## 8. Provider, privacy and legal release gates

- `FaceVerificationProvider` interface: start enrollment, verify enrollment,
  start liveness, fetch authenticated result, revoke/delete enrollment.
  Tests use an explicitly synthetic injected fake. Default production adapter
  is unavailable until endpoint, credentials, trust and supported protocol exist.
- Prefer verified in-country deployment/provider after legal assessment.
  Do not choose a foreign biometric provider or assume current Turso region is
  lawful. Actual data regions and account configuration remain unverified.
- Biometric references/templates use envelope encryption, separate keys, key
  rotation and least-privilege access; TLS required. No raw face images/videos
  in ordinary DB/logs. Retention/deletion includes provider and backup handling.
  Audit history avoids retaining deleted biometric payloads.
- GPS only during verification. Explain purpose/retention, permit review and
  correction, record biometric consent/revocation and a usable alternative flow.
- Browser GPS, camera and WebAuthn do not establish uncompromised device or
  physical presence. For higher assurance propose Android Play Integrity and
  iOS App Attest through a native client with server verification; attestation
  itself still does not prove GPS truth.
- Separate legal task before production biometric activation: assess current
  Uzbekistan personal-data rules, biometric consent, localization, database
  registration, cross-border transfer, employee notices and retention with a
  qualified reviewer. This design is not a compliance certification.
- Primary legal source found on 2026-10-22:
  https://lex.uz/uz/docs/-4396419 (O'RQ-547, personal data). Search surfaced 2026
  amendments; read the current consolidated text during legal acceptance,
  rather than rely on old localization summaries. Wage rules review is also
  separate; no attendance-triggered deductions in the proposed implementation.

## 9. Ordered implementation and acceptance plan

1. **Approved design and isolated branch:** clean feature worktree from explicitly
   selected base; preserve dirty checkout; resolve auth lock ownership and add lock.
2. **Migration and storage:** new domain schema, transactional pool capability,
   upgrade/re-run tests, FK/index/check tests, failure rollback and race tests.
3. **Identity/RBAC/API:** namespaced employee mappings, active-state checks,
   self/admin/kiosk/provider boundaries, CSRF, rate limits, typed inputs,
   idempotency and redacted audit. Test cross-employee/branch access denial.
4. **GPS/QR:** geofence policy, conservative accuracy, timestamps, kiosk challenge
   rotation, key rotation, per-employee redemption and step TTL revalidation.
5. **Face and alternative:** fail-closed adapter, consent, encrypted enrollment,
   signed callback binding and supervised alternative; provider contract tests.
6. **Rules and payroll:** overnight/calendar/leave handling, reconciliation,
   correction revisions, complete-pair duration and summary/outbox contract.
7. **Employee UI:** mobile guided flow, QR scanner, location permission, camera
   teardown, retry/expiry and attendance history, accessible responsive design.
8. **HR UI:** all nine sections, scoped filters, dashboard metrics, kiosk display,
   management forms, manual review, XLSX/PDF export and audit visibility.
9. **Verification:** unit + integration + browser E2E; outside GPS, poor accuracy,
   stale/future GPS, expired/replayed/wrong-branch QR, failed/spoofed face results,
   internet interruption, duplicate and concurrent confirmation, overnight shift,
   two branches, HR correction, revoked consent and alternative flow. Include
   foreign-subject collision, service impersonation and payroll double delivery.
   Test mobile Chrome and real iOS Safari/Android device camera paths separately;
   browser emulation alone is insufficient evidence for biometric/camera support.
10. **Security and release:** full repo pre-flight before PR (`SKIP_LIVE=1`
    pytest and `bandit -r src/ -ll`), dependency review, migration backup/restore
    drill, monitoring, retention job and operational runbooks. Add a separate
    example configuration file with empty placeholders, never read live `.env`.
    Supply administrator/employee guides, provider configuration and rollout/
    rollback instructions. Start disabled; stage with synthetic records, then an
    approved limited pilot after legal/provider/hosting acceptance.

## 10. Approval decision

Approve option 1: existing FastAPI + Turso/SQLite + Next.js, additive schema,
namespaced employee identity, isolated DB transactions, provider-neutral
fail-closed face integration, and payroll summaries without automatic deductions.
Provider choice, actual branch coordinates, shift schedules and legal acceptance
are configuration/release dependencies; they need not block safe local code/tests.
Architecture approval does not authorize live biometric enrollment or deployment.
