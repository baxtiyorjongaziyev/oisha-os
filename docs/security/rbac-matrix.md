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
| Telegram | read/send | read/send | denied | denied | exact Telegram scope |
| MCP | read/write | read/write | denied | denied | exact MCP scope |
| System | all | read only | denied | denied | exact system scope |
| Secrets/deploy | all | denied | denied | denied | denied |

Seller ownership is enforced at query/filter time using the authenticated
principal subject. Missing ownership data fails closed. Viewer call responses
omit client identity and internal summaries.

## Configuration

`OISHA_SERVICE_TOKENS_JSON` maps a token to a stable subject and exact scopes:

```json
{"token-from-secret-store":{"subject":"finance-sync","scopes":["finance:read"]}}
```

`OISHA_PROXY_ROLE_MAP_JSON` maps only known loopback proxy users to browser
roles:

```json
{"nginx-user":"admin"}
```

Malformed JSON, unknown roles, empty subjects, unmapped proxy users, weak JWT
keys, expired sessions, and unknown credentials fail closed. Never commit real
tokens to either file or environment example.
