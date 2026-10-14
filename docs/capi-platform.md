# JonBranding CAPI platformasi

Oisha private console: `/api/marketing/capi/console` (owner/admin). Existing
amoCRM status integration remains canonical: status 142 → Purchase;
`META_CAPI_QUALIFIED_STATUS_IDS` → QualifiedLead. Console reads existing
`capi_events`; these older rows do not identify dataset or test/live mode.

## Configuration and activation

Use deployment secret configuration, never the browser or version control:
`META_CAPI_DATASET_ID`, `META_CAPI_ACCESS_TOKEN`, `META_CAPI_ENABLED`,
`META_CAPI_TEST_EVENT_CODE`, and separate `OISHA_CAPI_INGEST_SECRET`.
No credential editing endpoint is exposed. Disabled intake may queue events,
but cannot dispatch. Enable only for an owner-approved test or activation.
Changing test/live mode or dataset never replays events into a different target.

## Website backend contract

Send `POST /api/marketing/capi/events` with `Authorization: Bearer <ingest secret>`.
The secret belongs on the website server, never client JavaScript. Maximum body
size is 16 KiB. Consent must be explicitly true. Supply the actual conversion
time, within seven days, and the same event ID used by the browser Pixel.

Fields: `source` (website or crm), `event_name`, `event_id`, `event_time`,
`consent`. Website requires HTTPS `event_source_url` without query/fragment,
`client_user_agent`, and at least phone, email, fbp or fbc. Purchase requires
finite positive `value` and explicit three-letter `currency`. CRM intake requires
Meta `leadgen_id`; this is not an amoCRM ID. Allowed events: PageView,
ViewContent, Lead, QualifiedLead, Purchase; CRM excludes page/content events.
CRM `event_id` must be `crm-<leadgen_id>-<event_name>` to match the existing sender.

JonBranding website adapter is implemented in `jonbranding-web/src/lib/oisha-capi-delivery.ts`.
Select it with server-only `OISHA_CAPI_URL` (full HTTPS intake endpoint) and
`OISHA_CAPI_INGEST_SECRET`. `/api/submit-form` forwards the observed analytics
consent cookie; absent consent skips CAPI. No automatic direct-to-Meta fallback
occurs when Oisha is selected. The adapter strips URL query/fragment and preserves
the Pixel event ID. An Oisha outage fails intake; website-side durable recovery
before an Oisha receipt is not implemented. A receipt is `queued`, not `delivered`.

Response HTTP 202 means durably queued (or duplicate), **not Meta acceptance**.
Raw phone/email are hashed before persistence. Hashes/cookies remain sensitive
matching data; restrict database access and implement deployment retention policy.
The panel returns no matching payload or credential. Producers must also avoid
personal data in page paths and user agent strings.

The API lifespan worker drains up to 20 due events every 30 seconds. Atomic
leases and stable IDs protect concurrent retries; stale pending claims recover
after ten minutes. Failure backoff grows to an hour. Event age remains original.
Events older than seven days become terminal `expired`; they require source review,
not falsifying event_time. Owner-only `POST /dispatch` runs the due queue early.
Failed legacy CRM events can be retried from the console; Purchase re-reads the
amoCRM amount instead of inventing a value. Automatic legacy CRM recovery remains
the responsibility of existing CRM/leadgen triggers.

## Acceptance and limits

Only Meta `events_received=1` marks the queued event sent. This is transport
acceptance, not proof of matching, attribution or ad performance. No production
activation is implied by local tests. Website producer installation, secure
credentials, accepted Test Events, approved live activation and live read-back
must be verified on the deployed services.

Meta reference: [official website CAPI sample](https://github.com/fbsamples/lead-ads-webhook-sample/blob/main/postman/FB%20Conversions%20API%20%28Part%201%20-%20online%29.postman_collection.json).
