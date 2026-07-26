# Oisha RBAC Permission Matrix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce fail-closed `owner/admin/seller/viewer/service` authorization with endpoint permissions, seller object isolation, mapped proxy identities, and auditable sensitive actions.

**Architecture:** Keep `ApiAccessMiddleware` as the authentication perimeter. Normalize all credentials into a typed `Principal`, evaluate permissions in `src/api/rbac.py`, apply explicit permission dependencies to route families, and enforce ownership predicates inside repositories for seller-scoped objects.

**Tech Stack:** Python 3.11, FastAPI, Starlette, PyJWT, pytest, TypeScript/Next.js web client.

## Global Constraints

- Browser roles are exactly `owner`, `admin`, `seller`, and `viewer`.
- Machine identity uses role `service` with explicit scopes and is never automatically owner.
- Unknown, malformed, expired, or weak-secret credentials fail closed.
- A forwarded proxy user is accepted only from loopback and only after explicit role mapping.
- Seller access is limited at query time to assigned/owned records.
- Cross-seller denial returns `403` without confirming object existence.
- Viewer output is read-only and privacy-reduced.
- Telegram/MCP write actions require explicit permission and owner approval policy.
- Audit payloads never contain tokens, secrets, finance values, transcripts, message bodies, phone numbers, or emails.

---

## File Structure

- Create `src/api/rbac.py`: role, permission, principal, policy, FastAPI dependencies.
- Create `src/api/security_audit.py`: sanitized security audit events.
- Create `src/api/write_approval.py`: one-time approval tickets for privileged writes.
- Modify `src/api/security.py`: resolve browser, service, and proxy principals.
- Modify `src/api/auth_service.py`: issue supported browser roles only.
- Modify route modules under `src/api/routes/` to declare permissions.
- Modify CRM/call repositories used by route handlers to apply ownership predicates.
- Create backend policy, endpoint contract, IDOR, redaction, and approval tests.
- Create `apps/web/src/lib/permissions.ts` and update `apiClient.ts`/`Sidebar.tsx`.

---

### Task 1: Define the typed policy

**Files:**
- Create: `src/api/rbac.py`
- Test: `tests/test_rbac_policy.py`

**Interfaces:**
- Produces: `Role`, `Permission`, `Principal`, `ROLE_PERMISSIONS`, `has_permission()`.
- Consumes: none.

- [ ] **Step 1: Write failing policy tests**

```python
from src.api.rbac import Permission, Principal, Role, has_permission


def p(role: Role, scopes: frozenset[str] = frozenset()) -> Principal:
    return Principal(subject="u1", role=role, auth_type="session", scopes=scopes)


def test_owner_has_every_permission():
    assert all(has_permission(p(Role.OWNER), item) for item in Permission)


def test_admin_cannot_manage_secrets_or_deploy():
    assert not has_permission(p(Role.ADMIN), Permission.SECRETS_MANAGE)
    assert not has_permission(p(Role.ADMIN), Permission.SYSTEM_DEPLOY)


def test_seller_has_assigned_leads_but_no_finance():
    assert has_permission(p(Role.SELLER), Permission.LEAD_READ_ASSIGNED)
    assert not has_permission(p(Role.SELLER), Permission.FINANCE_READ)


def test_viewer_is_read_only():
    assert has_permission(p(Role.VIEWER), Permission.DASHBOARD_READ)
    assert not has_permission(p(Role.VIEWER), Permission.LEAD_WRITE)


def test_service_requires_exact_scope():
    service = p(Role.SERVICE, frozenset({"finance:read"}))
    assert has_permission(service, Permission.FINANCE_READ)
    assert not has_permission(service, Permission.FINANCE_WRITE)
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/test_rbac_policy.py -q`
Expected: FAIL because `src.api.rbac` does not exist.

- [ ] **Step 3: Implement minimal policy types**

```python
from dataclasses import dataclass, field
from enum import StrEnum


class Role(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    SELLER = "seller"
    VIEWER = "viewer"
    SERVICE = "service"


class Permission(StrEnum):
    DASHBOARD_READ = "dashboard:read"
    LEAD_READ_ALL = "lead:read:all"
    LEAD_READ_ASSIGNED = "lead:read:assigned"
    LEAD_WRITE = "lead:write"
    CALL_READ_ALL = "call:read:all"
    CALL_READ_OWN = "call:read:own"
    TRANSCRIPT_READ_ALL = "transcript:read:all"
    TRANSCRIPT_READ_OWN = "transcript:read:own"
    FINANCE_READ = "finance:read"
    FINANCE_WRITE = "finance:write"
    TELEGRAM_READ = "telegram:read"
    TELEGRAM_SEND = "telegram:send"
    MCP_READ = "mcp:read"
    MCP_WRITE = "mcp:write"
    USERS_MANAGE_LIMITED = "users:manage:limited"
    USERS_MANAGE_ALL = "users:manage:all"
    SECRETS_MANAGE = "secrets:manage"
    SYSTEM_READ = "system:read"
    SYSTEM_DEPLOY = "system:deploy"
    AUDIT_READ_ALL = "audit:read:all"
    AUDIT_READ_OWN = "audit:read:own"


@dataclass(frozen=True, slots=True)
class Principal:
    subject: str
    role: Role
    auth_type: str
    scopes: frozenset[str] = field(default_factory=frozenset)
```

Define `ROLE_PERMISSIONS` exactly from the approved matrix. For `Role.SERVICE`, `has_permission()` checks `permission.value in principal.scopes`.

- [ ] **Step 4: Verify pass**

Run: `pytest tests/test_rbac_policy.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/api/rbac.py tests/test_rbac_policy.py
git commit -m "feat(security): define Oisha RBAC policy"
```

---

### Task 2: Normalize credentials into Principal

**Files:**
- Modify: `src/api/security.py`
- Modify: `src/api/auth_service.py`
- Modify: `tests/test_api_access_security.py`

**Interfaces:**
- Consumes: `Principal`, `Role`.
- Produces: `authorize_request_values(...) -> Principal | None`.

- [ ] **Step 1: Add failing identity tests**

```python

def test_seller_and_viewer_sessions_are_authenticated():
    for role in ("seller", "viewer"):
        token = jwt.encode(
            {"sub": f"{role}-1", "role": role, "exp": int(time.time()) + 60},
            STRONG_SESSION_SECRET,
            algorithm="HS256",
        )
        principal = authorize_request_values(
            authorization="",
            api_secret="",
            proxy_user="",
            client_host="203.0.113.10",
            session_token=token,
            jwt_secret=STRONG_SESSION_SECRET,
            service_tokens_json="{}",
            proxy_role_map_json="{}",
        )
        assert principal.role.value == role


def test_service_token_is_scope_limited():
    principal = authorize_request_values(
        authorization="Bearer svc-token",
        api_secret="owner-token",
        proxy_user="",
        client_host="203.0.113.10",
        session_token="",
        jwt_secret=STRONG_SESSION_SECRET,
        service_tokens_json='{"svc-token":{"subject":"finance-sync","scopes":["finance:read"]}}',
        proxy_role_map_json="{}",
    )
    assert principal.role.value == "service"
    assert principal.scopes == frozenset({"finance:read"})


def test_unmapped_loopback_proxy_user_is_rejected():
    principal = authorize_request_values(
        authorization="",
        api_secret="",
        proxy_user="unknown",
        client_host="127.0.0.1",
        session_token="",
        jwt_secret=STRONG_SESSION_SECRET,
        service_tokens_json="{}",
        proxy_role_map_json='{"known":"admin"}',
    )
    assert principal is None
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/test_api_access_security.py -q`
Expected: FAIL because the current code returns dictionaries and auto-promotes proxy users.

- [ ] **Step 3: Implement strict resolution order**

```text
1. Exact OISHA_API_SECRET -> owner principal for legacy trusted internal calls.
2. OISHA_SERVICE_TOKENS_JSON -> service principal with explicit scopes.
3. Loopback proxy + OISHA_PROXY_ROLE_MAP_JSON mapping -> mapped browser role.
4. Strong-key signed JWT -> owner/admin/seller/viewer.
5. Otherwise -> None.
```

Environment contracts:

```dotenv
OISHA_SERVICE_TOKENS_JSON={}
OISHA_PROXY_ROLE_MAP_JSON={}
```

Reject malformed JSON, empty subjects, unknown roles, and browser role `service`.

- [ ] **Step 4: Keep safe JWT issuance**

```python
SUPPORTED_BROWSER_ROLES = {"owner", "admin", "seller", "viewer"}
normalized_role = requested_role if requested_role in SUPPORTED_BROWSER_ROLES else "viewer"
```

- [ ] **Step 5: Verify pass**

Run: `pytest tests/test_api_access_security.py tests/test_rbac_policy.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/api/security.py src/api/auth_service.py tests/test_api_access_security.py
git commit -m "feat(security): normalize Oisha principals"
```

---

### Task 3: Add permission dependencies and sanitized audit events

**Files:**
- Create: `src/api/security_audit.py`
- Modify: `src/api/rbac.py`
- Create: `tests/test_permission_dependency.py`
- Create: `tests/test_security_audit.py`

**Interfaces:**
- Produces: `require_permissions(*permissions)`, `SecurityAuditEvent`, `emit_security_audit()`.
- Consumes: `authorize_connection()`, `has_permission()`.

- [ ] **Step 1: Write failing dependency tests**

```python

def test_missing_auth_is_401(client):
    assert client.get("/private-finance").status_code == 401


def test_authenticated_but_forbidden_is_403(client, seller_cookie):
    assert client.get("/private-finance", cookies=seller_cookie).status_code == 403


def test_owner_is_allowed(client, owner_cookie):
    assert client.get("/private-finance", cookies=owner_cookie).status_code == 200
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/test_permission_dependency.py -q`
Expected: FAIL because permission dependencies do not exist.

- [ ] **Step 3: Implement dependency factory**

```python
def require_permissions(*required: Permission):
    async def dependency(connection: HTTPConnection) -> Principal:
        principal = authorize_connection(connection)
        if principal is None:
            raise HTTPException(status_code=401, detail="Unauthorized")
        if not all(has_permission(principal, item) for item in required):
            emit_security_audit(SecurityAuditEvent.denied(principal, connection, required))
            raise HTTPException(status_code=403, detail="Forbidden")
        return principal
    dependency.__oisha_permissions__ = tuple(item.value for item in required)
    return Depends(dependency)
```

- [ ] **Step 4: Implement sanitized audit schema**

```python
@dataclass(frozen=True, slots=True)
class SecurityAuditEvent:
    event_type: str
    subject: str
    role: str
    auth_type: str
    route: str
    method: str
    outcome: str
    permissions: tuple[str, ...]
    resource_type: str | None = None
    resource_id_hash: str | None = None
```

Hash resource identifiers with SHA-256. Do not serialize request headers or bodies.

- [ ] **Step 5: Verify pass and redaction**

Run: `pytest tests/test_permission_dependency.py tests/test_security_audit.py -q`
Expected: PASS and serialized events contain no sensitive field names.

- [ ] **Step 6: Commit**

```bash
git add src/api/rbac.py src/api/security_audit.py tests/test_permission_dependency.py tests/test_security_audit.py
git commit -m "feat(security): enforce permissions and audit denials"
```

---

### Task 4: Classify all private route families

**Files:**
- Modify: `src/api/routes/crm_dashboard.py`
- Modify: `src/api/routes/callmaster_routes.py`
- Modify: `src/api/routes/sales_quality.py`
- Modify: `src/api/routes/finance_dashboard.py`
- Modify: `src/api/routes/telegram_routes.py`
- Modify: `src/api/routes/telegram_mcp.py`
- Modify: `src/api/routes/system_dashboard.py`
- Modify: `src/api/routes/erp_routes.py`
- Modify: `src/api/routes/business_commands.py`
- Modify: `src/api/routes/marketing_dashboard.py`
- Modify: `src/api/routes/ai_analytics.py`
- Modify: `src/api/routes/amocrm_integration.py`
- Modify: `src/api/routes/instagram_routes.py`
- Modify: `src/api/routes/openclaw_gateway.py`
- Create: `tests/test_endpoint_permission_contract.py`

**Interfaces:**
- Consumes: `require_permissions()`.
- Produces: explicit permission metadata on every protected endpoint.

- [ ] **Step 1: Write the route inventory contract test**

```python
PUBLIC_PATHS = {
    "/healthz",
    "/api/auth/telegram/login",
    "/api/auth/telegram/callback",
    "/api/auth/airtable/callback",
}


def test_every_private_route_declares_permissions(app):
    missing = []
    for route in app.routes:
        path = getattr(route, "path", "")
        endpoint = getattr(route, "endpoint", None)
        protected = path.startswith(("/api/", "/internal/", "/mcp", "/telegram-mcp", "/client"))
        if protected and path not in PUBLIC_PATHS and not getattr(endpoint, "__oisha_permissions__", ()):
            missing.append(path)
    assert missing == []
```

- [ ] **Step 2: Run test and capture unclassified routes**

Run: `pytest tests/test_endpoint_permission_contract.py -q`
Expected: FAIL with a concrete route list.

- [ ] **Step 3: Apply approved permission defaults**

```text
CRM read -> dashboard:read plus lead read policy
CRM mutation -> lead:write
Calls/transcripts -> all or own permission by role
Finance -> finance:read / finance:write
Telegram -> telegram:read / telegram:send
MCP -> mcp:read / mcp:write
System -> system:read / system:deploy / secrets:manage
ERP/business commands -> exact read/write permission per endpoint
```

- [ ] **Step 4: Add role matrix integration tests**

For each route family, assert exact outcomes for owner, admin, seller, viewer, and scoped service identities.

- [ ] **Step 5: Verify pass**

Run: `pytest tests/test_endpoint_permission_contract.py tests/test_permission_dependency.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/api/routes tests/test_endpoint_permission_contract.py
git commit -m "feat(security): classify Oisha endpoint permissions"
```

---

### Task 5: Enforce seller ownership and viewer redaction

**Files:**
- Modify: `src/api/routes/crm_dashboard.py`
- Modify: `src/api/routes/callmaster_routes.py`
- Modify: `src/api/routes/sales_quality.py`
- Modify: repository methods called by those routes.
- Create: `tests/test_seller_object_isolation.py`
- Create: `tests/test_viewer_redaction.py`

**Interfaces:**
- Consumes: authenticated `Principal`.
- Produces: principal-scoped repository queries.

- [ ] **Step 1: Write failing IDOR tests**

```python

def test_seller_a_cannot_read_seller_b_lead(client, seller_a_cookie, seller_b_lead):
    response = client.get(f"/api/crm/leads/{seller_b_lead.id}", cookies=seller_a_cookie)
    assert response.status_code == 403


def test_seller_list_contains_only_assigned_records(client, seller_a_cookie):
    response = client.get("/api/crm/leads", cookies=seller_a_cookie)
    assert {item["assigned_to"] for item in response.json()["items"]} == {"seller-a"}


def test_seller_cannot_read_other_transcript(client, seller_a_cookie, seller_b_call):
    response = client.get(f"/api/calls/{seller_b_call.id}/transcript", cookies=seller_a_cookie)
    assert response.status_code == 403
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/test_seller_object_isolation.py -q`
Expected: FAIL because current queries are not principal-scoped.

- [ ] **Step 3: Add explicit repository scope**

```python
async def list_leads(*, principal: Principal, limit: int, offset: int): ...
async def get_lead(*, principal: Principal, lead_id: str): ...
async def get_call(*, principal: Principal, call_id: str): ...
```

Seller queries include the canonical `assigned_to = principal.subject` predicate. Owner/admin omit it. Viewer projections exclude phone, email, Telegram username, full transcript, internal notes, finance data, secret/config fields, and raw Telegram content.

- [ ] **Step 4: Verify pass**

Run: `pytest tests/test_seller_object_isolation.py tests/test_viewer_redaction.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/api/routes src/db tests/test_seller_object_isolation.py tests/test_viewer_redaction.py
git commit -m "fix(security): isolate seller-owned resources"
```

---

### Task 6: Add one-time owner approval for privileged writes

**Files:**
- Create: `src/api/write_approval.py`
- Modify: `src/api/routes/telegram_routes.py`
- Modify: `src/api/routes/telegram_mcp.py`
- Create: `tests/test_write_approval.py`

**Interfaces:**
- Produces: `ApprovalTicket`, `request_write_approval()`, `consume_write_approval()`.
- Consumes: Telegram/MCP permissions.

- [ ] **Step 1: Write failing approval tests**

```python

def test_admin_write_returns_pending_ticket(client, admin_cookie):
    response = client.post("/api/telegram/send", cookies=admin_cookie, json={"chat_id":"1","text":"hello"})
    assert response.status_code == 202
    assert response.json()["status"] == "approval_required"


def test_owner_consumes_ticket_once(client, owner_cookie, approval_ticket):
    assert client.post(f"/api/write-approvals/{approval_ticket}/execute", cookies=owner_cookie).status_code == 200
    assert client.post(f"/api/write-approvals/{approval_ticket}/execute", cookies=owner_cookie).status_code == 409
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/test_write_approval.py -q`
Expected: FAIL because approval tickets do not exist.

- [ ] **Step 3: Implement ticket contract**

```text
id, requester subject, permission, payload hash,
created_at, expires_at=10 minutes,
status=pending|approved|consumed|rejected
```

Owner may execute directly. Admin requests become pending. Seller/viewer are denied. Replay and expired tickets return `409`.

- [ ] **Step 4: Verify pass**

Run: `pytest tests/test_write_approval.py -q`
Expected: PASS for pending, approved, rejected, expired, and replay cases.

- [ ] **Step 5: Commit**

```bash
git add src/api/write_approval.py src/api/routes/telegram_routes.py src/api/routes/telegram_mcp.py tests/test_write_approval.py
git commit -m "feat(security): require owner approval for privileged writes"
```

---

### Task 7: Reflect roles in the web client

**Files:**
- Create: `apps/web/src/lib/permissions.ts`
- Create: `apps/web/src/lib/permissions.test.ts`
- Modify: `apps/web/src/lib/apiClient.ts`
- Modify: `apps/web/src/components/Sidebar.tsx`

**Interfaces:**
- Produces: `can(role, permission)` and normalized `ForbiddenError`.
- Consumes: backend role and permission strings.

- [ ] **Step 1: Write failing UI policy tests**

```ts
import { can } from './permissions';

it('does not show finance to seller', () => {
  expect(can('seller', 'finance:read')).toBe(false);
});

it('shows assigned leads to seller', () => {
  expect(can('seller', 'lead:read:assigned')).toBe(true);
});
```

- [ ] **Step 2: Verify failure**

Run: `pnpm --filter web test -- permissions.test.ts`
Expected: FAIL because `permissions.ts` does not exist.

- [ ] **Step 3: Implement mirrored navigation policy**

Use backend permission strings. UI hiding is navigation convenience only; backend checks remain authoritative.

- [ ] **Step 4: Normalize API errors**

```text
401 -> missing/expired session; login flow
403 -> authenticated but forbidden; access-denied state
```

- [ ] **Step 5: Verify web checks**

Run: `pnpm run typecheck && pnpm run lint && pnpm run test && pnpm run build`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/lib apps/web/src/components/Sidebar.tsx
git commit -m "feat(web): reflect Oisha role permissions"
```

---

### Task 8: Publish and verify the matrix

**Files:**
- Create: `docs/security/rbac-matrix.md`
- Modify: `.env.example`

**Interfaces:**
- Consumes all previous tasks.
- Produces deploy configuration and human-readable matrix.

- [ ] **Step 1: Document environment variables and matrix**

Include safe empty examples only and list every route family against all five identities.

- [ ] **Step 2: Run focused security tests**

```bash
pytest tests/test_rbac_policy.py \
  tests/test_api_access_security.py \
  tests/test_permission_dependency.py \
  tests/test_endpoint_permission_contract.py \
  tests/test_seller_object_isolation.py \
  tests/test_viewer_redaction.py \
  tests/test_write_approval.py -q
```

Expected: PASS.

- [ ] **Step 3: Run full checks**

```bash
pytest -q --tb=short
pnpm install --frozen-lockfile
pnpm run typecheck
pnpm run lint
pnpm run test
pnpm run build
```

Expected: PASS. Any runner/account infrastructure failure is documented separately and not presented as a code failure.

- [ ] **Step 4: Commit**

```bash
git add docs/security/rbac-matrix.md .env.example
git commit -m "docs(security): publish Oisha RBAC matrix"
```

- [ ] **Step 5: Open PR**

PR title: `feat(security): enforce complete Oisha RBAC matrix`

Evidence: focused tests, full checks, protected-route count, role-matrix coverage, seller IDOR result.
