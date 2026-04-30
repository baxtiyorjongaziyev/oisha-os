# SESSION NOTES — Claude Code konteksti

> Bu faylni har yangi sessiya boshida Claude'ga ko'rsat: "SESSION_NOTES.md ni o'qi"

---

## Loyihalar

### 1. Oisha-OS (`/home/user/oisha-os`)
- **Repo:** `baxtiyorjongaziyev/oisha-os`
- **Branch:** `claude/review-gstack-ZMeKZ` → `main`ga merged (PR #12)
- **Stack:** Python 3.12, Telethon, aiogram, Gemini, Turso, AmoCRM, FastAPI
- **Cloud:** Google Cloud Run (europe-west3), Cloud Secret Manager

**Nima qilindi:**
- gstack review → `docs/GSTACK_REVIEW.md`
- `CLAUDE.md` yaratildi (gstack skills uchun)
- `SurgicalNegotiator` autonomous pipeline'ga ulandi (`src/main.py`)
- DB persistence: `kv_settings` jadval, kalit `surgical_conv_{user_id}`
- AmoCRM real integration: `_get_crm_data()`, `_save_to_crm()`
- `SURGICAL_MODE`, `AUTONOMY_THRESHOLD` → `settings.py`ga qo'shildi
- Telegram send callback: `_surgical_send()` → `main.py`

**Muhim fayllar:**
- `src/main.py` — entry point, surgical pipeline wired here
- `src/agents/surgical_negotiator.py` — autonomous orchestrator
- `src/agents/autonomous_sales_agent.py` — DB persistence added
- `src/settings.py` — SURGICAL_MODE, AUTONOMY_THRESHOLD

---

### 2. SalesCoach AI (`/home/user/oisha-os/salescoach-ai/`)
- **Repo:** xuddi oisha-os ichida subdirectory sifatida tracked
- **Stack:** TypeScript, pnpm workspaces, Turborepo, NestJS 10, Prisma, Next.js 15, BullMQ, Grammy

**Nima qilindi (barcha 7 Prompt):**
- Monorepo: pnpm + Turborepo, Docker Compose (postgres:16, redis:7, minio)
- `apps/api`: NestJS 10 + Fastify + Prisma — auth (JWT/Google OAuth), calls upload (presigned S3), scorecards, share-links (token-in-fragment), organizations
- `apps/worker`: BullMQ — Whisper transcription + Claude Sonnet scoring
- `apps/web`: Next.js 15 — dashboard, call detail, upload, share viewer, auth pages
- `apps/bot`: Grammy Telegram bot — audio upload pipeline, /score komandasi
- `packages/shared-types`: Zod schemalar
- `packages/ui`: Button, Badge, Card
- Prisma migration ishlatildi, API haqiqatan ishga tushirildi va test qilindi

**API ishlaydi:**
- `GET /v1/health` → `{status: "ok", database: "up"}`
- `POST /v1/auth/register` → `{accessToken, refreshToken}`
- `GET /v1/users/me`, `GET /v1/organizations/me` — JWT auth ishlaydi

**Infra (local):**
- Docker: `docker compose up -d` (salescoach-ai/ papkasida)
- DB: `postgresql://salescoach:salescoach_dev@localhost:5432/salescoach`
- MinIO: `http://localhost:9000` (minioadmin/minioadmin)

**Nima kerak hali:**
- `.env` ga `BOT_TOKEN` → bot ishlaydi
- `.env` ga `ANTHROPIC_API_KEY` → scoring worker ishlaydi
- `GOOGLE_CLIENT_ID/SECRET` → Google OAuth ishlaydi
- Next.js frontend hali ishga tushirilmagan (pnpm install kerak)

**Muhim fayllar:**
- `salescoach-ai/apps/api/src/main.ts`
- `salescoach-ai/apps/api/prisma/schema.prisma`
- `salescoach-ai/apps/api/src/auth/` — JWT + Google + Local
- `salescoach-ai/apps/api/src/shares/shares.service.ts` — token-in-fragment security
- `salescoach-ai/apps/worker/src/jobs/scoring.worker.ts` — Claude Sonnet scoring
- `salescoach-ai/.env` — credentials (gitignored)

---

## Token tejash qoidalari
- Katta fayllarni to'liq o'qima — `grep` yoki `Explore` agent ishlat
- `docs/knowledge_base.md` — Jon Branding biznes konteksti
- `docs/salescoach-prd.md` — SalesCoach AI to'liq PRD
- `CLAUDE.md` — Oisha-OS arxitektura va buyruqlar

## Muhim buyruqlar
```bash
# Oisha-OS tests
PYTHONPATH=/home/user/oisha-os python -m pytest -q

# SalesCoach API ishga tushirish
cd /home/user/oisha-os/salescoach-ai/apps/api
node dist/main.js

# Docker (SalesCoach infra)
cd /home/user/oisha-os/salescoach-ai
docker compose up -d

# Git branch
cd /home/user/oisha-os
git checkout claude/review-gstack-ZMeKZ
```
