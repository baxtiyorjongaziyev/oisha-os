# Oisha API RBAC matrix

Oisha authenticates every private API request at the existing
`ApiAccessMiddleware` perimeter, then authorizes it through explicit FastAPI
permission dependencies. Browser identities are `owner`, `admin`, `seller`,
and `viewer`; machine identities use `service` with exact permission scopes.

| Capability | owner | admin | seller | viewer | service |
|---|---|---|---|---|---|
| Dashboard | all | all | allowed | privacy-reduced | `dashboard:read` |
| Leads | all | all | assigned only | denied | exact lead scope |
| Calls | all | all | own only | redacted summary | exact call scope |
| Finance | read/write | read/write | denied | denied | exact finance scope |
| Telegram | direct read/send | read; send needs owner ticket | denied | denied | exact scope; write needs owner ticket |
| MCP | direct read/write | read; write needs owner ticket | denied | denied | exact scope; write needs owner ticket |
| System | all | read only | denied | denied | exact system scope |
| Secrets/deploy | all | denied | denied | denied | denied |

Seller ownership is enforced at query/filter time using the authenticated
principal subject. Missing ownership data fails closed. Viewer call responses
omit client identity and internal summaries.

## Machine and proxy identities

`OISHA_SERVICE_TOKENS_JSON` maps a token to a stable subject and exact scopes:

```json
{"token-from-secret-store":{"subject":"finance-sync","scopes":["finance:read"]}}
```

`OISHA_PROXY_ROLE_MAP_JSON` maps only known loopback proxy users to browser
roles. Production deployment requires this value because Nginx forwards the
Basic Auth username from loopback:

```json
{"oisha":"admin"}
```

Never place a password or bearer token in the proxy role map.

## Existing lead assignment backfill

`OISHA_LEAD_ASSIGNMENTS_JSON` is an explicit one-time mapping from existing
lead user IDs to seller subjects:

```json
{"123456":"seller-a","789012":"seller-b"}
```

The production deploy calls `POST /api/crm/lead-assignments/backfill` with the
owner bearer after readiness succeeds. Only rows with an empty `assigned_to`
value are updated. Later assignment or reassignment uses the audited endpoint:

```text
PUT /api/crm/leads/{user_id}/assignment
```

## Privileged write approvals

Owner identities may execute privileged Telegram/MCP writes directly. Admin
and scoped service identities receive a one-time approval ticket instead:

- ticket lifetime: 10 minutes;
- states: `pending`, `approved`, `consumed`, `rejected`, `expired`;
- only owner can approve/execute/reject;
- replay, expiry, wrong state, and missing ticket return HTTP 409;
- payload contents stay in process memory; responses and audit events contain
  only ticket ID, expiry, action, and SHA-256 payload hash.

The Oracle API is currently a single process. Before increasing API worker
count, move approval tickets to a shared transactional store.

## Audit policy

Authorization denials and privileged writes emit a fixed sanitized schema.
Audit events never include authorization headers, cookies, request bodies,
Telegram text, transcripts, contact details, raw finance values, or raw
resource IDs. Resource identifiers are SHA-256 hashed and URL query strings are
removed.

Malformed JSON, unknown roles, empty subjects, unmapped proxy users, weak JWT
keys, expired sessions, unknown credentials, and missing permissions fail
closed. Never commit real tokens to documentation or environment examples.
