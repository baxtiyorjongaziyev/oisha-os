# Oisha-OS — CLAUDE.md

## Project Overview

Oisha-OS is an autonomous internal management system ("Surgical COO") for Jon Branding Agency. It manages AmoCRM leads, Telegram communications, and team workflows through AI-driven agents.

**Core persona:** Oisha — autonomous, authoritative, focused on operational precision.

## Tech Stack

- **Runtime:** Python 3.12, asyncio
- **Telegram:** Telethon (userbot) + aiogram (admin bot)
- **AI:** Google Gemini 1.5 Flash / Pro via `google-generativeai` and `google-genai`
- **Database:** Turso (libsql, remote) + SQLite (local fallback via `aiosqlite`)
- **CRM:** AmoCRM v4 REST API
- **Sync:** Airtable, Google Sheets, Google Drive
- **API:** FastAPI + uvicorn (internal HTTP control plane)
- **Infra:** Google Cloud Run (primary), VPS (legacy userbot), Cloud Secret Manager, Cloud Build

## Commands

### Testing
```bash
# Fast gate tests (run always)
python -m pytest -q

# Single test file
python -m pytest tests/test_api_server_security.py -v

# Skip live API tests (CI default)
SKIP_LIVE=1 python -m pytest -q
```

### Security scan
```bash
bandit -r src/ -ll -x src/services/debug/ --quiet
```

### Compile check
```bash
python -m py_compile src/database.py src/api_server.py src/main.py
```

### Run locally
```bash
# Requires .env file with credentials
python src/main.py
```

## Project Structure

```
src/
  main.py                   # Entry point — wires all agents and starts Telegram client
  settings.py               # Pydantic settings (reads from env / .env)
  database.py               # Turso/SQLite singleton
  database_pool.py          # Connection pool with SmartRow adapter
  api_server.py             # FastAPI: /api/system/health, /traces, /runtime
  controllers/
    message_controller.py   # Routes incoming Telegram messages to agents
  services/
    core/                   # Production agents and services
      agent_loop.py         # Planner → Executor → Verifier cycle
      agent_policy.py       # Guardrails: quiet-hours, approval gates, auto_actions
      agent_verifier.py     # Post-action verification
      agent_brain.py        # LLM reasoning layer
      tool_registry.py      # Standardised ToolResult schema
      tool_adapters.py      # Telegram / AmoCRM / Airtable adapters
      amocrm_sync.py        # CRM pipeline sync
      enterprise_reporter.py # Daily plan + audit reports
      negotiation_engine.py # Role-specific sales instructions
      lead_scraper.py       # Scrapes CRM for actionable leads
      advisor_agent.py      # Gemini-powered conversation advisor
      auto_lead_agent.py    # Autonomous lead handling
      audit_agent.py        # Internal team audit
    ai/                     # AI model wrappers
    utils/                  # Scouter, voice processor, access manager
    debug/                  # ~90 one-off diagnostic scripts (NOT production)
tests/
  test_api_server_security.py
  test_ai.py
  test_crm_db.py
  test_genai_config.py
  test_lead_progression.py
  test_profile_status.py
docs/
  AGENT_ROADMAP.md          # 6-phase roadmap for agent maturity
  IDEAL_AI_AGENT.md         # Target architecture: Negotiator / SalesAgent / DealLifecycle
  GSTACK_REVIEW.md          # Review of garrytan/gstack patterns
```

## Architecture

### Agent Loop (Phase 3+)
```
Task → Planner (Gemini) → Executor (tool_adapters) → Verifier → audit log
```

### Key Agents
| Agent | File | Role |
|---|---|---|
| MessageController | controllers/message_controller.py | Routes Telegram events |
| AdvisorAgent | services/core/advisor_agent.py | Real-time sales coaching |
| AutoLeadAgent | services/core/auto_lead_agent.py | Autonomous lead actions |
| AuditAgent | services/core/audit_agent.py | Team performance audit |
| EnterpriseReporter | services/core/enterprise_reporter.py | Daily reports |

### Dual Runtime
- **Cloud Run** — primary API + bot, stateless, reads secrets from Cloud Secret Manager
- **VM** — legacy userbot (Telethon), quiet-hours enforced via `agent_policy.py`

### Database
- Primary: Turso (`TURSO_DATABASE_URL`) for cloud runs
- Fallback: SQLite `data/bot.db` for local development
- Schema: leads, daily_plans, job_traces, agent_state

## Environment Variables

Required (set in Cloud Secret Manager or `.env`):
```
BOT_TOKEN              Telegram bot token
API_ID / API_HASH      Telegram app credentials
GEMINI_API_KEY         Google Gemini
AMOCRM_SUBDOMAIN       AmoCRM account
AMOCRM_CLIENT_ID       AmoCRM OAuth
AMOCRM_CLIENT_SECRET   AmoCRM OAuth
TURSO_DATABASE_URL     Turso DB URL
TURSO_AUTH_TOKEN       Turso auth
```

Optional:
```
AIRTABLE_API_KEY       Airtable sync
GSHEET_ID              Google Sheets
ADMIN_BOT_TOKEN        Separate admin bot
DEEPSEEK_API_KEY       Fallback LLM
ENABLE_AUTO_REPLY      Enable autonomous replies (default: false)
OWNER_ID               Telegram user ID of owner
```

## CI/CD

- **CI:** GitHub Actions (`.github/workflows/deploy.yml`)
- **Trigger:** push to `main` — runs pytest + bandit + py_compile
- **Deploy:** Google Cloud Build → Cloud Run (tag: `europe-west3`)
- **Skip CI:** commit message containing `[skip ci]` or starting with `chore(auto): update DEV_LOG`

## Guardrails

- `agent_policy.py` — blocks actions during quiet-hours (23:00–07:00 Tashkent), requires approval for destructive CRM actions
- `auto_reply_gate.py` — gates autonomous Telegram replies behind `ENABLE_AUTO_REPLY`
- `WHITELIST_IDS` — only whitelisted Telegram IDs receive full agent capabilities
- `src/services/debug/` — excluded from bandit scan and should NEVER be imported in production

## TypeScript Monorepo (SalesCoach AI)

The project also contains a TypeScript monorepo for the SalesCoach AI product:

### Workspace Config
- **Package manager:** pnpm 10.33.2
- **Build system:** Turborepo 2.9.10
- **TypeScript:** 6.0.3

### Apps (`apps/`)
| App | Stack | Purpose |
|-----|-------|---------|
| @salescoach/api | NestJS 11 | REST API backend |
| @salescoach/web | Next.js 16 + React 19 | Dashboard frontend |
| @salescoach/worker | BullMQ + ioredis | Async job processing |

### Packages (`packages/`)
| Package | Purpose |
|---------|---------|
| @salescoach/shared-types | Zod schemas, shared types |
| @salescoach/ui | React component library |
| @salescoach/config | ESLint, Prettier, TSConfig |

### Separate workspace: `salescoach-ai/`
Second monorepo with apps (api, bot, web, worker) + packages. Bot app added May 2025.

### TypeScript Commands
```bash
pnpm run build       # Turbo build all
pnpm run dev         # Turbo dev --parallel
pnpm run lint        # Turbo lint
pnpm run test        # Turbo test
pnpm run typecheck   # Turbo typecheck
pnpm run format      # Prettier
```

## Docker & Infrastructure

### docker-compose.yml (dev stack)
- **oisha** — main Python app
- **postgres:16** — SalesCoach DB
- **redis:7** — Cache + BullMQ queue
- **minio** — S3-compatible object storage

### Deployment Targets
| Target | Use |
|--------|-----|
| Google Cloud Run (europe-west3) | Primary production |
| Oracle Cloud Free Tier | Secondary (added May 2025) |
| VPS | Legacy Telethon userbot |
| Fly.io | Stub/legacy |

### GitHub Workflows
- `deploy.yml` — Main CI/CD (pytest + bandit + py_compile → Docker → Cloud Run)
- `oracle-deploy.yml` — Oracle Cloud deployment
- `userbot-vps.yml` — VPS userbot deployment
- `codeql.yml` — Security scanning
- `test.yml` — pytest
- `juma-greeting.yml` — Scheduled Juma greetings

## AI Providers

| Provider | Use | Config |
|----------|-----|--------|
| Google Gemini 1.5 Flash | Fast responses | `GEMINI_API_KEY` |
| Google Gemini 1.5 Pro | Complex reasoning | `GEMINI_API_KEY` |
| AWS Bedrock (Claude) | Fallback (added May 2025) | AWS credentials |
| Anthropic SDK | Direct Claude API | `ANTHROPIC_API_KEY` |
| OpenAI | Fallback | `OPENAI_API_KEY` |

## Development Notes

- All new agents should use `tool_registry.ToolResult` for standardised output
- Gemini calls should specify model explicitly (`gemini-1.5-flash` for speed, `gemini-1.5-pro` for complex reasoning)
- Database writes must go through `database_pool.py` — never open raw connections
- Quiet-hours and approval gates must not be bypassed for CRM or Telegram actions
- `src/services/debug/` scripts are diagnostic one-offs — treat as read-only, never call from production code
- TypeScript monorepo uses pnpm workspaces — always use `pnpm` not `npm`
- Two separate workspaces exist: root `apps/` and `salescoach-ai/` — avoid confusion between them
