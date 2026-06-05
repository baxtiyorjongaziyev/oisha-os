# SalesCoach AI PRD

SalesCoach AI is the sales quality and conversation-intelligence product inside Oisha OS.
It works only from two real sources: AmoCRM and Telegram through the userbot. It turns real
AmoCRM calls/leads plus allowed Telegram conversations into understandable Uzbek analytics,
coaching, alerts, and next-step tasks.

This document is based on the attached Metasell platform research, but Oisha must remain an
independent product: no copied brand, no copied UI wording, and no fake demo metrics.

## Non-Negotiable Product Rule

SalesCoach must be real-data-only and source-limited.

- Allowed sources: AmoCRM and Telegram userbot history.
- Disallowed for this module: Airtable, Google Calendar, Google Contacts, manual demo numbers, CSV-only demo data, and guessed metrics.
- If AmoCRM, call recordings, transcripts, or Telegram userbot context are unavailable, the UI and reports must say so clearly.
- Never invent active deals, revenue, manager scores, lead counts, conversion rates, or call quality percentages.
- Every dashboard metric must expose its source: AmoCRM, AmoCRM call transcript, Telegram userbot, or unavailable.
- Every AI conclusion must be traceable to evidence: AmoCRM lead link, AmoCRM call ID, transcript segment, CRM note/task, Telegram chat/message reference, or shared Telegram context.
- If evidence is partial, the output must use `Ishonch: past/o'rtacha/yuqori` and explain what is missing.

## Product Goal

Oisha should help Jon Branding agency run a higher-service sales process by:

- analyzing every usable call;
- detecting weak sales behaviors;
- creating exact follow-up actions;
- warning about lost opportunities before they are lost;
- showing managers what to improve;
- giving the owner a clean daily picture without manual checking.

## Primary Users

- Owner/Admin: manages business settings, users, billing, integrations, and global quality rules.
- ROP/Sales lead: monitors team quality, manager rankings, follow-up discipline, and coaching needs.
- Sales manager: sees their own calls, scores, weaknesses, and recommended next phrases.
- Public viewer: opens a single shared call review without full account access.

## Core Modules

### Header And Global Navigation

- Sidebar toggle for wide/narrow working mode.
- Global search by contact, lead, phone number, and keyword.
- Notifications panel with unread count and recent alerts.
- Light/dark theme support.
- Bug/idea report modal that can include current business context.
- Business switcher for multi-business ownership.
- User avatar menu with profile, settings, and logout.

### Dashboard

Dashboard blocks must be configurable and reorderable.

Required blocks:

- Business pulse: current situation, focus, and next recommendation.
- Quality overview: analyzed calls, average call quality, lead quality, unreachable calls, average duration.
- Sales criteria trend: progress by rubric criteria.
- Alerts: high-priority warnings with action buttons.
- Manager ranking: top and weak areas per manager.
- Why we are losing customers: objection and loss-reason analysis.
- Recent analyses: latest analyzed calls with status and links.
- CRM activity and results: optional, only shown when CRM data is healthy.

Dashboard period filters:

- today;
- week;
- month;
- custom date range.

### Calls List

The calls page must support filters by:

- call status: connected, waiting, analyzing, error, unanswered, wrong number, no audio, too short, bad recording, too long;
- call family: lead qualification, solution presentation, closing/negotiation, customer coordination, post-sale process, finance/admin, not business-related;
- service direction: naming, logo/visual identity, brandbook, packaging design, trademark registration, mixed, unknown;
- manager;
- date range.

Each row must show:

- date;
- manager;
- direction;
- duration;
- status;
- quality score or clear empty state;
- call family;
- action buttons for detail and delete.

### Call Detail

Every call detail page must include:

- back button;
- status badge;
- date/time;
- AmoCRM lead link when available;
- share button;
- short AI summary;
- call category tags;
- sales progress answer: did this call move the sale forward;
- next action;
- context card with call ID, manager, duration, direction, and CRM link;
- manager/customer talk ratio;
- customer information;
- previous calls with this contact;
- audio player;
- timestamped transcript;
- voice analytics;
- objections and buying signals;
- commitments by customer and manager.

### Analytics

Analytics tabs:

- Overview: sales, revenue, conversion, average deal, call quality, close-ready leads, tasks.
- Quality control: weakest rubric criteria first, with examples and coaching recommendation.
- Team development: who needs coaching now, on which skill, and which call to review.
- Customer analysis: objections, urgency, budget reaction, and loss reasons.
- Activity analysis: total calls, connected, unreachable, analyzed, scoreable calls, average duration.
- Lead analytics: new leads, won, lost, active, conversion, won value, cycle length, lead quality.

All analytics must be calculated from real source tables or source APIs. If the source is not
available, show `Ma'lumot ulanmagan` instead of zero unless zero is truly verified.

### Daily Summary

Daily summary must include:

- CRM activity;
- connected/unreachable rate;
- total talk time;
- comparison with previous work day;
- analyzed and scoreable calls;
- lead movement;
- manager-level summary;
- tomorrow recommendations;
- final owner summary.

Daily summary must not send if source health is broken, unless it explicitly says which source is broken.

### Lead Summaries

Lead summaries should combine:

- latest AmoCRM lead status;
- contact details;
- call history;
- transcript highlights;
- Telegram context when allowed by policy;
- next best action;
- owner/manager;
- urgency;
- confidence level.

### Alerts

Alert types:

- inactive manager;
- low performance;
- missed follow-up;
- call promised but task missing;
- high-risk lead;
- repeated unanswered attempts;
- negative objection pattern;
- CRM stage stuck;
- data source unhealthy.

Every alert must have:

- reason;
- evidence link;
- recommended action;
- owner;
- deadline;
- dismiss/mark-read controls.

### Settings

Settings must include:

- profile;
- business info;
- theme and language;
- businesses;
- work schedule;
- daily report settings;
- leaders;
- sales managers;
- subscription;
- sales rubric/playbook;
- integrations health.

### Sales Rubric

Default Jon Branding rubric:

- Greeting: manager and company introduction, source clarification, call purpose.
- Needs: customer situation, required service, decision/resource context.
- Value: offer tied to need, clear business benefit, right format recommended.
- Objections: price, timeline, and service-scope objections handled.
- Closing: brief sent/filled, expert meeting scheduled, payment/contract next step.
- Communication quality: professional tone, active listening, clear explanation.

Rubric must be configurable by service direction and call family.

### AI Assistant Chat

Chat must answer from real business context only:

- today's sales indicators;
- best manager this week;
- latest call analysis;
- pipeline condition;
- which leads need attention;
- what changed since yesterday.

If data is missing, it should explain the missing integration instead of guessing.

### CRM Lead Detail

CRM lead detail must show:

- lead title and status;
- value;
- contact and phone;
- company;
- manager;
- pipeline/stage;
- call attempts;
- analyzed calls;
- CRM notes;
- stage changes;
- grouped call history;
- audio player for completed calls;
- AI next action.

## MVP Capabilities

- Call ingestion from AmoCRM call records and Telegram userbot-visible voice/audio messages only.
- Transcription with speaker split, timestamps, and UZ/RU/mixed language detection.
- Rubric scoring across greeting, needs, value, objections, closing, and communication quality.
- Voice analytics for WPM, talk ratio, tone, energy, and diction signals.
- AI summary, good points, improvement points, risk flags, and recommended next phrase.
- Dashboard for team KPI, manager ranking, trends, and searchable call list.
- Secure share links with token in URL fragment, expiry, password option, revoke, and access log.
- Telegram notifications for manager coaching and owner/ROP daily rollup.
- AmoCRM note/task write-back after scorecard is ready.
- Telegram userbot context enrichment when policy allows it.

## Security Baseline

- Share tokens are 256-bit random values and only SHA-256 hashes are stored server-side.
- Public routes use `Cache-Control: private, no-store` and `X-Robots-Tag: noindex, nofollow`.
- Customer phone numbers are masked by default.
- Audio is served only through short-lived pre-signed URLs.
- Public access attempts are rate-limited and logged without storing full IP addresses.
- Public share pages must not load third-party analytics.

## Acceptance Criteria

- A real call can be ingested, transcribed, scored, and shown in the call detail page.
- A scorecard contains evidence-backed reasoning and deterministic talk-ratio/WPM metrics.
- Dashboard cards do not show invented numbers when CRM/call data is missing.
- A generated follow-up task is written to AmoCRM and verified after write.
- A public share link can be created, opened, expired, revoked, and audited.
- Daily summary includes source-health status and refuses silent fake reporting.
