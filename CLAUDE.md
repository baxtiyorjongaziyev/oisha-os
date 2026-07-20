# Oisha-OS — CLAUDE.md

## Project Overview

Oisha-OS is an autonomous internal management system ("Surgical COO") for Jon Branding
Agency. It manages AmoCRM leads, Telegram communications, finance ("Hisobchi"), Instagram/Meta
messaging, and team workflows through a fleet of AI-driven agents.

**Core persona:** Oisha — autonomous, authoritative, focused on operational precision.
Much of the codebase (comments, `AGENTS.md`, `DEV_LOG.md`, `.env.example`) is written in a
mix of **Uzbek and English** — this is expected, not noise.

> This repository is a **polyglot monorepo**. The primary system is a Python/asyncio
> Telegram + AmoCRM automation platform under `src/`. Alongside it live several
> TypeScript products (`apps/`, `packages/`, `salescoach-ai/`), a marketing OAuth app
> (`marketing-os/`), and n8n workflow definitions (`n8n/`). Know which subsystem you are
> in before editing.

## Tech Stack (Python core)

- **Runtime:** Python 3.11 (Docker image is `python:3.11-slim-bookworm`), asyncio
- **Telegram:** Telethon (userbot) + aiogram / python-telegram-bot (admin & guest bots) + a
  Telegram-MCP approval gateway (`mcp` package)
- **AI:** Google Gemini via `google-genai`, plus a **multi-provider free-AI router**
  (`src/services/utils/free_ai_router.py`) fronting Groq, Cloudflare Workers AI, Ollama,
  Cerebras, SambaNova, Together AI, OpenRouter, NVIDIA NIM, Mistral, HuggingFace, with
  OpenAI / Anthropic / DeepSeek as paid fallback (`ENABLE_PAID_AI_FALLBACK`)
- **Database:** Turso (libsql, remote) + SQLite (local fallback via `aiosqlite`)
- **CRM:** AmoCRM v4 REST API (+ Moizvonki call integration)
- **Sync / Integrations:** Airtable, Google Sheets/Drive/Calendar/Contacts, Instagram/Meta
  Graph API, DocuSign, Apollo, SMS Gateway (sms-gate.app)
- **API:** FastAPI + uvicorn (internal HTTP control plane, `src/api_server.py`)
- **Infra:** **Oracle Cloud VM (primary, systemd)**; Google Cloud Run / Cloud Build (legacy
  fallback); legacy VPS userbot

## Commands

### Python testing / gates
```bash
# Fast gate tests (skip live API calls — this is the CI/preflight default)
SKIP_LIVE=1 python -m pytest -q

# Full run with coverage (as CI runs it)
pytest --cov=src --cov-report=xml

# Single test file
python -m pytest tests/test_api_server_security.py -v
```

### Security scan (must pass before every PR)
```bash
bandit -r src/ -ll -x src/services/debug/ --quiet
```

### Pre-flight checklist (run before every PR — see AGENTS.md)
```bash
SKIP_LIVE=1 python -m pytest -q --tb=short
bandit -r src/ -ll
```

### Run the Python app locally
```bash
# Requires a populated .env (copy from .env.example)
python src/main.py
```

### TypeScript monorepo (root apps/ + packages/)
```bash
pnpm run build       # turbo build all
pnpm run dev         # turbo dev --parallel
pnpm run lint        # turbo lint
pnpm run test        # turbo test
pnpm run typecheck   # turbo typecheck
pnpm run format      # prettier
```

### Docker dev stack (Makefile helpers)
```bash
make up          # docker compose up postgres + redis + minio
make python-test # python -m pytest -q
```

## Project Structure

```
src/
  main.py                   # Entry point (run target). Delegates wiring to boot.py
  boot.py                   # Service wiring, client init, background-task registration
                            #   (extracted from the former ~4000-line main.py God Object)
  settings.py               # Pydantic AppSettings (reads env / .env; SecretStr for secrets)
  config.py / context.py    # Runtime config + app_ctx singleton (shared state)
  database.py               # Turso/SQLite singleton (TursoAdapter)
  database_pool.py          # Connection pool with SmartRow adapter
  api_server.py             # FastAPI app (title "Oisha-OS Enterprise API"); mounts routers
  admin_bot.py / userbot.py # Bot entrypoints
  scheduler.py              # APScheduler wiring
  agents/                   # Domain AI agents (sales, negotiation, finance, PM, support,
                            #   researcher, copywriter, referral, upsell, deal lifecycle, …)
  controllers/              # message_controller.py, surgical_integration.py — event routing
  handlers/                 # Telegram handlers split out of the old monolith
                            #   (negotiation, kirim, payments, meeting, case_publisher, …)
  commands/                 # Slash-command modules (crm, calendar, dashboard, erp, sync, …)
  api/                      # FastAPI sub-app: routes/ (health, telegram_mcp, erp, instagram,
                            #   crm_dashboard, marketing_dashboard, chat_widget, …) + auth
  schedulers/               # Background jobs (frog_scheduler, instagram_weekly_reporter,
                            #   daily_analytics_reporter, brain_evolution, background_monitor)
  services/
    core/                   # ~115 production agents & services. Sub-packages:
      crm/                  #   AmoCRM sync, enrichment, guard, cleaner, archiver, night-shift
      finance/              #   Hisobchi engine/handlers/schema, ERP dashboard, card parser
      leads/                #   lead_scraper and lead pipelines
      telegram/             #   session_manager and Telegram helpers
      telegram_mcp/         #   MCP approval-gateway plumbing
      agent_loop.py         #   Planner → Executor → Verifier cycle
      agent_policy.py       #   Guardrails: quiet-hours, approval gates, auto_actions
      agent_verifier.py / agent_brain.py / agent_runtime.py / agent_orchestrator.py
      instagram_agent.py    #   Meta Graph DM/comment webhooks
      tool_registry.py      #   Standardised ToolResult schema
      tool_adapters.py      #   Telegram / AmoCRM / Airtable adapters
      enterprise_reporter.py, negotiation_engine.py, advisor_agent.py, audit_agent.py, …
    ai/                     # AI wrappers: conversation_engine, quality_analyzer, frog_agent
    edge/                   # edge_personalizer (Cloudflare Workers AI / GA4)
    utils/                  # free_ai_router, scouter, voice, access_manager, meta_webhook,
                            #   sms/finance helpers, scrapers
    debug/                  # One-off diagnostic scripts — NOT production, excluded from bandit
tests/                      # ~90 pytest modules (test_*.py); conftest.py; SKIP_LIVE gating
docs/                       # AGENT_ROADMAP, IDEAL_AI_AGENT, salescoach-*, integration guides
deploy/ ops/ scripts/       # systemd units, watchdog, Oracle setup, CLI + pipeline scripts
n8n/workflows/              # n8n JSON workflow definitions (lead lifecycle, reports, gates)
marketing-os/               # Standalone Meta-OAuth app: FastAPI backend/ + Vite/React frontend/
apps/ packages/             # Root TypeScript monorepo (SalesCoach AI) — see below
salescoach-ai/              # Second, self-contained TypeScript monorepo (api/bot/web/worker)
```

## Architecture

### Agent Loop
```
Task → Planner (Gemini/free-AI) → Executor (tool_adapters) → Verifier → audit log
```
New agents standardise on `tool_registry.ToolResult` and route LLM calls through the
free-AI router so provider outages degrade gracefully.

### Multi-agent coordination
`AGENTS.md` is a live **agent coordination protocol** — multiple AI agents (Claude, Codex,
Gemini, etc.) collaborate on this repo. Read it before large changes: it defines file
ownership (`## Roles`), a `## Locks` section (one writer per file at a time), the pre-flight
checklist, commit/branch conventions, and a "Dead Files (don't touch)" list.

### Key subsystems
| Subsystem | Location | Role |
|---|---|---|
| MessageController | `controllers/message_controller.py` | Routes Telegram events to agents |
| Agent fleet | `src/agents/` | Sales, negotiation, PM, finance, support, research agents |
| Hisobchi (Finance) | `services/core/finance/` | Telegram-topic accounting + Google Sheets backend |
| CRM engine | `services/core/crm/` | AmoCRM sync, enrichment, cleanup, guard |
| Instagram/Meta | `services/core/instagram_agent.py`, `api/routes/instagram_routes.py` | DM/comment webhooks, weekly reports |
| Telegram MCP gateway | `services/core/telegram_mcp/` | Owner-approved Telegram tool mutations |
| EnterpriseReporter | `services/core/enterprise_reporter.py` | Daily plan + audit reports |
| Free-AI router | `services/utils/free_ai_router.py` | Multi-provider LLM failover |

### Runtime (important: Oracle is primary now)
- **Oracle Cloud VM** — **primary production**. Runs `src/main.py` under systemd
  (`oisha-os.service`), owns the single userbot session. **Never run a parallel userbot
  locally** — it invalidates the Oracle session with `AuthKeyDuplicatedError`. Set
  `ALLOW_LOCAL_RUN=0` unless you know what you're doing.
- **Cloud Run / Cloud Build** — legacy fallback (`cloudbuild.yaml`, `scripts/entrypoint.sh`,
  `RUNNING_IN_CLOUD=True`). GitHub Actions self-hosted runner is the canonical rollout path.
- **VPS** — legacy Telethon userbot (`userbot-vps.yml`).
- Runtime is auto-detected via `services/core/agent_runtime.py` (`resolve_runtime_mode`).

### FastAPI control plane
`src/api_server.py` exposes `app` and mounts routers from `src/api/routes/`. Health:
`GET /healthz` (+ `/health`) and `GET /readyz`. Other routers cover dashboards, telegram-mcp,
CRM, ERP, Instagram, chat widget, sales-quality, marketing.

### Telegram MCP approval gateway
Two local ports: upstream `127.0.0.1:8765/mcp`, owner-approval gateway `127.0.0.1:8766/mcp`.
`TELEGRAM_MCP_SESSION_STRING` must be a **dedicated** session, never equal to
`USERBOT_SESSION_STRING`. Read tools are automatic; every mutation is owner-approved via
Telegram. Neither port may be exposed publicly (Nginx).

### Database
- Primary: Turso (`TURSO_DATABASE_URL` + `TURSO_AUTH_TOKEN`) for cloud/production
- Local: SQLite via `DATABASE_URL=file:oisha.db`
- All writes go through `database_pool.py` — never open raw connections
- Schema: leads, daily_plans, job_traces, agent_state, tasks (incl. Frog fields), finance tables

## Environment Variables

Copy `.env.example` → `.env` (it is the authoritative, commented list). Highlights:

Required:
```
API_ID / API_HASH        Telegram app credentials
BOT_TOKEN                Telegram bot token
USERBOT_SESSION_STRING   Telethon userbot session (Oracle-owned in prod)
GEMINI_API_KEY           Google Gemini
AMOCRM_CLIENT_ID / AMOCRM_CLIENT_SECRET / AMOCRM_SUBDOMAIN   AmoCRM OAuth
DATABASE_URL             Local SQLite (file:oisha.db) or libsql URL
TURSO_AUTH_TOKEN         Turso auth (with TURSO_DATABASE_URL in cloud)
```

Common optional groups:
```
# Free/fallback LLMs
GROQ_API_KEY, CLOUDFLARE_ACCOUNT_ID/CLOUDFLARE_AI_API_TOKEN, OLLAMA_BASE_URL,
CEREBRAS_API_KEY, SAMBANOVA_API_KEY, TOGETHERAI_API_KEY, OPENROUTER_API_KEY,
NVIDIA_NIM_API_KEY, MISTRAL_API_KEY, HUGGINGFACE_API_KEY,
OPENAI_API_KEY, ENABLE_PAID_AI_FALLBACK

# Telegram MCP gateway
TELEGRAM_MCP_ENABLED, TELEGRAM_MCP_SESSION_STRING, TELEGRAM_MCP_UPSTREAM_URL

# Meta / Instagram
META_VERIFY_TOKEN, META_PAGE_ACCESS_TOKEN, META_APP_SECRET, META_INSTAGRAM_USER_ID

# Hisobchi finance (Telegram topics + Google Sheets)
HISOBCHI_FINANCE_GROUP_ID, HISOBCHI_*_TOPIC_ID, HISOBCHI_GSHEET_ID, HISOBCHI_GSHEET_CREDS_FILE

# Integrations
AIRTABLE_API_KEY/AIRTABLE_BASE_ID, MOIZVONKI_EMAIL/PASSWORD,
SALESCOACH_*, DOCUSIGN_*, APOLLO_* (all getattr-guarded — safe when unset)

# Operation modes / guardrails
OWNER_ID, WHITELIST_IDS, ENABLE_AUTO_REPLY (default off), AUTO_REPLY_MODE,
ALLOW_LOCAL_RUN, ENABLE_CLOUD_USERBOT, SURGICAL_MODE, ENABLE_AI_NEGOTIATION
```

## CI/CD

- **`test.yml`** — CI on `main`/PRs (path-filtered to `src/`, `tests/`, `requirements*`).
  Runs on the **self-hosted Oracle runner**: bandit → `pytest --cov` → Codecov.
- **`oracle-deploy.yml`** — **primary production deploy** to the Oracle VM (self-hosted,
  health-verified via `/readyz`). Skips commits starting with `chore(auto):`.
- Other workflows: `codeql.yml`, `gitleaks.yml`, `oisha-web.yml`, `userbot-vps.yml`,
  `generate-session.yml`/`verify-session.yml`, `mcp-diagnose.yml`, plus scheduled AmoCRM
  audits (`amocrm-*.yml`) and greetings (`juma-greeting.yml`, `qurbon-greeting.yml`).
- **Skip CI:** commit message containing `[skip ci]` or starting with `chore(auto):`.

## Guardrails

- `services/core/agent_policy.py` — blocks actions during quiet-hours
  (23:00–07:00 Tashkent), requires approval for destructive CRM actions
- `services/core/auto_reply_gate.py` — gates autonomous Telegram replies behind
  `ENABLE_AUTO_REPLY` / `AUTO_REPLY_MODE`
- `WHITELIST_IDS` / `OWNER_ID` — only whitelisted Telegram IDs get full agent capabilities
- Telegram MCP mutations are owner-approved; MCP ports stay private
- `src/services/debug/` — excluded from bandit, must NEVER be imported in production
- Do not run a local userbot while Oracle owns the session (see Runtime)

## TypeScript Monorepos

### Root workspace (SalesCoach AI) — `apps/` + `packages/`
- **Package manager:** pnpm 10.33.2 · **Build:** Turborepo 2.10+ · **TypeScript:** 6.x
- `pnpm-workspace.yaml` globs `apps/*` and `packages/*` with dependency `overrides`
  (`@babel/core`, `js-yaml`, `multer`, `postcss`) for security pins.

| App | Stack | Purpose |
|-----|-------|---------|
| @salescoach/api | NestJS | REST API backend |
| @salescoach/web | Next.js + React | Dashboard frontend |
| @salescoach/worker | BullMQ + ioredis | Async job processing |

| Package | Purpose |
|---------|---------|
| @salescoach/shared-types | Zod schemas, shared types |
| @salescoach/ui | React component library |
| @salescoach/config | ESLint, Prettier, TSConfig |

### Second workspace — `salescoach-ai/`
Fully self-contained monorepo with its own `pnpm-workspace.yaml`, `turbo.json`, and
`apps/` (api, bot, web, worker) + `packages/`. Includes an MCP `server.ts` and a
`call-intel/*` pipeline (Fireflies + Gong → scoring queue). **Two distinct workspaces
exist — do not mix root `apps/` with `salescoach-ai/apps/`.**

### marketing-os/
Standalone Meta-OAuth app (independent of the pnpm workspaces): FastAPI `backend/`
(`main.py`, `db.py`) + Vite/React `frontend/`. Handles Meta app auth callbacks.

## Docker & Infrastructure

### docker-compose.yml (dev stack)
- **oisha** — main Python app (850M mem limit)
- **postgres:16** — SalesCoach DB
- **redis:7** — cache + BullMQ queue
- **minio** — S3-compatible object storage

### Deployment targets
| Target | Use |
|--------|-----|
| Oracle Cloud VM (systemd) | **Primary production** (Python core + userbot) |
| Google Cloud Run / Cloud Build (europe-west3) | Legacy fallback |
| VPS | Legacy Telethon userbot |
| Oracle web (`oisha.jonbranding.uz`) | Admin web UI |

## AI Providers

| Provider | Use | Config |
|----------|-----|--------|
| Google Gemini (2.5-flash / 2.0-flash / 2.5-flash-lite) | Primary reasoning, vision, calls | `GEMINI_API_KEY`, `GEMINI_*_MODEL` |
| Groq / Cloudflare / Ollama / Cerebras / SambaNova / Together / OpenRouter / NVIDIA / Mistral / HuggingFace | Free-tier router failover | provider `*_API_KEY` |
| OpenAI / Anthropic / DeepSeek | Paid fallback | `*_API_KEY`, `ENABLE_PAID_AI_FALLBACK` |
| AWS Bedrock (Claude) | Fallback | AWS credentials |

## Development Notes

- New agents should return `tool_registry.ToolResult` for standardised output.
- Route LLM calls through `free_ai_router` and specify Gemini models explicitly
  (`gemini-2.5-flash` for speed, larger models for complex reasoning).
- Database writes must go through `database_pool.py` — never open raw connections.
- Quiet-hours and approval gates must not be bypassed for CRM or Telegram actions.
- `src/services/debug/`, `src/agents/` internals, and any `src/legacy/` are treated as
  out-of-scope for refactors (see `AGENTS.md` → Dead Files).
- Shared files (`settings.py`, `context.py`, `boot.py`) are coordinator-owned — coordinate
  via `AGENTS.md` before editing.
- Use `pnpm`, never `npm`, in the TypeScript workspaces; keep the two workspaces separate.
- Branch naming: `feat/<desc>` or `fix/<desc>`. Commit style: `feat(scope): message`,
  `fix(scope): …`, `refactor(scope): …`.
- `DEV_LOG.md` and `AGENTS.md` track running history/coordination — skim them for context
  on recent work before starting.
