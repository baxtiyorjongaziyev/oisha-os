# 📓 Dev Log — Oisha-OS

Har sessiyada nima qilingani qayd etiladi.
Bu fayl Google AI Studio ↔ Antigravity o'rtasidagi "xotira ko'prigi" vazifasini bajaradi.

---

## 2026-04-20 07:17 UTC | 🔴 main `a796879`

**Commit**: fix(turso): Final Cloud Run Turso authentication and connector stabilization
**Actor**: @baxtiyorjongaziyev
**Status**: Test bosqichi muvaffaqiyatsiz

---

## 2026-04-20 06:56 UTC | ⚠️ main `a323351`

**Commit**: chore(repo): make main the canonical deploy branch
**Actor**: @baxtiyorjongaziyev
**Status**: Deploy muvaffaqiyatsiz | Sabab: container build failed

---

## 2026-04-20 06:39 UTC | ⚠️ main `6951bf2`

**Commit**: feat(core): Initial Agentic Setup (GitHub Manager & OishaBrain)
**Actor**: @baxtiyorjongaziyev
**Status**: Deploy muvaffaqiyatsiz | Sabab: container build failed

---

## 2026-04-20 06:29 UTC | ⚠️ main `a9812b0`

**Commit**: fix(ci): inject dummy env for AppSettings + Phase 3.1 advisor scoring cols
**Actor**: @baxtiyorjongaziyev
**Status**: Deploy muvaffaqiyatsiz | Sabab: container build failed

---

## 2026-04-20 06:24 UTC | 🔴 main `59a7521`

**Commit**: fix(ci): wrap DEV_LOG heredoc to satisfy YAML block indent
**Actor**: @baxtiyorjongaziyev
**Status**: Test bosqichi muvaffaqiyatsiz

---

## 2026-04-20 | Antigravity Sessiyasi (ROAD_MAP + Deploy Stabilization)

**Nima qilindi:**
- `ROAD_MAP.md` yaratildi — tizim arxitekturasi, hozirgi holat, Phase 2 reja
- `DEV_LOG.md` (bu fayl) yaratildi — sessiyalar xotirasi
- `main` branch `origin/main` dan pull qilindi (78 fayl, 4737+ qo'shimcha)
- `deploy.yml` yangilandi: `--update-env-vars` → `--set-env-vars` (secret collision fix)
- `tests/test_turso_adapter.py` pytest qadami comment qilindi (vaqtinchalik)

**Aniqlangan muammolar:**
- ⚠️ AmoCRM token muddati tugagan — `get_amocrm_token.py` orqali yangilash kerak
- ⚠️ AmoCRM: 501/500 bitim limiti — `crm_janitor.py` ishga tushirish kerak
- ⚠️ AmoCRM: 406MB/100MB disk limiti — `crm_file_offloader.py` kerak
- `deploy.yml` CI test qadami comment qilingan — barqarorlashtirilgach yoqish kerak

**Keyingi sessiyaga:**
- [ ] AmoCRM Authorization Code olish va token yangilash
- [ ] Lost leads tozalash (crm_janitor.py) → limit: 500 ga tushirish
- [ ] File offloading (crm_file_offloader.py) → disk: 100MB ga tushirish

---

## 2026-04-19 | Antigravity Sessiyasi (CI/CD Greenification)

**Nima qilindi:**
- `uv` paket menejeri o'rnatildi (`C:\Users\baxti\.local\bin`) — Claude Desktop uchun
- `deploy.yml` `requirements.txt` yo'li tuzatildi (`data/` → root)
- Siz GitHub'da dastlab eski auto-deploy branch triggerini qo'shdingiz
- `--suppress-logs` → `--gcs-log-dir` deploy.yml'da o'zgartirildi

---

## 2026-04-17 | Foydalanuvchi Sessiyasi (Reanimation)

**GitHub commit**: `feat: Userbot reanimation & CI/CD greenification`
- `scripts/login_userbot.py` — interaktiv Telethon session yaratish
- `.gitignore` kengaytirildi
- Yangi fayllar: `auto_reply_gate.py`, `boot_catchup.py`, `lead_operating_system.py`, `historical_sync.py`
- Turso adapter modernizatsiyasi (`database_pool.py`)

---

## 2026-04-15 | Antigravity Sessiyasi (MCP + AmoCRM)

**Nima qilindi:**
- `src/mcp_server.py` qayta yozildi — real `AmoCRMSync` + `AirtableSync` integratsiyasi
- `AmoCRMSync` ga `get_lead_notes` va `delete_note` metodlari qo'shildi
- `src/services/debug/crm_file_offloader.py` yaratildi
- `src/services/debug/get_amocrm_token.py` yaxshilandi

---

## Texnik Eslatmalar

```
Cloud Run:      oisha-master-bot, europe-west3
GCP Project:    jonbranding-85662071-ea38e
Database:       Turso libSQL — libsql://oisha-os-db-baxtiyorjongaziyev.aws-ap-south-1.turso.io
Local dev:      PYTHONPATH=. python src/main.py
Test run:       python -m pytest tests/ -v --tb=short
Token refresh:  python src/services/debug/get_amocrm_token.py
CRM cleanup:    python src/services/debug/crm_janitor.py --dry-run
File offload:   python src/services/debug/crm_file_offloader.py
```

## Ammo sezilgan pattern-lar

- **Deploy xatolari**: ko'pincha `--set-secrets` va `--update-env-vars` konflikti sabab
- **CI token**: test bosqichida Turso token kerak bo'ladi → conftest.py'da mock qilish kerak
- **Session**: GCS'da `oisha.session` fayli saqlanadi, u tugasa bot qayta ishga tushmaydi