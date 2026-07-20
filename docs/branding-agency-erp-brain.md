# Oisha Branding Agency ERP Brain

## Positioning

Oisha is not a monolithic ERP. Oisha is the 24/7 integration brain for a
branding agency. Free or low-cost external platforms remain the source of
truth; Oisha reads them, reasons over them, requests approval, writes back, and
verifies the result.

## Source Of Truth Map

| Area | Primary platform | Oisha role |
|---|---|---|
| Sales pipeline | AmoCRM | Prioritize leads, plan follow-ups, create approved tasks/notes |
| Client files | Google Drive | Link brief, KP, brandbook, feedback, assets |
| Project status | Airtable or Google Sheets | Detect deadline risk, owner gaps, blocked stages |
| Meetings | Google Calendar | Create approved meetings and reminders |
| Finance | Hisobchi + Google Sheets | Track advance, debt, cost, margin, payment alerts |
| Approvals | Telegram bot | Ask owner before mutations and store audit trail |
| Conversation evidence | Telethon userbot | Read allowed Telegram history on Oracle VM only |
| Automation | n8n | Run workflow glue that does not belong in core code |
| AI access | MCP gateways | Let agents inspect and act through approved tools |

## Runtime Rules

1. Production must run 24/7 on Oracle VM or another server runtime.
2. Local machine is only for coding and tests; it must not own the userbot
   session.
3. Telethon userbot stays on Telethon.
4. The bot-account head (`BOT_TOKEN`, @jonairobot) migrates to Aiogram in
   phases through a compatibility adapter.
5. Oisha never invents business data. Missing source means a clear
   `source_unavailable` style answer.
6. Any external mutation needs owner approval unless the policy explicitly marks
   it safe.
7. Every important answer should include source, timestamp, and evidence link or
   record id when available.

## Read-Only Control Endpoints

All endpoints require `Authorization: Bearer <OISHA_API_SECRET>` and must never
return secret values.

| Endpoint | Purpose |
|---|---|
| `GET /api/oisha/integrations` | Shows configured integration capability counts without exposing tokens |
| `GET /api/oisha/erp/roadmap` | Shows the branding-agency ERP phases and acceptance checks |
| `GET /api/oisha/telegram/migration` | Shows Telethon userbot / Aiogram bot-head migration stage, rollback path, and unsafe order checks |
| `GET /api/oisha/sales/today-priorities` | Ranks open AmoCRM leads for today's seller outreach without inventing missing facts |
| `GET /api/oisha/projects/risks` | Ranks Airtable/project-source deadline, PM, stage, and handoff risks |
| `GET /api/oisha/finance/risks` | Ranks project payment, advance, remaining balance, and missing finance-field risks without guessing margin |
| `GET /api/oisha/team/capacity` | Shows team/PM workload from active project assignments without guessing availability |
| `GET /api/oisha/command-center` | Aggregates sales, project, finance, and team signals into one owner cockpit while preserving source status |
| `POST /api/oisha/command/plan` | Classifies a business command into read-only or owner-approved mutation plan |

Telegram admin commands:

- `/sales_today`, `/bugun_sotuv`, `/kimga_qongiroq`
- `/project_risks`, `/loyiha_risk`, `/deadline_risk`
- `/finance_risks`, `/moliya_risk`, `/pul_risk`
- `/team_capacity`, `/jamoa_yuklama`, `/bandlik`
- `/command_center`, `/oisha_center`, `/biznes_markaz`

Server digest:

- `OISHA_COMMAND_CENTER_DIGEST_ENABLED=true`
- `OISHA_COMMAND_CENTER_DIGEST_HOUR=9`
- `OISHA_COMMAND_CENTER_DIGEST_MINUTE=5`
- Delivery goes through the bot-account runtime, never the Telethon userbot.

## Implementation Phases

1. Stabilize 24/7 runtime: `/healthz`, `/readyz`, systemd active, userbot
   authorized, bot token can send, n8n active.
2. Lock AmoCRM sales discipline: stages, tasks, lead owners, reactivation, no
   automatic Lost/delete for open leads.
3. Connect delivery board: brief, KP, deadlines, files, project owner, feedback.
4. Connect finance: advance, remaining payment, expenses, project margin, debt.
5. Move bot-account head to Aiogram: adapter first, then approvals, admin
   commands, reports, callback flows.
6. Add dashboard/client portal only after source-of-truth integrations are
   stable.

## Acceptance Standard

The system is ERP-grade only when a manager can ask:

- Bugun sotuvchi kimlar bilan gaplashadi?
- Qaysi lead avansga yaqin?
- Qaysi loyiha kechikyapti?
- Qaysi mijozdan pul kelmagan?
- Qaysi jamoa a'zosi band?
- Qaysi task owner/deadlinesiz?

and Oisha answers from live sources, not memory or guesses.
