# Oisha-OS — Google AI Studio Context

Sen Jon Branding agentligining **Oisha-OS** tizimi ustida ishlovchi AI assistant san.

## Loyiha haqida

**Oisha-OS** — Telegram userbot + AI agent asosidagi 24/7 avtonom operatsion tizim.
- **Deploy**: Google Cloud Run (`oisha-master-bot`, `europe-west3`)
- **Stack**: Python 3.11, Telethon, Aiogram, FastAPI, Turso (libSQL), Gemini AI
- **GitHub**: `baxtiyorjongaziyev/oisha-os`

## Stack va muhit

```
Runtime:    Python 3.11
Database:   Turso libSQL (libsql://oisha-os-db-baxtiyorjongaziyev.aws-ap-south-1.turso.io)
AI:         Google Gemini (primary), DeepSeek (fallback)
Deploy:     Google Cloud Run via GitHub Actions
Secrets:    GCP Secret Manager
Session:    Google Cloud Storage (oisha.session)
```

## Asosiy fayllar

| Fayl | Vazifa |
|---|---|
| `src/main.py` | Asosiy kirish nuqtasi (Telethon + Aiogram launcher) |
| `src/api_server.py` | FastAPI `/health` endpoint |
| `src/database.py` | SQLite + Turso wrapper |
| `src/database_pool.py` | Connection pool |
| `src/settings.py` | Pydantic settings (env vars) |
| `src/agents/ai_router.py` | Multi-model AI routing |
| `src/agents/orchestrator.py` | Agent koordinatsiya |
| `src/services/core/persona_hub.py` | Oisha persona boshqaruvi |
| `src/services/core/lead_operating_system.py` | Lead boshqaruvi |
| `src/services/core/auto_reply_gate.py` | Shadow/active auto-reply |
| `src/services/core/mission_control.py` | Jamoaviy vazifalar |
| `src/services/core/enterprise_reporter.py` | Cockpit report |
| `src/services/core/amocrm_sync.py` | AmoCRM integratsiya |
| `src/mcp_server.py` | MCP diagnostika serveri |

## Muhim qoidalar

1. **Test qilman** — barcha o'zgarishlarda `src/database.py`, `src/api_server.py`, `src/main.py` fayllarini py_compile tekshiruvi o'tishi kerak
2. **Import yo'li** — `from src.services.core.X import Y` shaklida, PYTHONPATH root
3. **Async everywhere** — barcha servislar `asyncio` asosida, `async def` ishlatiladi
4. **Environment** — barcha secrets `.env` faylidan yoki GCP Secret Manager'dan
5. **Turso** — `database_pool.py` orqali, to'g'ridan-to'g'ri sqlite3 ishlatma
6. **DEV_LOG.md** — push qilganda avtomatik yangilanadi, qo'lda yozma

## Hozirgi muammolar (hal qilish kerak)

- ⚠️ AmoCRM token muddati tugagan → `src/services/debug/get_amocrm_token.py`
- ⚠️ AmoCRM: 501/500 lead limiti → `src/services/debug/crm_janitor.py --dry-run`
- ⚠️ AmoCRM: 406MB disk limiti → `src/services/debug/crm_file_offloader.py`

## Workflow

```bash
# Local ishga tushirish
PYTHONPATH=. python src/main.py

# Test
python -m pytest tests/ -v --tb=short

# Deploy (GitHub Actions orqali avtomatik)
git push origin main
```

## Kodni yozish uslubi

- Python type hints ishlatiladi
- Logging: `logging.getLogger(__name__)`
- Error handling: try/except + log, exception oshirma
- Yangi servis: `src/services/core/` ichiga, `async class` shaklida
- Yangi test: `tests/` ichiga, `pytest-asyncio` bilan
