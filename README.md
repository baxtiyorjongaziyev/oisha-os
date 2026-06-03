# Oisha OS

Oisha OS is Jon Branding Agency's internal agentic COO. The production bot runs on the
Oracle VM service and works with Telegram, Turso, AmoCRM, and Airtable.

## Core platform

- Python control plane for Telegram bot, reporting, CRM/Airtable sync, and agent workflows.
- Turso/libSQL database layer for production persistence.
- Oracle VM healthy-only rollout through GitHub Actions.
- Telegram deploy notifications with one final status per commit.
- Google Cloud is not used for the Oisha runtime. Any legacy GCP cleanup or setup script is
  blocked unless `OISHA_ALLOW_GCP=1` is set explicitly.

## Oisha Sales OS suite

Oisha now combines three product layers in one amoCRM + Telegram operating system:

- DeepSales-style lead intelligence: phone-based enrichment, buyer context, scoring, source tags.
- Metasell-style conversation intelligence: call transcription, Uzbek summaries, coaching, and next-step tasks.
- Reportagram-style revenue reporting: daily, weekly, and monthly funnel reports with SLA alerts.

The product contract is exposed at `GET /api/oisha/product-suite` and documented in
`docs/oisha-sales-os-suite.md`.

## SalesCoach AI workspace

The repository now also contains a TypeScript monorepo foundation for the SalesCoach AI product:

- `apps/web`: Next.js 15 dashboard shell.
- `apps/api`: NestJS API shell with `/healthz`.
- `apps/worker`: BullMQ worker shell with `/healthz`.
- `packages/shared-types`: shared Zod schemas and TypeScript types.
- `packages/ui`: shared React UI primitives.
- `packages/config`: shared tool presets.

This is Prompt 1 from the SalesCoach AI plan: tooling, health checks, and dev infrastructure only.
Business logic starts in the next prompts.

## Local development

Install JavaScript dependencies:

```bash
pnpm install
```

Start Postgres, Redis, and MinIO for the SalesCoach AI workspace:

```bash
make up
```

Run the TypeScript workspace:

```bash
pnpm dev
```

Run checks:

```bash
pnpm typecheck
pnpm build
pnpm test
python -m pytest -q
```

## Existing Python bot

The existing Oisha bot is started and deployed through the Oracle VM workflow. The SalesCoach AI
workspace is added side-by-side so the live bot is not broken while the new product is built.
