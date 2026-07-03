# Oisha-OS Agent Coordination Protocol

> Barcha AI agentlar ish boshlashdan oldin bu faylni o'qiydi va tugatgandan keyin yangilaydi.

## Communication Rules

1. **Bir faylga bir vaqtda faqat bitta agent yozadi**
2. **Agent ish boshlaganda `## Locks` ga o'z nomini yozadi, tugatganda o'chiradi**
3. **Shared fayllarga (settings.py, context.py, boot.py) faqat Agent Coordinator yozadi**
4. **Har bir PR dan oldin `pytest -q` va `bandit -r src/ -ll` ishga tushiriladi**
5. **git commit → git push → keyin keyingi agent pull qiladi (rebase)**

## Roles

| Agent | Scope | Owner |
|-------|-------|-------|
| **Coordinator** | AGENTS.md, settings.py, context.py, boot.py, PR merge | @user |
| **Parser** | main.py → handlers/, commands/, schedulers/ | — |
| **Hisobchi** | hisobchi_engine.py, hisobchi_handlers.py, hisobchi_schema.py | — |
| **Security** | tests/, bandit issues, exception handling | — |
| **Migration** | global variable → app_ctx.* | — |
| **Database** | database.py, migrations, SQL optimization | — |
| **API Server** | api_server.py, endpoints, auth | — |
| **Integration** | AmoCRM, Airtable, Telegram integrations | — |
| **Documentation** | README, API docs, inline docs | — |
| **Performance** | profiling, caching, optimization | — |
| **Code Quality** | dead code, naming, type hints | — |

## Current State

### Locked
- **Hisobchi (Codex)** — branch/worktree `codex/hisobchi-production` (`C:\Users\baxti\playground\oisha-os-card-finance`). Vazifa: Hisobchi card-bot production verification, userbot session holati, Oracle VM runtime dalillari. Shared fayllarga tegilmaydi.
- **Integration (Claude)** — branch `feat/agent-integrations`. Fayllar:
- Test: 316 passed, 1 failed (instagrapi missing), 8 skipped

### Done (yangi)
- Saved Messages/private photo receipt auto-scan cheklandi: endi owner private rasmlari faqat `/kirim`, `/chiqim`, `/chek`, `/receipt`, `#kirim`, `#chiqim` markerlari bilan ishlanadi; oddiy saqlangan rasmlar Hisobchi/Gemini tekshiruviga tushmaydi. Test: 358 passed, 13 skipped; Bandit: no issues (Codex).
- Barcha ochiq PRlar (38 ta) va Dependabot security alerts (multer, nodemailer, @babel/core) hal qilindi: dependency lar eng oxirgi versiyaga yangilandi, xavfsizlik kamchiliklari (SSL verification) tuzatildi va gitleaks historical allowlist yangilandi (TRAE).
- Meta Graph API orqali Instagram DM va Comment webhooklari to'liq implement qilindi (`src/api_server.py` va `src/services/core/instagram_agent.py` yaratildi) hamda local va remote testlardan muvaffaqiyatli o'tdi (Antigravity).
- Webhook so'rovlarini `x-hub-signature-256` orqali xavfsiz tasdiqlash va background tasks orqali Meta timeoutlarining oldini olish yo'lga qo'yildi (Antigravity).
- Yangilangan kod remote Oracle VM ga deploy qilindi, uerdagi `oisha-os` systemd xizmati qayta ishga tushirilib, API server muvaffaqiyatli ishlayotganligi `/healthz/` orqali tasdiqlandi (Antigravity).
- `handle_new_message` event handler sifatida ro'yxatdan o'tkazildi
- Hisobchi AI: `init_hisobchi_tables()` boot.py da chaqiriladi
- Hisobchi AI: `_hisobchi_engine` global placeholder qo'shildi
- Masofaviy n8n da Google Gemini API orqali ishlaydigan bepul AI Chatbot workflow (ID: `xf2kLGu1vuXGM5cC`) to'liq sozlandi va faollashtirildi (Antigravity).
- n8n v1.0+ ga mos keladigan yangi connection formatiga (`ai_languageModel` porti) muvofiq Gemini ulanishlari to'g'rilandi.
- Gemini API ning `host` parametridagi protokol xatosi va `modelName` parametrining model mos kelmasligi (`gemini-2.5-flash` ga o'zgartirish orqali) hal qilindi.
- Chatbot webhook POST so'rovlari muvaffaqiyatli sinovdan o'tdi (Response: `{"output":"..."}`).
- database.py: f-string SQL -> parametrized query refactoring bajarildi (682 va 998 qatorlar, `upsert_user` va `get_storage_counts`). Bandit va pytest tekshiruvlaridan muvaffaqiyatli o'tdi (Antigravity).
- Web chat widgeti production xatoligi (FastAPI /api/chat/send va /api/chat/history API-dagi 422 xatoliklar) `X-Secret-Key` header qo'llab-quvvatlash orqali tuzatildi, barcha testlardan o'tdi va remote Oracle VM ga deploy qilinib muvaffaqiyatli ishga tushirildi (Antigravity).

### Next Tasks
1. [Done] `self_command_handler` (1000+ lines) → `src/commands/` ga ajratish
2. [Done] `except Exception: pass` larni tuzatish (~30+ joy `call_analyzer.py` da tuzatildi)
3. Global → app_ctx.* migratsiyasi (Jarayonda)
4. [Done] f-string SQL → parametrized query (database.py:682, 998)
5. [Done] Handler lar: `src/handlers/` ga ajratish (negotiation, kirim, case_publisher, etc.)

### Dead Files (don't touch)
- `src/agents/` — autonomous AI agents, domain-specific, bu refactoringga kirmaydi
- `src/services/debug/` — tashqi debug tools
- `src/legacy/` — eski prototiplar

## Pre-flight Checklist (har bir PR dan oldin)
```powershell
$env:SKIP_LIVE=1; python -m pytest -q --tb=short
bandit -r src/ -ll
```

## Branch Naming
`feat/<short-description>` yoki `fix/<short-description>`

## Commit Style
`feat(scope): message` / `fix(scope): message` / `refactor(scope): message`
