# amoCRM credential sources

`AmoCRMSync.__init__` delegates credential loading to `AmoCRMTokenLoaderMixin`.
The loader reads process environment variables, not the Pydantic settings object.
Ensure deployment exports the selected configuration into the service environment.

Default (`AMOCRM_TOKEN_SOURCE` unset or `auto`) precedence remains:
`AMOCRM_ACCESS_TOKEN` (long-lived), `AMOCRM_TOKEN_JSON`, constructor `token_file`
(default `data/amocrm_token.json`), raw `AMOCRM_REFRESH_TOKEN`, then DB fallback.

Set `AMOCRM_TOKEN_SOURCE=file` to use only the configured constructor token file;
`env_json` selects only `AMOCRM_TOKEN_JSON`; `long_lived` selects only
`AMOCRM_ACCESS_TOKEN`. A missing/unusable selected source fails closed with
`token_source_unavailable`; unknown selectors return `token_source_invalid`.
Explicit file selection does not attach the raw environment refresh token or
load DB credentials during startup. Normal OAuth refresh/rotation is unchanged.

A long-lived token's HTTP 401 is reported as
`long_lived_token_rejected_http_401`. It cannot be refreshed and does not trigger
automatic credential substitution. HTTP 401 alone does not establish whether
the token was revoked, belongs to a different account, or has another issue.

Owner rollout: select the separately verified source in the service environment,
ensure its file exists and is readable by the service user if selecting `file`,
restart the service, and verify the read-only account connection check. Never
paste credentials into logs, tickets, chat, or this document. Revoke/replace the
rejected long-lived credential in amoCRM as appropriate after owner verification.
No credential value or live endpoint was inspected by the implementation tests.
