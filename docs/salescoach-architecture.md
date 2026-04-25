# SalesCoach AI Architecture

This workspace starts as a side-by-side monorepo so the existing Python Oisha bot stays stable
while the sales quality product is built in safe slices.

## Workspace layout

- `apps/web`: Next.js dashboard and public share pages.
- `apps/api`: NestJS API and future Prisma-backed business modules.
- `apps/worker`: BullMQ worker for ingest, transcribe, score, and notify jobs.
- `packages/shared-types`: Zod schemas and TypeScript types shared across apps.
- `packages/ui`: reusable React UI primitives.
- `packages/config`: shared config presets.

## Pipeline target

1. API creates a call row and stores the audio object reference.
2. Worker transcribes audio and saves timestamped speaker segments.
3. Worker scores the transcript with deterministic metrics plus LLM rubric output.
4. API exposes authenticated call detail and secure public share access.
5. Telegram sends coaching summaries and manager rollups.

## Current status

Prompt 1 is infrastructure-only: health endpoints, workspace wiring, and local services for
Postgres, Redis, and MinIO. Auth, Prisma models, CRM ingestion, transcription, scoring, and
share-link security are intentionally reserved for the next prompts.
