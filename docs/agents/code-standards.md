# Code Standards (MAJBURIY)

> AGENTS.md dan ko'chirildi (2026-09-29).

## Communication & Architecture Rules

1. **Bir faylga bir vaqtda faqat bitta agent yozadi**
2. **Agent ish boshlaganda `## Locks` ga o'z nomini yozadi, tugatganda o'chiradi**
3. **Shared fayllarga (settings.py, context.py, boot.py) faqat Agent Coordinator yozadi**
4. **Har bir PR dan oldin `pytest -q` va `bandit -r src/ -ll` ishga tushiriladi**
5. **git commit → git push → keyin keyingi agent pull qiladi (rebase)**
6. 📏 **400 QATOR CHEGARASI (MODULAR CODE STANDARD — MAJBURIY):**
   - **Fayl Hajmi**: Production Python (`src/**/*.py`) va TypeScript (`apps/**/*.ts`) implementatsiya fayllari **400 qatordan oshmasligi** shart. Facade, `__init__`, schema/type, migration, test va bir martalik operator skriptlarida sun'iy 150-qator minimum yo'q; ular SRP va xavfsizlik talablariga baribir rioya qiladi.
   - **"God-file" Mutlaqo Taqiqlanadi**: Hech qaysi fayl 400 qatordan oshmasligi kerak (1000+ qatorli monolithic fayllar qat'iyan man etiladi).
   - **Avtomatik Dekompozitsiya (SRP & Mixin Pattern)**: Modul yoki klass kengayib 400 qatordan oshsa, darhol o'z vazifasiga ko'ra alohida submodullarga (auth, leads, formatting, reporting, schedulers, actions) ajratiladi va Mixin/Composition orqali birlashtiriladi.
   - **Zero-Breaking Facade Pattern**: Eski fayl yo'li saqlanib, 10–50 qatorli toza Facade rejimiga o'tkaziladi va barcha public API, klass, funksiya va konstantalarni to'liq re-export qiladi (`__all__` bilan). Mavjud importlar va testlar 100% buzilmasdan ishlashi shart.
   - **Funksiyalar Hajmi**: Har bir alohida funksiya/metod **20 – 60 qatordan** oshmasligi, bitta aniq vazifani bajarishi shart.
   - **Yangi Kod Yozish Qoidasi**: Yangi funksionallik qo'shganda mavjud to'lgan fayllarga kod tiqishtirish taqiqlanadi — yangi modul yoki submodule ochiladi.
7. **Claude Antigravity handoff (majburiy):** Har bir agent tugatgan yoki to'xtatgan ishini shu fayldagi `## Agent Handoff Log` bo'limiga yozadi: sana/agent, bajarilgan ish, o'zgargan fayllar, tekshiruv dalili va qolgan ish/bloker. Sirlar, tokenlar va session stringlar jurnalga yozilmaydi.
8. **Airtable & Obsidian Sinxronizatsiya Qoidasi (Owner Majburiy Qoidasi — 2026-09-15):** Barcha AI agentlar Airtable'da har qanday o'zgarish (moliyaviy tranzaksiya, loyiha, schema/maydon, status) amalga oshirsa, bu o'zgarish darhol Obsidian vault'dagi `20-Areas/Airtable_Operatsion_Tizimi_va_Ozgarishlar.md` notasiga va `brain_log` orqali muhrlanishi shart. O'zgarishlar Airtable ichida yashirin qolib ketishi qat'iyan taqiqlanadi.

