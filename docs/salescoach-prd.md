# SalesCoach AI PRD

SalesCoach AI is the planned sales quality platform inside Oisha OS. It will turn real sales
calls into transcript, scorecard, coaching advice, manager ranking, and shareable call reviews.

## MVP roles

- Admin: manages organization, users, billing, and global settings.
- ROP: reviews team quality, calls, rankings, and coaching gaps.
- Manager: sees own calls, scores, coaching advice, and growth trend.
- Public viewer: opens one shared call review without account access.

## MVP capabilities

- Call ingestion from web upload, Telegram forward, and CRM webhooks.
- Transcription with speaker split, timestamps, and UZ/RU/mixed language detection.
- Rubric scoring across introduction, discovery, presentation, objection handling, and next step.
- Voice analytics for WPM, talk ratio, tone, energy, and diction signals.
- AI summary, good points, improvement points, and recommended next-call phrase.
- Dashboard for team KPI, manager ranking, trends, and searchable call list.
- Secure share links with token in URL fragment, expiry, password option, revoke, and access log.
- Telegram notifications for manager coaching and ROP daily rollup.

## Security baseline

- Share tokens are 256-bit random values and only SHA-256 hashes are stored server-side.
- Public routes use `Cache-Control: private, no-store` and `X-Robots-Tag: noindex, nofollow`.
- Customer phone numbers are masked by default.
- Audio is served only through short-lived pre-signed URLs.
- Public access attempts are rate-limited and logged without storing full IP addresses.
