---
name: uzbek-text
description: O'zbekcha matn va apostrof kodiqni tekshiruvchi guard skill. Yangi lotin alifbosi (2026) bo'yicha o'zbekcha xatlarni xavfsiz yozishga intiladi.
---

# Oʻzbekcha matn va apostrof skill

## Muammo

Python'da `'...'` va `"..."` ikkala tirnoq bir xil kuchga ega. O'zbekcha matnda `oʻ`/`gʻ` oldin oddiy `'` bilan terilgan:

```python
matn = 'qo'ng'iroq'   # SyntaxError: "qo" da string tugadi
matn = "qo'ng'iroq"   # kod ishlaydi, lekin matn noto'g'ri, keyingi tahrirda buzadi
```

Yangi (2026) alifbo `ö ğ ş ç` va tutuq belgisi `ʼ` (U+02BC) bilan sho'ng'ladiganida ham, `maʼno`, `eʼlon`, `taʼtil` kabi so'zlarda tutuq belgisi qoladi. Agar uni ASCII `'` bilan yozilsa — xuddi shu SyntaxError qaytadi.

## Qoidalar (qa'da)

1. **O'zbekcha matn faqat ikki tirnoq ichida:** `"qo'ng'iroq"`, `"qönğiroq"`.
2. **ASCII `'` so'z ichida taqiqlanadi:** `'qo'ng'iroq'` → SyntaxError; `"qo'ng'iroq"` → keyingi tahrirda kodni buzadi.
3. **Tutuq belgisi:** `ʼ` (U+02BC), `'` maslan `maʼno`, `eʼlon`.
4. **Harflar:** `oʻ`/`gʻ` → `ö`/`ğ` (yangi alifbo) yoki `ʻ` (U+02BB); `sh` → `ş`, `ch` → `ç`.
5. **Identifikator, email, teg, username:** ASCII, ularga tegilmaydi (`shahnoza@jonbranding.uz`, `menejer:`).

## Tekshiruv

```bash
python scripts/check_uzbek_text.py --staged   # commit dan oldin
python scripts/check_uzbek_text.py --base origin/main   # PR diff bo'yicha
python scripts/check_uzbek_text.py --all   # butun repo (mavjud qarzlarni ko'rsatadi)
```

## Rost agentlar

Barcha AI agentlar (Claude, Codex, Gemini, Jules, Antigravity) ish boshlashdan oldin `AGENTS.md` va `CLAUDE.md` ga yozilgan bu qoidani o'qishi majburiy.
