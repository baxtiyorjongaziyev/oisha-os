---
name: uzbek-text
description: O'zbekcha matnda ASCII apostrof (`qo'ng'iroq`, `ma'no`) xatosini oldini oluvchi guard. Yangi lotin alifbosi (2026) qoidalari, baseline/ratchet, pre-commit va CI bilan ishlash.
---

# O'zbekcha matn va apostrof skill

## Muammo

Python'da `'...'` va `"..."` ikkala tirnoq bir xil kuchga ega. O'zbekcha matnda `oʻ`/`gʻ` oldin oddiy `'` bilan terilgan:

```python
matn = 'qo'ng'iroq'   # SyntaxError: "qo" da string tugadi
matn = "qo'ng'iroq"   # kod ishlaydi, lekin matn noto'g'ri, keyingi tahrirda buzadi
```

Yangi (2026) alifbo `ö ğ ş ç` va tutuq belgisi `ʼ` (U+02BC) bilan ishlatilganda ham `maʼno`, `eʼlon`, `taʼtil` kabi so'zlarda tutuq belgisi qoladi. Uni ASCII `'` bilan yozish xuddi shu SyntaxError'ga olib keladi.

## Qoidalar

1. **O'zbekcha matn faqat ikki tirnoq ichida:** `"qo'ng'iroq"`, `"qönğiroq"`.
2. **ASCII `'` so'z ichida taqiqlanadi:** `'qo'ng'iroq'` → SyntaxError; `"qo'ng'iroq"` → keyingi tahrirda kodni buzadi.
3. **Tutuq belgisi:** `ʼ` (U+02BC), masalan `maʼno`, `eʼlon`, `taʼtil`.
4. **Harflar:** `oʻ`/`gʻ` → `ö`/`ğ` (yangi alifbo) yoki `ʻ` (U+02BB); `sh` → `ş`, `ch` → `ç`.
5. **Identifikator, email, teg, username:** ASCII, ularga tegilmaydi (`shahnoza@jonbranding.uz`, `menejer:`).
6. **Inglizcha qisqartmalar istisno:** `don't`, `we're`, `John's`, `o'clock` — guard ularni xato deb hisoblamaydi.

## Tekshiruv

```bash
python scripts/check_uzbek_text.py --staged              # commit dan oldin (faqat staged qatorlar)
python scripts/check_uzbek_text.py --base origin/main    # PR diff (yangi qatorlar)
python scripts/check_uzbek_text.py --all --baseline config/uzbek_text_baseline.txt   # butun repo, ratchet
```

## Baseline (ratchet)

Repo'da 7000+ eski xato bor. Ular `config/uzbek_text_baseline.txt` da fayl bo'yicha qulflangan:

- **Yangi xato** qo'shilsa yoki yangi fayl paydo bo'lsa — CI qizil.
- **Qarz tuzatilganda** baseline qayta yoziladi (son faqat kamayadi):

```bash
python scripts/check_uzbek_text.py --write-baseline
```

Baseline faqat `--all` va aniq fayl rejimida qo'llanadi; `--staged`/`--base` diff rejimida har bir qo'shilgan qator tekshiriladi.

## Avtomatik himoya

| Qatlam | Joy | Vazifa |
|---|---|---|
| Pre-commit hook | `.githooks/pre-commit` | staged qatorlarni tekshiradi |
| Makefile | `make hooks`, `make uzbek-text` | hookni o'rnatish / qo'lda tekshirish |
| CI | `.github/workflows/uzbek-text-guard.yml` | PR diff + main push ratchet |
| Testlar | `tests/test_check_uzbek_text.py` | aniqlash va baseline mantiqi |
| Agent qoidasi | `AGENTS.md` #12, `CLAUDE.md` Guardrails | barcha AI agentlar o'qiydi |

Hookni bir marta o'rnatish:

```bash
make hooks   # git config core.hooksPath .githooks
```

## Barcha agentlar

Claude, Codex, Gemini, Jules, Antigravity ish boshlashdan oldin `AGENTS.md` va `CLAUDE.md` dagi qoidani o'qiydi. Yangi o'zbekcha matn yozganda shu skillga amal qilinadi.
