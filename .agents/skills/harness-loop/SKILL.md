---
name: harness-loop
description: Oisha-OS da har bir kod ishi (feature, fix, refactor) uchun majburiy sikl — reja, branch, gate'lar, PR, CI va review loop, merge, merge'dan keyingi tekshiruv. Kod yozish, PR ochish, push qilish yoki merge qilishdan oldin ishlating.
---

# Harness Loop (Oisha-OS)

> Maqsad: ish hech qachon "yarim" qolmasin va hech qachon yoʻqolmasin.
> Har bir bosqichning **gate**i bor: gate oʻtmaguncha keyingisiga oʻtilmaydi.
> Sabab boʻlgan hodisa: 2026-11-19, PR #1099 merge boʻlgandan keyin push qilingan
> commit `main` ga tushmay qoldi (keyin PR #1101 bilan qoʻlda tiklandi).

## Sikl

```
0 Sync → 1 Reja → 2 Branch → 3 Bajarish → 4 Gate → 5 PR → 6 CI/Review loop → 7 Merge → 8 Post-merge → 9 Handoff
                              ↑______________ gate qizil ______________|
```

### 0. Sync
- `git fetch origin main`; `AGENTS.md` dagi `## Locks` va `docs/agents/handoff-log.md` oxirini oʻqing.
- **Gate:** kerakli fayllar boshqa agent qulfida emas.

### 1. Reja
- Ishni 3–7 ta tekshiriladigan qadamga boʻling; har biri uchun "tayyor" mezonini yozing.
- **Gate:** har bir qadamning tekshiruvi aniq (test nomi, buyruq yoki URL).

### 2. Branch
- Har doim **yangi** branch, `origin/main` dan: `git switch -c feat/<nom> origin/main`.
- **Gate:** branchda ochiq PR yoki merge boʻlgan PR yoʻq.

### 3. Bajarish
- Kichik commitlar, `feat(scope): …` / `fix(scope): …`. Fayl ≤ 400 qator, funksiya ≤ 60.
- Har bir yangi xatti-harakat uchun test (avval qizil, keyin yashil).

### 4. Gate (har push dan oldin)
```bash
SKIP_LIVE=1 python -m pytest -q --tb=short
bandit -r src/ -ll
ruff check --select F821,F822,ASYNC210,ASYNC221 --per-file-ignores "src/config.py:F822" src/
python scripts/check_uzbek_text.py --base origin/main
```
- **Gate:** hammasi yashil (`AGENTS.md` 3-qoida). `main` dan meros qizil test boʻlsa — avval uni
  alohida PR da tuzating (yoki shu PR da, sababini PR body da yozib); qizil holatda PR ochilmaydi.

### 5. PR
- `.github/pull_request_template.md` boʻyicha; "Tekshiruv" da faqat haqiqatan bajarilganini belgilang.
- **Gate:** PR body da tekshirilmagan narsa "TEKSHIRILMAGAN" deb yozilgan.

### 6. CI / Review loop
- Yiqilgan check → log oʻqing (`gh run view <id> --log-failed`) → sabab sizdanmi yoki `main` danmi aniqlang.
- Review sharhi → tuzating → thread ga bir qatorli javob → resolve.
- **Har push dan oldin PR holatini tekshiring:**
  ```bash
  gh pr view --json state -q .state   # MERGED yoki CLOSED bo'lsa — PUSH QILMANG
  ```
  `MERGED` boʻlsa: `git switch -c feat/<nom>-followup origin/main && git cherry-pick <sha>` va yangi PR.
- **Gate:** barcha check yashil, ochiq thread yoʻq.

### 7. Merge
- Faqat **oxirgi commit** CI dan oʻtgan boʻlsa: `gh pr view --json headRefOid,statusCheckRollup`.
- Merge dan oldin branchga push davom etmayotganiga ishonch hosil qiling (agent hali ishlayotgan boʻlsa — kuting).

### 8. Post-merge
- `main` dagi CI va deploy (`oracle-deploy.yml`, `/readyz`) natijasini tekshiring.
- Merge boʻlgan branchga keyin commit tushsa, `.github/workflows/followup-pr.yml` avtomatik
  `followup/<branch>-<sha>` PR ochadi (konflikt boʻlsa eski PR ga izoh qoldiradi). Uni koʻrib chiqing.
- **Gate:** ish `main` da va prod da (yoki "deploy qilinmagan" deb ochiq yozilgan).

### 9. Handoff
- `docs/agents/handoff-log.md` oxiriga: nima qilindi, fayllar, dalil, qolgan ish.
- Takrorlanadigan yangi saboq boʻlsa — tegishli skillni yangilang (`skill-evolution`).

## Avtomatlashtirilgan qismlar

| Nima | Qayerda |
|---|---|
| Merge dan keyingi commitlar uchun follow-up PR | `.github/workflows/followup-pr.yml` → `scripts/followup_pr.py` |
| Oʻzbekcha matn guard | `oracle-deploy.yml` (PR), `uzbek-text-guard.yml` |
| CI testlar, bandit | `test.yml` |
| Deploy + `/readyz` | `oracle-deploy.yml` |

**Eslatma:** `GITHUB_TOKEN` bilan ochilgan PR CI ni ishga tushirmaydi. Follow-up PR larda CI ham
ishlashi uchun repo secretlariga `AUTOMATION_PAT` (fine-grained, faqat shu repo: contents +
pull requests write) qoʻshing — Owner bosadi.
