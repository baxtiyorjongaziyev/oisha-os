# Oisha-OS Agent Coordination Protocol

> Bu fayl — **xarita**, ensiklopediya emas (~100 qator). Batafsil ma'lumot `docs/agents/` da.
> Barcha AI agentlar (Claude, Codex, Gemini, Jules, Antigravity) ish boshlashdan oldin shu faylni
> o'qiydi. Bu faylni 150 qatordan oshirmang — tarix va tafsilot `docs/agents/` ga yoziladi.

## Qayerda nima bor

| Mavzu | Fayl |
|---|---|
| Loyiha, stack, buyruqlar, arxitektura | `CLAUDE.md` |
| Kod standartlari (400 qator, facade, funksiya hajmi) | `docs/agents/code-standards.md` |
| Oltin tamoyillar (agent uchun mexanik qoidalar) | `docs/agents/golden-principles.md` |
| Joriy holat, operatsion eslatmalar, refactor tarixi | `docs/agents/state-and-history.md` |
| Agent handoff jurnali (tarix + yangi yozuvlar) | `docs/agents/handoff-log.md` |
| Avtonom dev loop (Ralph) | `scripts/ralph/` |
| Deploy | `DEPLOYMENT.md`, `deploy/` |
| Xavfsizlik | `SECURITY.md`, `docs/security/` |
| Eski hisobot va handofflar | `docs/archive/` |

## Asosiy qoidalar

1. **Bir faylga bir vaqtda bitta agent yozadi.** Ish boshida `## Locks` ga yoziladi, tugagach o'chiriladi.
2. **Shared fayllar** (`settings.py`, `context.py`, `boot.py`, shu `AGENTS.md`) — faqat Coordinator.
3. **Pre-flight har PR dan oldin** (pastga qarang). Qizil bo'lsa — PR yo'q.
4. **git:** commit → push → keyingi agent `pull --rebase`. `main` ga to'g'ridan-to'g'ri push yo'q.
5. **Kod hajmi:** production fayl ≤ 400 qator, funksiya ≤ 60 qator → `docs/agents/code-standards.md`.
6. **Handoff majburiy:** ish tugagach `docs/agents/handoff-log.md` OXIRIGA yozing:
   sana/agent, bajarilgan ish, o'zgargan fayllar, tekshiruv dalili, qolgan ish/bloker.
7. **Airtable o'zgarishi** → darhol Obsidian `20-Areas/Airtable_Operatsion_Tizimi_va_Ozgarishlar.md`
   va `brain_log` ga muhrlanadi (Owner qoidasi, 2026-09-15).
8. **Sirlar hech qayerga yozilmaydi:** token, parol, session string, API key.

## Xavfli zonalar (hook bilan bloklangan — `.claude/hooks/guard.py`)

- ⚠️ **Userbot sessiyasi Oracle VM'ga tegishli.** Lokal `src/main.py` / userbot ishga tushirish →
  prod sessiya `AuthKeyDuplicatedError` bilan o'ladi. `ALLOW_LOCAL_RUN=0`.
- `.env`, session fayllar, sirlarni o'qish/yozish taqiqlanadi.
- `git push --force`, `main` ga push, `git reset --hard`, `rm -rf` — bloklangan.
- Telegram MCP portlari (8765/8766) public qilinmaydi; mutatsiyalar faqat owner tasdig'i bilan.
- `src/services/debug/` production'da import qilinmaydi.

## Dead Files (tegmang)

`src/services/debug/`, `src/legacy/`, `src/agents/` ichki qismlari (refactor scope'dan tashqari).

## Roles

| Agent | Scope | Owner |
|-------|-------|-------|
| **Coordinator** | AGENTS.md, settings.py, context.py, boot.py, PR merge | @user |
| **Parser** | main.py → handlers/, commands/, schedulers/ | — |
| **Hisobchi** | finance engine / handlers / schema | — |
| **Security** | tests/, bandit issues, exception handling | — |
| **Migration** | global variable → app_ctx.* | — |
| **Database** | database.py, migrations, SQL optimization | — |
| **API Server** | api_server.py, endpoints, auth | — |
| **Integration** | AmoCRM, Airtable, Telegram integrations | — |
| **Documentation** | README, API docs, inline docs | — |
| **Performance** | profiling, caching, optimization | — |
| **Code Quality** | dead code, naming, type hints | — |

## Locks



> Faqat **faol** qulflar. Bo'shatilgan qulf o'chiriladi (tarix → handoff-log).

- Codex Coordinator: leadgen delivery recovery modules and focused tests (2026-09-15).
- Codex Coordinator: client journey, SalesCoach writer, Telegram task creator, dependency contracts.

## Pre-flight Checklist (har bir PR dan oldin)

```powershell
$env:SKIP_LIVE=1; python -m pytest -q --tb=short
bandit -r src/ -ll
```

## Branch & Commit

- Branch: `feat/<short-description>` yoki `fix/<short-description>`
- Commit: `feat(scope): message` / `fix(scope): message` / `refactor(scope): message`
- Avtonom loop commitlari oxirida `[ralph]` bo'ladi.

## VS Code: uch agent

Ish boshida `AGENTS.md`, `docs/oisha-prd.md` va `docs/agents/three-agent-workflow.md` ni o'qing. Bir checkoutda bitta implementer yozadi; reviewer va analyst shu fayllarga yozmaydi.
