# SalesCoach AI Architecture

SalesCoach AI runs side-by-side with the existing Python Oisha bot so the live Telegram/CRM
automation remains stable while the sales quality product is built in safe slices.

## Workspace Layout

- `salescoach-ai/apps/web`: Next.js dashboard, calls, upload, negotiate, and public share pages.
- `salescoach-ai/apps/api`: NestJS API, auth, organizations, calls, scorecards, shares, integrations, negotiations.
- `salescoach-ai/apps/worker`: BullMQ workers for transcription and scoring.
- `salescoach-ai/apps/bot`: Telegram bot for audio intake, summaries, and coaching notifications.
- `salescoach-ai/packages/shared-types`: Zod schemas and shared TypeScript types.
- `salescoach-ai/packages/ui`: reusable React UI primitives.
- `salescoach-ai/packages/config`: shared config presets.
- `src/services/core`: Python Oisha control plane for Telegram userbot, AmoCRM, and agent workflows.

## Real-Data Contract

The product must never present synthetic metrics as real business results.
For the SalesCoach/Metasell module, the only accepted sources are AmoCRM and Telegram through
the userbot.

Every metric should carry:

- `source`: `amocrm`, `telegram_userbot`, `amocrm_call_transcript`, or `unavailable`;
- `last_synced_at`;
- `confidence`: `low`, `medium`, or `high`;
- `evidence_url` or `evidence_id` when a drill-down exists.

If a source is unhealthy, the UI should show `Ma'lumot ulanmagan` or `Manba ishlamayapti`,
not a fabricated zero.

## Call Analysis Pipeline

1. A call is created from AmoCRM call records or Telegram userbot-visible voice/audio messages.
2. API stores the audio object reference and creates a `Call` row with source metadata.
3. API enqueues a transcription job.
4. Worker downloads audio through a server-side signed URL.
5. Worker transcribes the audio and stores timestamped speaker segments.
6. Worker computes deterministic voice metrics: talk ratio, words per minute, duration.
7. Worker sends transcript plus rubric to the LLM for structured scoring.
8. Worker validates the LLM JSON output before saving a `Scorecard`.
9. API exposes the call detail and scorecard.
10. Bot/worker sends coaching summary and creates verified follow-up tasks when configured.

## CRM And Telegram Context Pipeline

1. AmoCRM sync pulls leads, contacts, notes, stages, tasks, and call references.
2. Telegram userbot context is used only when policy allows it.
3. Personal/family/private chats are excluded from lead classification.
4. Matching uses phone number, username, shared groups, and conversation intent.
5. Oisha creates tasks only when evidence supports the next step.
6. Verifier checks AmoCRM and Telegram evidence after writing before reporting success.

## Share-Link Flow

1. Authenticated user creates a share link for one call.
2. API generates a 32-byte token and stores only `sha256(token)`.
3. The browser receives `https://.../public/calls/{id}#k={token}`.
4. Public page reads the token from the URL fragment and sends it in `X-Share-Key`.
5. API validates hash, expiry, revocation, and optional password.
6. API logs access with privacy-safe IP prefix and user-agent family.
7. API returns redacted call/scorecard/transcript data.

## Dashboard Data Flow

Dashboard cards should read from reviewed AmoCRM and Telegram-userbot adapters, not ad-hoc AI text.

- Sales and pipeline: AmoCRM.
- Revenue and payment-related sales movement: AmoCRM deal value/stage plus Telegram evidence when available.
- Call quality: call transcript + scorecards.
- Manager ranking: scorecards plus CRM activity.
- Lead quality and risk: AmoCRM lead context plus call/Telegram evidence.
- Service/PM quality is outside this module unless it is visible in AmoCRM or allowed Telegram context.

## Health And Rollout Rules

- `/healthz` is the service liveness and deploy gate.
- Source-health checks should be separate from process liveness.
- A service may be alive while AmoCRM, Telegram userbot, or Gemini is unhealthy; reports must show that distinction.
- Production deploy promotion should happen only after the new revision is ready and `/healthz` passes.
- Userbot should not run in Cloud Run; personal Telegram session belongs on the Oracle VM runtime.

## Current Implementation Status

Implemented foundation:

- TypeScript monorepo with web/api/worker/bot packages.
- Prisma models for organizations, users, calls, transcript segments, scorecards, share links.
- Calls API for upload/list/detail/transcript.
- Worker services for transcription/scoring scaffolding.
- Secure share-link module.
- Telegram bot scaffolding for audio intake and scorecard notifications.
- Python Oisha services for AmoCRM, Telegram userbot context, meeting scheduling, deal hygiene, and agent policies.

Still requiring hard verification before calling it production-complete:

- AmoCRM token health and real lead/call pull.
- Telegram userbot runtime and permission health.
- Gemini quota fallback and LLM cost guard.
- Worker end-to-end run on real audio.
- Dashboard source-health badges and fake-zero prevention.
- Verified AmoCRM task/note write-back.
- Oracle userbot runtime monitoring.
