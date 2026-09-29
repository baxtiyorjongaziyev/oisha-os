# Oisha-OS — To'liq Audit Hisoboti

**Sana:** 2026-05-28
**Auditor:** Claude (Cowork)
**Ko'lam:** Xavfsizlik · Kod sifati · Arxitektura · Testlar · CI/CD
**Repozitoriy:** `oisha-os` (Python ~50,760 satr / 363 `.py` · TypeScript 99 fayl · 644 tracked fayl)

---

## 1. Umumiy xulosa (Executive Summary)

Oisha-OS — yetuk va mahsulotga yaqin loyiha. **Agent xavfsizlik mexanizmlari (guardrail'lar) g'oyat kuchli ishlangan** — bu loyihaning eng katta yutug'i. Joriy manba kodida hardcoded (kodga yozib qo'yilgan) maxfiy kalitlar yo'q, `.gitignore` keng qamrovli, bandit skani asosiy modullarda toza.

Ammo bitta jiddiy muammo bor: **git tarixiga va Docker image'ga haqiqiy maxfiy kalitlar tushib qolgan.** Bu kodning sifatidan emas, "tozalash" jarayonidan kelib chiqqan — lekin oqibati jiddiy va darhol harakat talab qiladi.

| Daraja | Soni | Mazmuni |
|--------|------|---------|
| 🔴 Critical | 1 | Git tarixida ochiq maxfiy kalitlar (GitHub PAT, AmoCRM tokenlar) |
| 🟠 High | 2 | Docker image'ga maxfiy fayllar pishib qolishi · himoyasiz API endpointlar |
| 🟡 Medium | 6 | Query-paramdagi secret, root Docker, error-handling intizomi, monolit fayllar va b. |
| 🔵 Low | 5 | Root'dagi axlat fayllar, ikki TS workspace, versiya nomuvofiqligi va b. |

**Birinchi 24 soatda qilinadigan ish:** GitHub PAT'ni bekor qilish, AmoCRM tokenlarni qayta generatsiya qilish, `.dockerignore`'ni to'ldirish. Tafsilotlar quyida.

---

## 2. 🔴 CRITICAL — Git tarixidagi ochiq maxfiy kalitlar

Bu eng jiddiy topilma. Maxfiy fayllar keyinroq "remove credentials" commiti bilan o'chirilgan, **lekin git tarixidan o'chmagan** — git tabiatan har bir commitni saqlaydi. Repozitoriyga kirish huquqi bo'lgan har kim `git log` orqali ularni tiklay oladi.

**Topilgan kalitlar:**

1. **GitHub Personal Access Token — commit xabarining O'ZIDA.**
   Commit `245ec22` ning sarlavhasi tokenning aynan o'zi: `ghp_ZZ8X…OcnM` (to'liq qiymat repoda ochiq turibdi). Bu GitHub akkauntingizga to'liq kirish huquqini berishi mumkin.

2. **AmoCRM OAuth tokenlari** — `tmp/amocrm_token_live.json` va `tmp/amocrm_token_cloudrun.json` fayllarida (commit `092b25b`, keyin `7b1b213` da "tozalangan"). Ichida `access_token` (JWT) va, eng muhimi, uzoq muddatli `refresh_token` bor. Refresh token CRM'ingizga doimiy kirish ochib turishi mumkin.

3. **`billing_accounts.json`** — GCP billing ma'lumotlari, tarixда (commit `e25041c`).

### Tavsiya (ketma-ket, shoshilinch)

1. **Hozir:** GitHub Settings → Developer settings → Tokens'da `ghp_ZZ8X…` tokenini **revoke** qiling.
2. **Hozir:** AmoCRM integratsiyasini qayta avtorizatsiya qiling (eski `refresh_token` ni bekor qiluvchi yangi OAuth oqimi). Mijoz bazangiz shu CRM'da — bu eng qimmatli aktiv.
3. **Hozir:** GCP'da `github-actions-key.json` service-account kalitini almashtiring (yangi kalit yarating, eskisini o'chiring).
4. **So'ng:** Git tarixini tozalang — `git filter-repo` yoki BFG Repo-Cleaner bilan o'sha fayllar va commit xabarini olib tashlang, keyin force-push. (Hammaga `git clone`ni qayta qilishni aytasiz.)
5. Buni avtomatlashtirish uchun CI'ga `gitleaks` yoki `trufflehog` skanerini qo'shing — kelajakda secret tushishini bloklaydi.

> **Eslatma:** Aktiv ishlab turgan branda esa, kalit oqishi nafaqat texnik, balki reputatsion risk — mijoz ma'lumotlari (leadlar, suhbatlar) ochilishi brendingizga zarar. Shuning uchun bu #1 ustuvorlik.

---

## 3. 🟠 HIGH — Yuqori darajali risklar

### H-1. Maxfiy fayllar va production DB Docker image'ga pishib qoladi

`Dockerfile` da `COPY . .` butun papkani image'ga ko'chiradi. `.dockerignore` `.env` va `*.session`ni to'g'ri chiqaradi, **lekin quyidagilarни chiqarmaydi** — demak ular har bir production image ichiga kiritiladi:

| Fayl | Nima | Risk |
|------|------|------|
| `bot_database.db` (229 KB) | Production baza: leadlar, kontaktlar, suhbatlar | Mijoz ma'lumotlari oshkor bo'lishi |
| `amocrm_token_secret.json` | AmoCRM OAuth tokenlar | CRM'ga kirish |
| `github-actions-key.json` | GCP service-account kaliti | Bulutga kirish |
| `billing_accounts.json` | GCP billing | Moliyaviy ma'lumot |

Image registry'ga kirish oqib ketsa yoki image ulashilsa — bularning barchasi ochiladi.

**Tavsiya:** `.dockerignore`ga qo'shing:
```
*.db
*.db-shm
*.db-wal
amocrm_token_secret.json
github-actions-key.json
billing_accounts.json
*.json          # va kerakli .json'larni allowlist qiling (!package.json va h.k.)
```
Yoki yanada xavfsiz yo'l: `COPY . .` o'rniga faqat kerakli papkalarni ko'chiring (`COPY src/ ./src/`, `COPY scripts/ ./scripts/` va h.k.).

### H-2. Himoyasiz (autentifikatsiyasiz) tizim endpointlari

`src/api_server.py` da quyidagi endpointlar **hech qanday autentifikatsiyasiz** ochiq turibdi — Cloud Run servisi public bo'lsa, internetdan kim bo'lsa o'qiy oladi:

- `GET /api/system/traces` (satr 961) — agent harakatlari va job-runlar tarixi
- `GET /api/system/inventory` (972) — runtime inventari
- `GET /api/system/activity` (982) — faollik logi
- `GET /api/system/stats` (994) — **biznes ko'rsatkichlari** (leadlar, statistika)
- `GET /dashboard/sales-quality` (1028) — sotuv sifati dashboard

Bu raqobatchiga biznes operatsiyalaringiz haqida ma'lumot bera oladi.

**Tavsiya:** bu endpointlarni ham `OISHA_API_SECRET` (yoki header-orqali Bearer token) bilan himoyalang — xuddi `/api/chat/*` endpointlari kabi. FastAPI `Depends()` bilan umumiy auth dependency yarating va barcha `/api/system/*` ga qo'llang.

---

## 4. 🟡 MEDIUM — O'rtacha risklar

### M-1. Secret URL query-paramda uzatiladi
`GET /api/chat/lookup/{phone}?secret_key=…` (satr 1508) va `GET /api/chat/history/{user_id}?secret_key=…` (1524) maxfiy kalitni URL'da oladi. URL query'lar server access-log'lariga, proksilarga va brauzer tarixiga yoziladi. **Tavsiya:** kalitni `Authorization` header'da uzating, query'da emas. (POST `/api/chat/send` to'g'ri — body'da.)

### M-2. Docker konteyner root sifatida ishlaydi
`Dockerfile`da `USER` direktivasi yo'q → konteyner root huquqida ishlaydi. Image buzilsa, zarar kengayadi. **Tavsiya:** non-root user qo'shing:
```dockerfile
RUN useradd -m appuser
USER appuser
```

### M-3. `deploy.yml` da bandit deploy'ni bloklamaydi
`deploy.yml` (satr 40): `bandit … || true` — skan xato topsa ham deploy davom etadi. (`test.yml` da bloklovchi, shu yengillashtiradi, lekin deploy oqimining o'zi e'tiborsiz qoldiradi.) **Tavsiya:** `|| true`ni olib tashlang yoki ataylab non-blocking ekanини izohда yozing.

### M-4. Juda keng (broad) exception handling
Manba kodida **635 ta `except Exception`** va **8 ta bo'sh `except:`** bor. Eng xavflisi `src/services/core/juma_notifier.py:157` da `except: pass` — xatoni butunlay yutadi. Bunday keng catch'lar buglarni yashiradi va debugни qiyinlashtiradi. Bo'sh `except:` hatto `KeyboardInterrupt`ни ham yutadi.

Joylashuvlar: `handlers/commands.py:238`, `action_parser.py:133`, `admin_bot.py:1806`, `juma_notifier.py:157,236`, `singularity_core.py:227`, `automation_portal.py:64,83`.

**Tavsiya:** bo'sh `except:` larни aniq turlarga almashtiring (`except (ValueError, KeyError):`), kamida `logger.exception()` qo'shing.

### M-5. Guardrail trust-boundary'si
`agent_policy.py` mexanizmi zo'r, lekin `payload.manual_override` yoki `requested_by="owner"` BARCHA gate'larni chetlab o'tadi (satr 61-64, 114-160). Agar bu maydonlarni LLM planner'ning o'zi to'ldira olsa, prompt-injection orqali xavfsizlik o'chirilishi mumkin. **Tavsiya:** `manual_override` / `requested_by` faqat ishonchli (server-side, autentifikatsiyalangan owner) manbadан kelishiga ishonch hosil qiling — LLM chiqishidan emas.

### M-6. Monolit "god-file"'lar
Eng katta fayllar testlash va saqlashни qiyinlashtiradi:
`src/main.py` (2,863 satr), `api_server.py` (2,713), `services/core/proactive_worker.py` (2,273), `admin_bot.py` (1,848), `database.py` (1,404). **Tavsiya:** `api_server.py`ни FastAPI `APIRouter` modullariga bo'ling (system / chat / leads / dashboard); `main.py`dan wiring logikasini ajrating.

---

## 5. 🔵 LOW — Gigiyena va tartib

- **L-1. Root'da git'ga commit qilingan 15 ta axlat fayl:** `=` (0 bayt, xato redirect natijasi), `_fix.py`, `_fx.py`, `_fx2.py`, `_do_fix.py`, `_fix_ai_router.py`, `_fix_all.py`, `_fix_script.py`, `_run_fix.py`, `ai_router.b64` (28 KB base64 blob), `apply_all_fixes.py`, `auto_fix.py`, `do_fix1.py`, `claude_chat.py`, `test_write.py`. → `git rm` qiling, professional ko'rinish uchun.
- **L-2. Ikkita parallel TS monorepo:** root `apps/` (api, web, worker) va `salescoach-ai/apps/` (api, bot, web, worker). Chalkashlik manbai (CLAUDE.md ham ogohlantirgan). → Birini tanlang yoki vazifalarini hujjatlashtiring.
- **L-3. Python versiya nomuvofiqligi:** `Dockerfile` `python:3.11`, CI/dev esa `3.12`. → Bittaga keltiring (3.12 tavsiya).
- **L-4. Lokal branch `origin/main`dan 20 commit orqada** + staged o'zgarishlar bor. → `git pull` / rebase qilib sinxronlang.
- **L-5. Floating dependency versiyalar** (`>=` yuqori chegarasiz). → Reproducibility uchun lock yoki yuqori chegara qo'shing.

---

## 6. ✅ Kuchli tomonlar (saqlab qoling)

Auditda ko'p narsa **juda yaxshi** ishlangani aniqlandi — bularни yo'qotmaslik muhim:

- **`agent_policy.py`** — ko'p qatlamli guardrail: quiet-hours (23:00–07:00), approval gate, confidence chegarasi (<0.85), sezgir-so'z (narx/chegirma/shartnoma) gating. Konstruksiyasi puxta.
- **`auto_reply_gate.py`** — tier'li rollout (off→shadow→vip_only→live) + alohida kill-switch + escalation triggerlar (shikoyat/sud/advokat/firibgar) + past-confidence shadow. Default — xavfsiz `off`. Namunaviy dizayn.
- **Joriy kodda hardcoded secret yo'q**, `eval/exec/shell=True/pickle/yaml.load` yo'q, bandit asosiy modullarda toza.
- **`conftest.py`** testlarni Turso'dan ajratib, SQLite fallback'ga majburlaydi — CI barqarorligi uchun.
- **36 test fayli**, keng qamrov; `test.yml` coverage + bloklovchi bandit ishlatadi.
- **hmac.compare_digest** webhook va cron auth'da (timing-attack'ga chidamli).
- **Multi-stage Docker build** + deploy'da **health-gated rollout** (sog'lom bo'lsagina promote).
- Keng `.gitignore` — joriy maxfiy fayllar tracked emas.

---

## 7. Ustuvor harakatlar rejasi

**Bugun (Critical):**
1. GitHub PAT `ghp_ZZ8X…` ni revoke qilish.
2. AmoCRM OAuth qayta avtorizatsiya (refresh_token almashtirish).
3. GCP service-account kalitini almashtirish.

**Shu hafta (High):**
4. `.dockerignore`ga `*.db` + uchta `.json` faylni qo'shish (yoki `COPY` ni aniqlashtirish).
5. `/api/system/*` va `/dashboard/*` endpointlariga auth qo'shish.
6. Git tarixini `git filter-repo`/BFG bilan tozalash + force-push.

**Shu oy (Medium/Low):**
7. CI'ga `gitleaks` secret-skaner qo'shish.
8. Chat endpointlarda secret'ni header'ga ko'chirish; Docker'ni non-root qilish.
9. Bo'sh `except:` larni tuzatish; `api_server.py`/`main.py`ni modullarga bo'lish.
10. Root'dagi 15 axlat faylni `git rm`; ikki TS workspace'ni tartibga solish; branch'ni sinxronlash.

---

*Hisobot statik kod tahlili, git tarixi va konfiguratsiya tekshiruviga asoslangan. To'liq pytest to'plami sandbox muhitida (barcha bog'liqliklar o'rnatilmagani uchun) ishga tushirilmadi — ammo `py_compile` asosiy fayllarda muvaffaqiyatli o'tdi va test infratuzilmasi puxta tuzilgan.*
