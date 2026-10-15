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
| Telegram networking lidlarini CRM/Obsidianga sinxronlash | `.agents/skills/community-lead-sync/SKILL.md` |
| Telegram tanishtiruv guruhlari va networking manbalarini kashf qilish | `.agents/skills/telegram-lead-discovery/SKILL.md` |
| O'zbekiston soliq hisobotlari (JShDS 11101_20, Aylanma 10104_36) | `.agents/skills/soliq-ops/SKILL.md` |

## Asosiy qoidalar

1. **Bir faylga bir vaqtda bitta agent yozadi.** Ish boshida `## Locks
` ga yoziladi, tugagach o'chiriladi.
2. **Shared fayllar** (`settings.py`, `context.py`, `boot.py`, shu `AGENTS.md`) — faqat Coordinator.
3. **Pre-flight har PR dan oldin** (pastga qarang). Qizil bo'lsa — PR yo'q.
4. **git:** commit → push → keyingi agent `pull --rebase`. `main` ga to'g'ridan-to'g'ri push yo'q.
5. **Kod hajmi:** production fayl ≤ 400 qator, funksiya ≤ 60 qator → `docs/agents/code-standards.md`.
6. **Handoff majburiy:** ish tugagach `docs/agents/handoff-log.md` OXIRIGA yozing:
   sana/agent, bajarilgan ish, o'zgargan fayllar, tekshiruv dalili, qolgan ish/bloker.
7. **Airtable o'zgarishi** → darhol Obsidian `20-Areas/Airtable_Operatsion_Tizimi_va_Ozgarishlar.md`
   va `brain_log` ga muhrlanadi (Owner qoidasi, 2026-09-15).
8. **Sirlar hech qayerga yozilmaydi:** token, parol, session string, API key.
9. **Umumiy skills:** Codex, Claude va Antigravity barcha takrorlanadigan ishlar uchun `.agents/skills/skill-evolution/SKILL.md` qoidasiga amal qiladi. Masalan, Telegram guruh va forumlaridan lidlarni olish va amoCRM ga dublikatsiz boyitish uchun `.agents/skills/community-lead-sync/SKILL.md`, yangi networking manbalari va tanishtiruv mavzularini avtomatik qidirish uchun `.agents/skills/telegram-lead-discovery/SKILL.md` hamda oylik soliq hisobotlari (JShDS 11101_20 va Aylanma 10104_36) uchun `.agents/skills/soliq-ops/SKILL.md` ishlatiladi. Mos skill mavjud bo‘lsa, ish boshlashdan oldin o‘qiydi; yangi tasdiqlangan workflow paydo bo‘lsa, ish tugagach umumiy `.agents/skills/<skill>/SKILL.md` ni yangilaydi.

10. **Soxta ma'lumot taqiqlanadi (owner, 2026-10-10):** chat, Obsidian, skills, kod, jadval, hisobot va tashqi tizimlarda uydirma ma'lumotni haqiqiy fakt sifatida yozmang. Yetishmagan qiymatni taxminiy raqam yoki nol bilan to'ldirmang; `noma'lum` yoki `tekshirilmagan` deb belgilang. Faktga manba va kerak bo'lsa sanani qo'shing; taxminni aniq ajrating. Bajarilmagan ishni `bajarildi`, yuborilmagan hisobotni `topshirildi`, tasdiqlanmagan to'lovni `to'landi` demang. Xato aniqlansa, manbasi bilan ochiq tuzatish kiriting. Sintetik test ma'lumotlari aniq belgilansin va haqiqiy operatsion yozuvlarga aralashmasin.
11. **Owner bosadigan tugmalar:** autentifikatsiya, xavfsizlik ruxsati yoki ownerning shaxsiy ishtiroki zarur bo'lsa, sahifa va tugma nomini aniq ayting; Baxtiyorjon o'zi bosadi. Uning bosganini yoki natijani taxmin qilmang — yangi holatni tekshiring. Oldindan ruxsat berilgan oddiy ishlar uchun qayta tasdiq so'ramang.

## Dalil va tekshiruv (owner, 2026-10-10)

- Muhim fakt va raqam uchun tekshirilgan manba, davr, birlik va tekshiruv sanasini saqlang. Havola, hujjat raqami, iqtibos yoki tool natijasini uydirmang; ochilmagan manbani o'qilgan demang.
- `Manbadan tekshirilgan`, `owner aytgan`, `hisoblangan`, `taxmin` va `noma'lum`ni ajrating. Owner aytgan ma'lumotni hujjatdan tasdiqlangan deb ko'rsatmang.
- Eski chat, xotira, Obsidian yoki boshqa AI javobi joriy holat isboti emas. O'zgaruvchan holatni vakolatli manbadan qayta tekshiring; kirish bo'lmasa, sana va cheklovni ayting.
- Manbalar zid bo'lsa, farqni yozing va asl hujjat bilan yarashtiring. Hal qilinmagan muhim tafovutga tayangan hisobot yoki to'lovni yubormang; mustaqil ishlarni davom ettiring.
- Muhim moliyaviy hisobni kalkulyator yoki kod bilan hisoblang; kiruvchi qiymatlar, formula, davr, valyuta va yaxlitlashni qayd qiling. Jami va tarkibni alohida solishtiring. To'g'ri arifmetika manbaning to'g'riligini isbotlamaydi.
- Har tashqi amaldan keyin holatni qayta o'qing. Bosilgan tugma, yuborish urinishlari yoki tayyor fayl muvaffaqiyat isboti emas; qabul raqami, yakuniy status yoki amaldagi natija kerak. Natija noaniq bo'lsa, takroriy yuborishdan oldin mavjud yozuvni tekshiring.
- Yakuniy javobda bajarilgan, qisman va ochiq ishlarni dalilga mos ayting. Tekshiruv qamrovini oshirib ko'rsatmang; qisman tekshiruvdan 'barcha muammo hal' xulosasini chiqarmang.
- Xato topilsa, oldingi da'voni aniq tuzating va undan kelib chiqqan qayd, hisob yoki skillni tekshiring. Xatoni yangi tasdiqlanmagan da'vo bilan almashtirmang.
- Qoidaning faylga yozilishi boshqa agentlar uni o'qigani yoki galutsinatsiya butunlay yo'qolgani isboti emas. Boshqa agent fikri mustaqil birlamchi dalil hisoblanmaydi.

## Xavfli zonalar (hook bilan bloklangan — `.claude/hooks/guard.py`)

- ⚠️ **Userbot sessiyasi Contabo VPS'ga tegishli (109.199.100.137).** (Eski Oracle VM to'xtatildi). Lokal `src/main.py` / userbot ishga tushirish →
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
- Codex: prospect discovery modules, admin command hook, channel scout scheduler hook, focused tests (2026-10-13).
 





> Faqat **faol** qulflar. Bo'shatilgan qulf o'chiriladi (tarix → handoff-log).

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
