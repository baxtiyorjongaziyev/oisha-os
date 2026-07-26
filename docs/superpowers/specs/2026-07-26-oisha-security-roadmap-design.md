# Oisha Security Roadmap Design

Date: 2026-07-26
Status: Approved for planning

## Purpose

Close the remaining security and reliability gaps in Oisha without combining unrelated high-risk changes into one release. The work is split into independently reviewable branches and pull requests so each security boundary can be tested, deployed, and rolled back separately.

## Scope

This design covers:

1. Complete `owner/admin/seller/viewer` RBAC.
2. GitHub Actions runner and account diagnostics.
3. A real finance data source backed by the existing Hisobchi Google Sheets integration.
4. Docker and dependency hardening.
5. Authenticated staging permission tests and a controlled staging pentest.

Jon Branding CSP and spam monitoring are specified separately in the Jon Branding repository.

## Non-goals

- No production destructive security testing.
- No demo or fabricated finance values.
- No execution of pull-request code on the production Oracle runner.
- No shared all-powerful token for browser users and service integrations.
- No broad unrelated refactoring.

## Delivery sequence

1. `security/rbac-permission-matrix`
2. `feature/real-finance-source`
3. `ci/runner-diagnostics`
4. `security/docker-dependency-hardening`
5. `security/staging-auth-pentest`

Each item is a separate PR and must pass its own acceptance criteria before the next security boundary is considered complete.

---

## 1. RBAC architecture

### Principal model

Every authenticated request resolves to a normalized principal:

```text
Principal
- subject: stable user or service identifier
- role: owner | admin | seller | viewer | service
- auth_type: session | bearer | trusted_proxy
- permissions: computed permission set
- scopes: optional object-level constraints
```

The existing central middleware remains the fail-closed outer boundary. Endpoint-level authorization is added through explicit permission dependencies.

### Roles

- `owner`: full business and platform control.
- `admin`: operational administration, excluding owner-only secrets, deploy controls, and ownership transfer.
- `seller`: access only to assigned leads, own calls, own tasks, and permitted sales actions.
- `viewer`: read-only access to explicitly allowed, privacy-reduced views.
- `service`: machine identity with explicit scopes; it is not automatically equivalent to owner.

### Permission matrix

| Capability | Owner | Admin | Seller | Viewer | Service |
|---|---:|---:|---:|---:|---:|
| General dashboard | Full | Full | Own metrics | Read-only allowed metrics | Scoped |
| Leads and customers | Full | Full | Assigned records | Restricted read | Scoped |
| Calls | Full | Full | Own calls | Redacted summary only | Scoped |
| Full transcripts | Full | Full | Own calls only | No | Scoped |
| Finance dashboard | Full | Full | No | Optional explicit permission | Scoped read |
| Finance writes | Full | Full | No | No | Scoped write |
| Telegram chat read | Full | Restricted | No | No | Explicit read scope |
| Telegram send | Owner approval policy | Owner approval policy | No | No | Explicit write scope plus approval policy |
| MCP read tools | Full | Restricted | No | No | Explicit read scope |
| MCP write tools | Full | Owner-approved | No | No | Explicit write scope plus approval policy |
| User role management | Full | Seller/viewer only | No | No | No |
| Secrets and integrations | Full | No | No | No | No |
| Deploy and system settings | Full | No | No | No | No |
| Audit logs | Full | Full | Own events | No | No |

### Endpoint authorization

Protected endpoints declare permissions explicitly:

```python
Depends(require_permissions("lead:read"))
Depends(require_permissions("finance:read"))
Depends(require_permissions("telegram:send"))
```

Prefix protection remains a safety net, but a protected prefix alone is not sufficient authorization.

### Object-level authorization

Seller access must validate assignment or ownership at query time. A seller cannot access another seller's lead, call, transcript, task, or customer merely by changing an object ID.

Rules:

- Seller queries include an ownership/assignment predicate.
- Cross-seller access returns `403` without confirming whether the object exists.
- Viewer responses omit private contact details, transcripts, secrets, and internal notes unless a specific permission allows them.

### Trusted proxy handling

A loopback proxy identity is accepted only when it maps to a known Oisha user and role. A forwarded username is not automatically promoted to `admin`.

### Audit events

Record at minimum:

- authentication success/failure;
- authorization denial;
- role changes;
- finance reads and writes;
- Telegram and MCP write attempts;
- secret/integration changes;
- owner approvals;
- deploy/system operations.

Sensitive values and tokens must never be included in audit payloads.

### RBAC acceptance criteria

- Anonymous access fails closed.
- Invalid, expired, or malformed tokens fail closed.
- `seller` and `viewer` sessions are accepted only for permitted endpoints.
- Seller A cannot access Seller B objects.
- Viewer endpoints return redacted data.
- Service tokens are scope-limited and cannot use browser-only owner actions.
- Proxy header spoofing from non-loopback clients is rejected.
- Permission tests cover every protected route family.

---

## 2. Real finance source

### Source choice

Use the existing Hisobchi Google Sheets integration as the first production finance source. The API must depend on a source interface rather than directly embedding Google Sheets logic.

```text
Finance API
  -> FinanceSource interface
      -> GoogleSheetsFinanceSource
          -> Hisobchi Google Sheet
```

### Source interface

The source returns normalized domain objects:

```text
FinanceSnapshot
- balance
- monthly_income
- monthly_expense
- currency
- calculated_at
- source_updated_at
- freshness: fresh | stale

FinanceTransaction
- stable source id
- direction: income | expense
- amount
- currency
- description
- occurred_at
- category
```

All monetary calculations use `Decimal`; floating-point arithmetic is prohibited.

### Configuration

Configuration identifies:

- spreadsheet ID;
- worksheet names;
- required column names;
- timezone;
- default currency;
- freshness threshold;
- service account credential reference.

Credentials remain in the deployment secret store and are never committed.

### Error behavior

- Missing configuration: `503 finance_source_not_configured`.
- Source unavailable: `503 finance_source_unavailable`.
- Invalid sheet schema/data: `502 finance_source_invalid`.
- Stale data: return data with `freshness: stale` and emit monitoring; do not label it current.
- No demo values under any production code path.

### Finance authorization

- Dashboard and transaction reads: `finance:read`.
- Writes/imports/reconciliation: `finance:write`.
- Default access: owner/admin only.
- Every finance access is audited.

### Finance acceptance criteria

- API values are derived from a controlled test sheet in staging.
- Balances and monthly totals reconcile with fixture data.
- Invalid rows do not silently corrupt totals.
- Missing source returns explicit 503.
- Seller and unauthorized viewer roles receive 403.
- No sample transaction remains in production responses.

---

## 3. GitHub Actions and runner diagnostics

### Security boundary

- Pull requests run only on GitHub-hosted or disposable isolated runners.
- The production Oracle runner is used only for trusted `main` deployment and explicitly trusted main-branch checks.
- Pull-request dependencies are never installed on the production host.

### Diagnostic workflow

Add a minimal workflow with no repository build steps:

1. GitHub-hosted job: checkout-free `echo`, environment summary, and runner metadata.
2. Oracle job: trusted manual/main-only diagnostic with runner labels, disk, service state, and workspace permissions.
3. Upload a small diagnostic artifact and job summary.

This separates account/runner assignment failure from application test failure.

### Oracle runner requirements

- Dedicated production label.
- Runs as a minimal-privilege user.
- No passwordless broad sudo.
- Concurrency lock for deployments.
- Clean workspace before and after trusted jobs.
- Secrets exposed only to deploy jobs.
- Runner service health documented and monitored.

### Account checks

The diagnostic result must identify whether the blocker is:

- GitHub Actions spending/minutes restriction;
- account payment restriction;
- repository Actions policy;
- GitHub-hosted runner assignment failure;
- self-hosted runner offline/busy/label mismatch;
- workflow syntax or permission error.

### CI acceptance criteria

- A minimal GitHub-hosted job reaches step 1 and completes.
- A pull-request Python job and TypeScript job complete on isolated runners.
- No pull-request job targets `[self-hosted, oracle]`.
- The Oracle runner reports online and only accepts trusted jobs.
- Infrastructure failures are reported separately from test failures.

---

## 4. Docker hardening

### Container runtime

- Create a non-root `oisha` user.
- Use `COPY --chown`.
- Run the application as the non-root user.
- Set `no-new-privileges` where supported.
- Keep writable paths explicit and minimal.
- Add a healthcheck.
- Use pinned image versions or digests in production.

### Compose networking

Development service ports bind to loopback only unless external exposure is explicitly required:

```yaml
127.0.0.1:5432:5432
127.0.0.1:6379:6379
127.0.0.1:9000:9000
```

Production infrastructure services are not exposed publicly through compose port mappings.

### Secrets

- Remove default credentials from production compose files.
- Require environment or secret-store values.
- Production startup fails if required secrets are absent.
- Separate development defaults from production configuration.

### Docker acceptance criteria

- Runtime UID is non-root.
- Database, Redis, and MinIO are not reachable from public interfaces by default.
- No `latest` tags remain in production definitions.
- Secret scanning finds no committed production credential.
- Healthcheck reports service readiness accurately.

---

## 5. Dependency hardening

### Python

- Produce a reproducible lock using `uv lock` or `pip-compile`.
- Separate direct requirements from generated locked versions.
- Use hashes for production installation where practical.
- Run `pip-audit` against the locked environment.

### TypeScript

- Keep one authoritative `pnpm-lock.yaml`.
- Install with `pnpm install --frozen-lockfile`.
- Run `pnpm audit` and review security overrides explicitly.
- Do not run untrusted lifecycle scripts during remediation workflows.

### GitHub Actions

- Pin third-party actions to immutable commit SHAs in production/security workflows.
- Keep Dependabot security updates separate from routine version updates.
- Security remediation must include before/after audit evidence.

### Dependency acceptance criteria

- Repeated clean installs resolve identical versions.
- Python and pnpm audits contain no unresolved fixable critical/high alerts.
- Any accepted exception has a documented reason, affected path, and review date.
- Lockfile changes pass typecheck, tests, and build.

---

## 6. Staging permission tests and pentest

### Environment

Use a dedicated staging deployment with synthetic data only. Production Telegram sessions, finance data, CRM records, customer contact details, and production secrets are prohibited.

### Test identities

- anonymous;
- invalid token;
- expired token;
- viewer;
- seller A;
- seller B;
- admin;
- owner;
- scoped service token;
- spoofed proxy identity.

### Automated permission suite

For every protected endpoint, assert the expected status and response shape for each identity. Include object-level IDOR tests proving Seller A cannot access Seller B resources.

### Security test scope

- authentication bypass;
- JWT validation and role escalation;
- proxy header spoofing;
- endpoint permission gaps;
- IDOR/BOLA;
- WebSocket authentication;
- MCP read/write separation;
- Telegram send approval enforcement;
- finance authorization;
- CORS and sensitive response leakage;
- rate limiting;
- dependency and container baseline scans;
- authenticated ZAP baseline/API scan where compatible.

### Safety controls

- No destructive payloads.
- Rate limits respected.
- No denial-of-service testing.
- Findings recorded with endpoint, identity, evidence, impact, and remediation.

### Pentest acceptance criteria

- No anonymous or lower-role access to protected data.
- No cross-seller object access.
- No viewer write capability.
- No unapproved Telegram/MCP write action.
- No high or critical unresolved staging finding.
- Final permission matrix matches automated test results.

---

## Rollout and rollback

- Deploy each PR to staging first.
- Run focused regression and permission tests.
- Promote to production only after staging acceptance criteria pass.
- RBAC can be rolled back independently of finance and infrastructure changes.
- Finance remains fail-closed if the source is unavailable.
- Docker changes retain the previous image/tag for rollback.
- Runner diagnostic changes never expose production secrets to pull requests.

## Completion definition

The roadmap is complete only when all five PRs are merged, staging permission tests pass, the controlled pentest has no unresolved high/critical finding, and the documented role matrix matches production behavior.