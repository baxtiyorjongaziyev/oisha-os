# Oisha Security Roadmap Design

Date: 2026-07-26
Status: Approved for planning

## Purpose

Close Oisha's remaining security and reliability gaps through independently reviewable PRs. Each security boundary must be testable, deployable, and reversible without coupling unrelated high-risk changes.

## Scope

1. Complete `owner/admin/seller/viewer` RBAC.
2. Diagnose and resolve GitHub Actions runner/account failures.
3. Connect finance endpoints to the existing Hisobchi Google Sheets integration.
4. Harden Docker and dependency management.
5. Run authenticated staging permission tests and a controlled staging pentest.

Jon Branding CSP and spam monitoring are specified separately in the Jon Branding repository.

## Non-goals

- No destructive production security testing.
- No demo or fabricated finance values.
- No pull-request code on the production Oracle runner.
- No all-powerful shared browser/service token.
- No unrelated refactoring.

## Delivery sequence

1. `security/rbac-permission-matrix`
2. `feature/real-finance-source`
3. `ci/runner-diagnostics`
4. `security/docker-dependency-hardening`
5. `security/staging-auth-pentest`

Each item is a separate PR and must satisfy its own acceptance criteria.

---

## 1. RBAC architecture

### Principal model

Every authenticated request resolves to:

```text
Principal
- subject: stable user or service identifier
- role: owner | admin | seller | viewer | service
- auth_type: session | bearer | trusted_proxy
- permissions: computed permission set
- scopes: optional object-level constraints
```

The central middleware remains the fail-closed outer boundary. Endpoint-level authorization is enforced with explicit permission dependencies.

### Roles

- `owner`: full business and platform control.
- `admin`: operational administration, excluding owner-only secrets, deploy controls, and ownership transfer.
- `seller`: assigned leads, own calls, own tasks, and allowed sales actions only.
- `viewer`: privacy-reduced read-only views only.
- `service`: machine identity with explicit scopes; never automatically equivalent to owner.

### Permission matrix

| Capability | Owner | Admin | Seller | Viewer | Service |
|---|---:|---:|---:|---:|---:|
| General dashboard | Full | Full | Own metrics | Allowed read-only metrics | Scoped |
| Leads and customers | Full | Full | Assigned records | Restricted read | Scoped |
| Calls | Full | Full | Own calls | Redacted summary | Scoped |
| Full transcripts | Full | Full | Own calls only | No | Scoped |
| Finance dashboard | Full | Full | No | No by default | Scoped read |
| Finance writes | Full | Full | No | No | Scoped write |
| Telegram chat read | Full | Restricted | No | No | Explicit read scope |
| Telegram send | Interactive owner confirmation | Requires owner approval | No | No | Explicit write scope plus owner approval |
| MCP read tools | Full | Restricted | No | No | Explicit read scope |
| MCP write tools | Interactive owner confirmation | Requires owner approval | No | No | Explicit write scope plus owner approval |
| User role management | Full | Seller/viewer only | No | No | No |
| Secrets and integrations | Full | No | No | No | No |
| Deploy and system settings | Full | No | No | No | No |
| Audit logs | Full | Full | Own events | No | No |

A viewer may receive `finance:read` only through an explicit owner-issued grant recorded in the audit log. The base viewer role itself never includes finance access.

For owner-initiated Telegram/MCP writes, the owner's explicit interactive confirmation is the approval. Admin and service writes require a separate owner approval record.

### Endpoint authorization

Protected endpoints declare permissions explicitly:

```python
Depends(require_permissions("lead:read"))
Depends(require_permissions("finance:read"))
Depends(require_permissions("telegram:send"))
```

Prefix protection remains a safety net, not the final authorization decision.

### Object-level authorization

Seller access validates assignment or ownership at query time. Seller A must not access Seller B's lead, call, transcript, task, or customer by changing an ID.

- Seller queries include ownership/assignment predicates.
- Cross-seller access returns `403` without confirming object existence.
- Viewer responses omit contact details, transcripts, secrets, and internal notes unless a specific permission allows them.

### Trusted proxy handling

A loopback proxy identity is accepted only when it maps to a known Oisha user and role. A forwarded username is never automatically promoted to `admin`.

### Audit events

Record authentication failures, authorization denials, role/grant changes, finance access, Telegram/MCP writes, owner approvals, secret/integration changes, and deploy/system operations. Tokens and sensitive values are excluded.

### RBAC acceptance criteria

- Anonymous, malformed, invalid, and expired credentials fail closed.
- Seller/viewer sessions work only on permitted endpoints.
- Seller A cannot access Seller B objects.
- Viewer data is redacted.
- Base viewer role cannot read finance data.
- Service tokens are scope-limited.
- Proxy spoofing from non-loopback clients fails.
- Every protected route family has permission tests.

---

## 2. Real finance source

### Source choice

Use the existing Hisobchi Google Sheets integration through an interface:

```text
Finance API
  -> FinanceSource
      -> GoogleSheetsFinanceSource
          -> Hisobchi Google Sheet
```

### Domain objects

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
- stable_source_id
- direction: income | expense
- amount
- currency
- description
- occurred_at
- category
```

All monetary calculations use `Decimal`.

### Configuration

Configuration provides spreadsheet ID, worksheet names, required columns, timezone, currency, freshness threshold, and a secret-store reference for the service account. Credentials are never committed.

### Error behavior

- Missing config: `503 finance_source_not_configured`.
- Unavailable source: `503 finance_source_unavailable`.
- Invalid schema/data: `502 finance_source_invalid`.
- Stale source: return `freshness: stale`, emit monitoring, and never label it current.
- No demo values under any production path.

### Authorization

- Reads: `finance:read`.
- Writes/import/reconciliation: `finance:write`.
- Default: owner/admin only.
- Explicit viewer grants are owner-issued and audited.
- Every finance access is audited.

### Finance acceptance criteria

- Staging values come from a controlled test sheet.
- Totals reconcile with fixtures.
- Invalid rows do not silently corrupt totals.
- Missing source returns explicit 503.
- Seller/base-viewer access returns 403.
- No sample transaction remains.

---

## 3. GitHub Actions and runner diagnostics

### Security boundary

- PRs run only on GitHub-hosted or disposable isolated runners.
- Oracle is limited to trusted `main` deploy and explicitly trusted main checks.
- PR dependencies are never installed on production.

### Diagnostic workflow

Add a checkout-free GitHub-hosted `echo` job and a trusted manual/main-only Oracle diagnostic. Record runner metadata, labels, disk, service state, workspace permissions, and a small artifact/job summary.

The result must distinguish:

- Actions spending/minutes restriction;
- account payment restriction;
- repository Actions policy;
- GitHub-hosted assignment failure;
- self-hosted offline/busy/label mismatch;
- workflow syntax/permission failure.

### Oracle requirements

Dedicated production label, minimal-privilege user, no broad passwordless sudo, deploy concurrency lock, clean workspace, deploy-only secrets, and monitored runner service health.

### CI acceptance criteria

- Minimal GitHub-hosted job reaches step 1 and completes.
- PR Python and TypeScript jobs complete on isolated runners.
- No PR job targets `[self-hosted, oracle]`.
- Oracle reports online and accepts trusted jobs only.
- Infrastructure failures are separated from test failures.

---

## 4. Docker hardening

- Add non-root `oisha` user and `COPY --chown`.
- Run as non-root with minimal writable paths.
- Set `no-new-privileges` where supported.
- Add accurate healthcheck.
- Pin production image versions/digests.
- Bind development Postgres, Redis, and MinIO ports to loopback only.
- Do not expose production infrastructure services publicly through compose mappings.
- Remove production default credentials.
- Require secret-store/environment values and fail startup when missing.
- Separate development defaults from production config.

### Docker acceptance criteria

- Runtime UID is non-root.
- Postgres/Redis/MinIO are not publicly reachable by default.
- No production `latest` tag remains.
- Secret scan finds no production credential.
- Healthcheck represents readiness accurately.

---

## 5. Dependency hardening

### Python decision

Use `pip-tools` and `pip-compile` because the repository already uses `requirements*.txt`. Direct dependencies remain human-maintained; generated lock files pin transitive versions. Production installation uses the compiled lock, with hashes where compatible.

Run `pip-audit` against the compiled environment.

### TypeScript

Use one authoritative `pnpm-lock.yaml`, `pnpm install --frozen-lockfile`, `pnpm audit`, reviewed overrides, and no untrusted lifecycle scripts during remediation.

### GitHub Actions

Pin third-party actions to immutable commit SHAs in production/security workflows. Keep security updates separate from routine updates and attach before/after audit evidence.

### Dependency acceptance criteria

- Clean installs resolve identical versions.
- No unresolved fixable critical/high Python or pnpm alert.
- Exceptions include reason, affected path, and review date.
- Lock changes pass typecheck, tests, and build.

---

## 6. Staging permission tests and pentest

Use a dedicated staging deployment with synthetic data only. Production Telegram sessions, finance data, CRM records, customer details, and production secrets are prohibited.

### Test identities

Anonymous, invalid token, expired token, viewer, seller A, seller B, admin, owner, scoped service token, and spoofed proxy identity.

### Test scope

- auth bypass and JWT validation;
- role escalation;
- proxy spoofing;
- permission gaps;
- IDOR/BOLA;
- WebSocket auth;
- MCP read/write separation;
- Telegram approval enforcement;
- finance authorization;
- CORS and response leakage;
- rate limiting;
- dependency/container baseline scans;
- authenticated ZAP baseline/API scan where compatible.

No destructive payloads, denial-of-service tests, or production targets.

### Pentest acceptance criteria

- No anonymous/lower-role protected-data access.
- No cross-seller access.
- No viewer writes.
- No unapproved Telegram/MCP write.
- No unresolved high/critical staging finding.
- Automated results match the documented matrix.

---

## Rollout and rollback

Deploy each PR to staging, run focused regression/permission tests, then promote. RBAC, finance, runner, and Docker changes remain independently reversible. Finance stays fail-closed on source failure. Previous container image remains available for rollback. Runner diagnostics never expose production secrets to PRs.

## Completion definition

Complete only when all five PRs are merged, staging permission tests pass, the controlled pentest has no unresolved high/critical finding, and production behavior matches the documented role matrix.