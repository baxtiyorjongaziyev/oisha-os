# Oisha-OS Loyiha Strukturasi Takomillashtirish Rejasi

## Hozirgi Muammo
- 150+ Python fayllar ildiz目录da tartibsiz
- Scripts, deployment, va asosiy kod aralash
- Import qilish qiyin
- Loyihani tushunish va qo'llab-quvvatlash murakkab

## Taklif Etilayotgan Yangi Struktura

```
oisha-os/
├── src/                          # Asosiy ilova kodi
│   ├── __init__.py
│   ├── main.py                   # Botni ishga tushirish (userbot.py dan)
│   ├── config.py                 # Konfiguratsiya
│   ├── settings.py               # Sozlamalar (pydantic)
│   ├── database.py               # Ma'lumotlar bazasi
│   │
│   ├── agents/                   # AI Agentlar
│   │   ├── __init__.py
│   │   ├── advisor_agent.py
│   │   ├── auto_lead_agent.py
│   │   ├── audit_agent.py
│   │   ├── activity_monitor.py
│   │   └── ...
│   │
│   ├── services/                 # Biznes logika xizmatlari
│   │   ├── __init__.py
│   │   ├── google_service.py     # Google Contacts, Calendar, Sheets
│   │   ├── crm_service.py        # AmoCRM integratsiyasi
│   │   ├── lead_scraper.py       # Lead aniqlash va saqlash
│   │   ├── action_parser.py      # Harakat parseri
│   │   ├── safe_responder.py     # Xavfsiz javob berish
│   │   ├── enterprise_reporter.py # Hisobotlar
│   │   ├── workflow_manager.py   # Ish oqimi menejeri
│   │   └── ...
│   │
│   ├── controllers/              # Nazoratchilar
│   │   ├── __init__.py
│   │   └── message_controller.py # Xabar nazoratchisi
│   │
│   ├── handlers/                 # Telegram handlerlar
│   │   ├── __init__.py
│   │   └── commands.py           # Buyruqlar handleri
│   │
│   └── utils/                    # Yordamchi funksiyalar
│       ├── __init__.py
│       ├── logger.py
│       └── helpers.py
│
├── scripts/                      # Mustaqil skriptlar
│   ├── sync_contacts.py
│   ├── process_backlog_leads.py
│   ├── verify_proof.py
│   └── ...
│
├── deploy/                       # Deployment fayllar
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── Procfile
│   ├── railway.json
│   └── ...
│
├── tests/                        # Testlar
│   ├── __init__.py
│   ├── test_ai.py
│   ├── test_contact_ai.py
│   ├── test_history.py
│   └── ...
│
├── docs/                         # Hujjatlar
│   ├── API.md
│   ├── DEPLOYMENT.md
│   └── ...
│
├── .env                          # Muhit o'zgaruvchilari
├── .env.example                  # Muhit shabloni
├── .gitignore
├── requirements.txt              # Python bog'liqliklar
├── README.md                     # Asosiy hujjat
└── QOLLANMA.md                   # O'zbek tilida qo'llanma
```

## Ko'chirish Kerak Bo'lgan Asosiy Fayllar

### src/ ichiga:
- `userbot.py` → `src/main.py`
- `config.py` → `src/config.py`
- `settings.py` → `src/settings.py`
- `database.py` → `src/database.py`
- `agent_core.py` → `src/agents/core.py`
- `agent_orchestrator.py` → `src/agents/orchestrator.py`
- `agent_tools.py` → `src/agents/tools.py`
- `services/*.py` → `src/services/` (hammasi)
- `controllers/*.py` → `src/controllers/` (hammasi)
- `handlers/*.py` → `src/handlers/` (hammasi)

### scripts/ ichiga:
- Barcha `*_audit.py`, `*_sync.py`, `*_cleanup.py` fayllar
- `amocrm_*.py` fayllar
- `analyze_*.py`, `check_*.py` fayllar
- `deploy_*.py` fayllar (deploy/ ga ko'chirish yaxshiroq)

### tests/ ichiga:
- `test_*.py` fayllar

## Import o'zgarishlari

### Hozirgi:
```python
from services.google_service import GoogleService
from controllers.message_controller import MessageController
```

### Yangi:
```python
from src.services.google_service import GoogleService
from src.controllers.message_controller import MessageController
# Yoki (agar src/ PYTHONPATH da bo'lsa):
from services.google_service import GoogleService
```

## Deployment o'zgarishlari

### Dockerfile yangilanadi:
```dockerfile
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY src/ ./src/
COPY scripts/ ./scripts/
CMD ["python", "-m", "src.main"]
```

## Afzalliklari
1. **Toza struktura** - Har bir komponent o'z joyida
2. **Oson navigatsiya** - Yangi dasturchilar tezroq tushunadi
3. **Modullik** - Har bir qismni alohida test qilish mumkin
4. **Masshtablanish** - Yangi xususiyatlar qo'shish oson
5. **Xavfsizlik** - Muhim fayllar yaxshi tashkil etilgan

## Keyingi qadamlar
1. Yangi papkalarni yaratish
2. Fayllarni ko'chirish
3. Importlarni yangilash
4. Testlarni o'tkazish
5. Deployment skriptlarini yangilash
6. Hujjatlarni yangilash