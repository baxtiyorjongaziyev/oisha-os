# Cloudflare Code Mode Protokoli

Oisha-OS tizimidagi barcha AI agentlar (**Codex**, **Claude Code**, **Antigravity**) uchun koʻp qadamli API, maʼlumotlar bazasi va MCP (Model Context Protocol) vositalari bilan ishlash standarti.

---

## 1. Konseptsiya

Cloudflare tomonidan ilgari surilgan **Code Mode** tamoyili quyidagicha:
> *"Executing code is all you need for MCP and agentic tools."*

Anʼanaviy agentlarda har bir vosita (tool) alohida JSON sxemasi orqali modelga uzatiladi. Katta APIʼlar (masalan, Cloudflareʼning 2,500+ endpointi, AmoCRM, Turso, Meta Graph) butun kontekst oynasini (millionlab tokenlarni) egallaydi.

**Code Mode arxitekturasida:**
1. Agent minglab vositalar roʻyxatini kontekstda saqlamaydi.
2. Buning oʻrniga atigi ikkita asosiy qadam ishlatiladi:
   - **`search / inspect`**: Kerakli modullar, tiplar yoki endpointlarni aniqlash.
   - **`execute`**: Olingan API va maʼlumotlarni birlashtiruvchi, sikl va filtrlarga ega ixcham kod (Python yoki TypeScript) yozish va qumloqda (sandbox) ishga tushirish.
3. Kontekstga faqat **yakuniy ixcham xulosa** qaytariladi.

---

## 2. Oisha-OS dagi 3 ta qoida

### 1-qoida: Maʼlumotni manbada filtrlang (Filter at Source)
Hech qachon 50 tadan ortiq xom JSON obyektini bevosita agent kontekstiga yuklamang. Agar statistik raqam yoki saralangan natija kerak boʻlsa, filtrlash va hisoblashni skript ichida bajaring:

```python
# Masalan: faol bitimlarni sanash
leads = await amocrm.get_leads()
active_leads = [lead for lead in leads if lead.status_id in ACTIVE_STATUSES]
print(f"Jami faol: {len(active_leads)}")
```

### 2-qoida: "Search then Execute" (2 vosita andozasi)
- Birinchi bosqichda sxema yoki funksiya signaturasini qisqa koʻzdan kechiring.
- Ikkinchi bosqichda barcha kerakli amallarni bajaruvchi bitta skript yozing va ishga tushiring.

### 3-qoida: Koʻp bosqichli amallarni birlashtirish (Single-turn Execution)
Agar operatsiya ketma-ket 3+ bosqichdan iborat boʻlsa:
- Bosqichma-bosqich har safar agentga javob qaytarib, yangi navbat (turn) kutmang.
- Barcha bosqichlarni oʻz ichiga olgan xavfsiz, idempotent skript tuzing.

---

## 3. Agentlar rollari va amaliyoti

- **Codex (Implementer):**
  Katta migratsiyalar, DB tahlillari va ommaviy sinxronizatsiyalarda `python -c` yoki `scripts/` ichidagi yordamchi skriptlardan foydalanadi.
- **Claude Code (Reviewer / Dev):**
  Kodni tahlil qilishda yuzlab fayllarni oʻqimasdan, testlar, diff va xatoliklarni maqsadli buyruqlar orqali tekshiradi.
- **Antigravity (Analyst / Orchestrator):**
  Murakkab biznes hisobotlari (moliya, CRM pipeline, lidlar statistikasi) uchun bitta skript yozib, qisqa xulosani foydalanuvchiga taqdim etadi.

---

## 4. Xavfsizlik

- Lokal userbot sessiyasi Hetzner prod VPSʼga tegishli (2.29.198.0; `ALLOW_LOCAL_RUN=0`).
- `.env` yoki sirlarni kod orqali ekranga chiqarish qatʼiyan taqiqlanadi.
- Skriptlar `AGENTS.md` dagi xavfsizlik chegaralari va `.claude/hooks/guard.py` qoidalariga toʻliq mos boʻlishi shart.
