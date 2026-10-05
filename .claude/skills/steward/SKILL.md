---
name: steward
description: Drive an Oisha-OS pull request to green and mergeable — handle CI failures, merge conflicts and review comments with this repo's conventions. Use when babysitting/stewarding a PR, on a CI-failure or review event, or when asked to "get this PR green".
---

# PR Steward (Oisha-OS)

Maqsad: PR **yashil CI + konfliktsiz + review'lar javoblangan** holatga kelsin.
Har bir hodisada (CI, review, konflikt) butun PR'ga qarang va hamma ochiq ishni yoping.

## Tartib

Har safar shu tartibda ishlang: **konflikt → CI → review**.

### 1. Merge konflikt

```bash
git fetch origin main
git merge origin/main          # rebase EMAS — merge commit boshqalarning checkout'ini buzmaydi
```

- Lockfile'lar (`pnpm-lock.yaml`) qo'lda tahrirlanmaydi — `pnpm install` bilan qayta yarating.
- Ikkala tomon bir xil mantiqni o'zgartirgan bo'lsa va biri yo'qolsa — Owner'dan so'rang.
- Force push, `git reset --hard`, `main` ga push — `.claude/hooks/guard.py` bloklaydi. Chetlab o'tmang.

### 2. CI qizil

CI: `.github/workflows/test.yml` (PR'larda GitHub-hosted runner, Python 3.12).
Qadamlar: `ruff --select F821` → `bandit` → `pytest` (+ o'zgargan TS workspace'lar).

1. Muvaffaqiyatsiz job log'ini o'qing va xatoni **lokal takrorlang** (`preflight` skill).
2. Bu PR'ning xatosimi? `main` da ham qizil bo'lsa yoki diff tegmagan servis xatosi bo'lsa —
   PR'ga bitta izoh: qaysi check, nega bu PR'niki emas, tuzatish bormi.
   `main` uchun tuzatish mavjud bo'lsa — shu PR'ga ko'chiring.
3. PR'niki bo'lsa — ildiz sababini tuzating, `preflight` ni yashil qiling, keyin push.
4. "Flake" ildiz sabab emas. Qayta ishga tushirish ko'pi bilan bir marta; ikkinchi qizil — haqiqiy.

**Taqiqlangan:** testni o'chirish / `skip` / `xfail` / karantin; bo'sh commit; PR'ni yopib-ochish.

Repo-spetsifik eslatmalar:
- Testlar `SKIP_LIVE=1` bilan ishlaydi — live API'ga uriladigan yangi test `SKIP_LIVE` bilan himoyalanishi shart.
- `oracle-deploy.yml` faqat `main` ga merge'dan keyin ishlaydi; PR'da deploy xatosi kutilmaydi.
- `chore(auto):` yoki `[skip ci]` commit'lari CI'ni o'tkazib yuboradi — tuzatish commit'larida ishlatmang.

### 3. Review izohlari

- Kichik, lokal so'rovlar (nit, nom, test qo'shish, bitta funksiya refactor) → bajaring, push qiling.
- Katta so'rovlar (ko'p faylli refactor, API/schema o'zgarishi, shared fayllar) → taklif bilan javob bering,
  push qilmang; Owner (@user, Coordinator) hal qiladi.
- Bot topilmalari (CodeQL, gitleaks, bandit, Claude Code Review 🔴) — bug report sifatida tekshiring va tuzating.
  🟡 / "optional" / "nit" topilmalari push'ni boshlamaydi: bir qatorda javob bering, keyingi push'ga qo'shing.
- Tuzatilgan thread'larni resolve qiling.

## Push'dan oldin

1. `preflight` skill'ini ishga tushiring — hammasi ✅ bo'lishi shart.
2. Diff minimal: faqat xato yoki izoh talab qilgan narsa. PR scope'ini o'zboshimchalik bilan kengaytirmang.
3. Commit uslubi: `fix(scope): message` / `feat(scope): …` / `refactor(scope): …`.
4. `git push -u origin <branch>` (force yo'q).

## PR tayyor bo'lganda

- CI yashil, konflikt yo'q, ochiq review thread yo'q → "reviewer kutilmoqda" deb bir marta ayting.
- `AGENTS.md` → `## Locks` dan o'z qulfingizni o'chiring.
- `docs/agents/handoff-log.md` OXIRIGA yozing: sana/agent, bajarilgan ish, o'zgargan fayllar,
  tekshiruv dalili, qolgan ish/bloker (AGENTS.md qoida 6).

## Hech qachon

- Approve yoki merge qilmang — bu Owner'ning ishi.
- Boshqa birovning branch tarixini qayta yozmang (rebase/amend/force-push).
- Sirlarni (token, session string, API key) commit, izoh yoki log'ga yozmang.
