---
name: code-mode
description: Cloudflare Code Mode yondashuvi — barcha AI agentlar (Claude, Codex, Antigravity) uchun. Katta API, DB va MCP vositalari bilan ishlashda xom JSON yoki koʻp qadamli tool-calling oʻrniga ixcham skript orqali bajarish va kontekst oynasini tejash qoidasi.
---

# Code Mode (Cloudflare Pattern)

Oisha-OS ekotizimidagi barcha agentlar (**Claude Code**, **Codex**, **Antigravity**) uchun koʻp qadamli API, maʼlumotlar bazasi va MCP vositalari bilan ishlashda kontekst oynasini asrash hamda kechikishni (latency) kamaytirish qoidasi.

---

## 1. Asosiy maqsad va muammo

Anʼanaviy **JSON-Schema Tool Calling** (ketma-ket vositalarni chaqirish):
- Har bir qadamda yangi LLM chaqiruvi talab qilinadi.
- Katta APIʼlar (masalan, Cloudflare, AmoCRM, Turso) yuzlab vositalarni talab qiladi va millionlab tokenlarni behuda sarflaydi.
- 500 ta elementli xom JSON javob toʻgʻridan-toʻgʻri kontekstga tashlanadi va kontekst oynasi (context window) tezda toʻlib qoladi.

**Code Mode yondashuvi:**
> "Executing code is all you need for MCP and agentic tools."

LLM vositalarni bittalab chaqirmaydi. Buning oʻrniga agent ixcham dastur kodi (Python yoki TypeScript) yozadi va uni qumloqda (sandbox / runtime) bajartiradi. Natijada xom maʼlumotlar mahalliy (lokal) filtrlanadi va kontekstga faqat **yakuniy ixcham natija** qaytariladi.

---

## 2. Uchta Oltin Qoida

### Qoida 1: Maʼlumotni manbada filtrlang va jamlang (Filter at Source)
Hech qachon 50 tadan ortiq yozuvni toʻgʻridan-toʻgʻri chat/kontekstga yuklamang. Agar sizga faqat statistik raqam yoki bir nechta qator kerak boʻlsa, darhol Python yoki SQL kodi orqali filtrlashni skript ichida bajaring:

```python
# YOMON: Barcha lidlarni kontekstga yuklash
leads = await amocrm.get_leads() # 500 ta obyekt = 40,000 token!

# YAXSHI: Code Mode (skript ichida filtrlash)
active = [l for l in leads if l.status == "in_progress"]
print(f"Jami faol lidlar: {len(active)}")
```

### Qoida 2: "Search then Execute" (2 vosita andozasi)
Katta API yoki keng kutubxonalar bilan ishlaganda:
1. `search / inspect`: Kerakli metod, endpoint yoki tip taʼrifini aniqlab oling.
2. `execute`: Hammasini birlashtiruvchi, sikl va xatolarni ushlovchi skript yozing va ishga tushiring.

### Qoida 3: Atomik koʻp bosqichli ijro (Atomic Multi-step Execution)
Agar vazifa 3 tadan ortiq qadamni talab qilsa (masalan: 1. DB dan olish → 2. hisoblash → 3. CRM ga yozish):
- Buni 3 marta alohida LLM navbati (turn) orqali qilmang.
- Yagona, idempotent Python skripti (masalan, `scripts/scratch/` yoki vaqtinchalik buyruq) tuzing va bir marta ishga tushiring.

---

## 3. Agentlar boʻyicha taqsimot

| Agent | Rol | Code Mode qoʻllanilishi |
| :--- | :--- | :--- |
| **Codex** | Implementer | Murakkab migratsiya, DB tekshiruvlari va ommaviy API operatsiyalarini skript orqali bajaradi. |
| **Claude Code** | Reviewer / Dev | Diff va loglarni tekshirishda xom fayllarni birma-bir oʻqimasdan, test va tahlil skriptlari orqali natijani oladi. |
| **Antigravity** | Analyst / Orchestrator | Katta tahliliy maʼlumotlarni (CRM holati, moliya balansi) yagona skript orqali jamlab, hisobot tayyorlaydi. |

---

## 4. Xavfsizlik cheklovlari

Code Mode skriptlari loyihaning umumiy xavfsizlik qoidalariga boʻysunadi (`AGENTS.md` va `.claude/hooks/guard.py`):
1. **Lokal userbot ishga tushirilmaydi** (`ALLOW_LOCAL_RUN=0`).
2. `.env` va sirli kalitlar konsolga yoki loglarga chiqarilmaydi.
3. Buzuvchi buyruqlar (`rm -rf`, `git reset --hard`) taqiqlanadi.
4. Vaqtinchalik sinov fayllari `scripts/debug/` yoki scratch papkasida saqlanadi.
