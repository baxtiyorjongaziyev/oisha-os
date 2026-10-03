---
name: preflight
description: Oisha-OS pre-flight checks to run before every commit/push/PR — mirrors CI (`.github/workflows/test.yml`) so a red PR is caught locally. Use before pushing, before opening a PR, or when asked to "pre-flight", "run checks", or "is it safe to push".
---

# Pre-flight (Oisha-OS)

`AGENTS.md` qoidasi: **pre-flight qizil bo'lsa — PR yo'q.** Bu skill CI bilan bir xil
tekshiruvlarni lokal ishga tushiradi. Hammasi repo ildizidan (`oisha-os/`) ishlatiladi.

## 1. Nima o'zgarganini aniqlang

```bash
git fetch origin main
git diff --name-only origin/main...HEAD
git status --short
```

Qaysi bo'limlar kerakligini shu ro'yxat hal qiladi (pastdagi jadval).

| O'zgargan yo'l | Ishga tushiriladigan bo'lim |
|---|---|
| `src/`, `tests/`, `requirements*.txt`, `pyproject.toml` | 2 (Python) — har doim |
| `apps/`, `packages/`, `package.json`, `pnpm-lock.yaml`, `turbo.json` | 3a (root TS) |
| `salescoach-ai/` | 3b (SalesCoach) |
| `marketing-os/frontend/` | 3c |
| `marketing-os/backend/` | 3d |
| Faqat `docs/`, `*.md`, `.claude/`, `.cursor/` | CI ishlamaydi; 4-bo'limdagi diff tekshiruvi yetarli |

## 2. Python core (CI: `pull-request-tests`)

```bash
ruff check --select F821 src/                       # aniqlanmagan nomlar
bandit -r src/ -ll -x src/services/debug/ --quiet   # CI security gate
SKIP_LIVE=1 python -m pytest -q --tb=short          # live API'larsiz testlar
```

`AGENTS.md` pre-flight'i bandit'ni istisnosiz ham talab qiladi — PR'dan oldin buni ham ishga tushiring:

```bash
bandit -r src/ -ll
```

> `src/services/debug/` dagi topilmalar CI'ni bloklamaydi, lekin yangi topilma qo'shmang.

Tez tekshiruv (bitta modul o'zgarganda, to'liq run'dan oldin):

```bash
python -m py_compile src/main.py src/api_server.py src/database.py
SKIP_LIVE=1 python -m pytest tests/test_<modul>.py -q
```

Vositalar yo'q bo'lsa: `pip install -r requirements.txt -r requirements-dev.txt`.

## 3. TypeScript / boshqa workspace'lar

Ikkita workspace **alohida** — aralashtirmang. Faqat `pnpm`, hech qachon `npm`.

```bash
# 3a. Root (apps/ + packages/)
pnpm install --frozen-lockfile && pnpm run typecheck && pnpm run lint && pnpm run test && pnpm run build

# 3b. salescoach-ai/
(cd salescoach-ai && pnpm install --frozen-lockfile && pnpm run type-check && pnpm run test && pnpm run build)

# 3c. marketing-os/frontend/
(cd marketing-os/frontend && pnpm install --frozen-lockfile --ignore-workspace && pnpm audit --audit-level high --ignore-workspace && pnpm run build)

# 3d. marketing-os/backend/
python -m py_compile marketing-os/backend/main.py marketing-os/backend/db.py
```

## 4. Diff'ni o'zingiz tekshiring

Push'dan oldin `git diff origin/main...HEAD` ni "CI buni nega rad etadi?" ko'zi bilan o'qing:

- **Sirlar:** diff'da token, parol, session string, API key yo'q (gitleaks CI'da ushlaydi).
- **Kod hajmi:** production fayl ≤ 400 qator, funksiya ≤ 60 qator (`docs/agents/code-standards.md`).
- **Taqiqlangan zonalar:** `src/services/debug/` production'ga import qilinmagan; `src/legacy/`,
  `src/agents/` ichki qismlari refactor qilinmagan.
- **Shared fayllar:** `settings.py`, `context.py`, `boot.py`, `AGENTS.md` — faqat Coordinator.
  `AGENTS.md` → `## Locks` da boshqa agent ushlab turgan fayl o'zgarmagan.
- **DB:** yozuvlar `database_pool.py` orqali; raw connection yo'q.
- **Guardrail'lar:** quiet-hours / approval gate / `AUTO_REPLY_MODE` chetlab o'tilmagan.

## 5. Natija

Qisqa hisobot bering — har bir bo'lim uchun ✅ / ❌ va ❌ bo'lsa xato chiqishining asosiy qatori.

- Hammasi ✅ → push qilish mumkin.
- Biror ❌ → **push yo'q**. Sababini toping, tuzating, shu skill'ni qaytadan ishga tushiring.
- Testni o'tkazib yuborish, `skip`/`xfail` qo'shish yoki o'chirib qo'yish bilan "yashil" qilish taqiqlanadi.
- Bo'lim ishga tushmagan bo'lsa (vosita yo'q, tarmoq yo'q) — buni ochiq ayting, "o'tdi" demang.

## Hech qachon

- `python src/main.py` yoki userbot'ni lokal ishga tushirmang (Oracle sessiyasi o'ladi).
- `.env` yoki `*.session` fayllarni o'qimang.
