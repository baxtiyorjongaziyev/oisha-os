# Telegram SalesCoach → AmoCRM Design

## Maqsad

Oracle VM’dagi Telegram userbot ko‘ra oladigan biznes dialoglarini tahlil qilish, sotuvchi ishini 100 ballik SalesCoach mezonida baholash va dalil yetarli bo‘lsa AmoCRM’dagi tegishli lead uchun aniq keyingi vazifani yozish.

Tizim mijozga o‘zi xabar yubormaydi. U faqat baho, tavsiya, tayyor javob varianti, AmoCRM note va task beradi.

## Scope

Birinchi versiya quyidagilarni qamrab oladi:

- Telegram private DM dialoglari;
- faqat AmoCRM lead/contact bilan ishonchli bog‘langan suhbatlar;
- matnli xabarlar va voice note transcriptlari;
- SalesCoach scoring;
- Oisha bazasiga tahlil natijasini saqlash;
- AmoCRM note va task write-back;
- task dedupe va write verification;
- shadow, approval va auto rollout rejimlari.

Birinchi versiyaga kirmaydi:

- mijozga avtomatik javob yuborish;
- guruh chatlarini ommaviy tahlil qilish;
- CRM’da yangi leadni faqat AI taxmini asosida avtomatik ochish;
- past ishonchli tasklarni tasdiqsiz yozish;
- shaxsiy/oila/do‘st dialoglarini tahlil qilish.

## Asosiy arxitektura

1. `src/handlers/message_handler.py` Telegram eventni qabul qiladi.
2. Yangi `src/services/core/telegram_salescoach.py` dialogni filtrlash, batching, fingerprint, CRM mapping va orchestration bilan shug‘ullanadi.
3. `src/services/core/salescoach_sync.py` SalesCoach API’ning yangi `/v1/negotiations/analyze-conversation` endpointiga strukturali payload yuboradi.
4. `salescoach-ai/apps/api` kiruvchi payloadni validatsiya qiladi va scoring queue’ga uzatadi.
5. Worker LLM javobini schema bo‘yicha tekshiradi va structured analysis qaytaradi.
6. Oisha tahlilni `call_analyses`ga mos yangi source bilan saqlaydi yoki alohida `conversation_analyses` jadvaliga yozadi. Implementatsiya vaqtida mavjud schema bilan collision bo‘lmasa alohida jadval afzal.
7. Yangi async AmoCRM task writer leadning `responsible_user_id` qiymatini ishlatadi, dublikatni tekshiradi, note/task yozadi va qayta o‘qib tasdiqlaydi.
8. Approval mode’da owner yoki sales lead Telegram inline action orqali taskni tasdiqlaydi.

## Telegram dialog filtrlari

Tahlilga faqat quyidagi shartlarning barchasi mos kelgan dialog kiradi:

- private user chat;
- bot emas;
- ownerning Saved Messages’i emas;
- `PERSONAL_FOLDER_KEYWORDS` orqali shaxsiy/oila/do‘st papkasiga kirmaydi;
- ichki jamoa Telegram ID ro‘yxatiga kirmaydi;
- AmoCRM contact/lead bilan telefon, username yoki oldindan saqlangan mapping orqali bog‘langan;
- oxirgi batchda kamida ikki tomonlama suhbat bor;
- yangi xabarlar oldingi `conversation_fingerprint` bilan bir xil emas.

Loglarda xabar matni, telefon, token yoki session string yozilmaydi. Faqat hashed identifiers va event holati yoziladi.

## Batching va trigger

Har bir dialog uchun buffer yuritiladi.

Tahlil quyidagi holatlardan birida ishga tushadi:

- yangi xabardan keyin 10 daqiqa jimlik;
- mijoz savol yoki e’tiroz bilan yakunlagan va 15 daqiqa javobsiz qolgan;
- sotuvchi uchrashuv, KP, material yoki follow-up va’da qilgan;
- owner `/sales_audit` yoki admin paneldan qo‘lda ishga tushirgan.

Default batch: oxirgi 50 ta matnli xabar yoki 7 kunlik faol blok, qaysi biri kichik bo‘lsa. Voice note bo‘lsa transcript matnga qo‘shiladi, audio fayl LLM promptiga yuborilmaydi.

## CRM matching

Matching ustuvorligi:

1. saqlangan `telegram_user_id → contact_id/lead_id` mapping;
2. verified telefon raqami;
3. verified Telegram username custom field;
4. contact note yoki oldingi Telegram sync evidence;
5. nom bo‘yicha taxmin faqat approval queue uchun, auto task uchun emas.

Auto write uchun confidence kamida `0.85` bo‘lishi kerak. `0.60–0.84` oralig‘i approval mode’ga tushadi. `0.60`dan past bo‘lsa faqat dashboardda “bog‘lanmagan” deb ko‘rsatiladi.

## SalesCoach scoring — 100 ball

- Kontakt va suhbatni boshlash — 10
- Ehtiyojni aniqlash va SPIN savollari — 20
- Mijoz og‘rig‘iga mos taklif — 15
- Qiymatni tushuntirish — 15
- E’tiroz bilan ishlash — 15
- Keyingi qadamni aniq belgilash — 15
- Javob tezligi va suhbat intizomi — 10

Natija schema:

```json
{
  "overall_score": 0,
  "scores": {
    "opening": 0,
    "needs_discovery": 0,
    "solution_fit": 0,
    "value_explanation": 0,
    "objection_handling": 0,
    "next_step": 0,
    "response_discipline": 0
  },
  "strengths": [],
  "mistakes": [],
  "missed_questions": [],
  "client_intent": "cold|warm|hot",
  "objections": [],
  "deal_risk": "low|medium|high",
  "next_best_action": "",
  "recommended_reply": "",
  "recommended_tasks": [],
  "confidence": 0.0,
  "evidence_message_ids": []
}
```

Barcha ballar deterministic range validationdan o‘tadi. Umumiy ball kategoriya ballari yig‘indisiga teng bo‘lishi kerak; farq bo‘lsa server qayta hisoblaydi.

## AmoCRM note va task qoidalari

Har bir tahlil leadga bitta strukturali note yozadi:

- SalesCoach balli;
- mijoz intenti;
- asosiy e’tiroz;
- bitim riski;
- keyingi qadam;
- Telegram message ID dalillari;
- analysis fingerprint.

Task faqat dalil va confidence yetarli bo‘lsa yoziladi.

| Signal | Task | Deadline |
|---|---|---|
| Mijoz javobsiz qolgan | `Mijozga javob bering` | 30 daqiqa |
| Qiziqish `hot`, uchrashuv yo‘q | `Uchrashuv vaqtini belgilang` | shu kun |
| Narx e’tirozi | `Moslashtirilgan taklif/KP yuboring` | 2 soat |
| “O‘ylab ko‘raman” | `Follow-up qiling` | 24 soat |
| Sotuvchi material va’da qilgan | `Va’da qilingan materialni yuboring` | 1 soat |
| `deal_risk=high` yoki score < 50 | `Rahbar bilan suhbatni ko‘rib chiqing` | shu kun |

Task `responsible_user_id` sifatida AmoCRM leadning mas’ul menejerini oladi. `OWNER_ID` hardcode ishlatilmaydi.

## Dedupe va idempotency

Idempotency key:

```text
sha256(lead_id + task_type + conversation_fingerprint)
```

Yangi task yozilishidan oldin:

- shu lead uchun ochiq bir xil task qidiriladi;
- lokal task audit jadvalida idempotency key tekshiriladi;
- task mavjud bo‘lsa yangi task yozilmaydi, note yangilanadi;
- yozuv muvaffaqiyatsiz bo‘lsa bir xil key bilan retry qilinadi.

## Write verification

AmoCRM POST muvaffaqiyatli qaytgani yakuniy success hisoblanmaydi.

Task yoki note yozilgandan keyin tizim:

1. AmoCRM’dan entityni qayta o‘qiydi;
2. task ID, text, responsible user va deadline mosligini tekshiradi;
3. note fingerprint mavjudligini tekshiradi;
4. verification natijasini audit logga yozadi;
5. mismatch bo‘lsa Telegram admin alert yuboradi va auto mode uchun shu dialogni vaqtincha bloklaydi.

## Rollout rejimlari

### Shadow mode

- Tahlil qilinadi.
- Dashboard va Telegram admin digestga natija keladi.
- AmoCRM task/note yozilmaydi.

### Approval mode

- AmoCRM note avtomatik yozilishi mumkin.
- Task owner/sales lead tasdiqlagandan keyin yoziladi.
- Inline actions: `Tasdiqlash`, `Tahrirlash`, `Bekor qilish`.

### Auto mode

Faqat quyidagi holatda task avtomatik yoziladi:

- CRM matching confidence ≥ 0.85;
- analysis confidence ≥ 0.80;
- task turi allowlist ichida;
- dublikat yo‘q;
- source health `healthy`;
- suhbat shaxsiy filterlardan o‘tgan.

Default production rejimi: `shadow`.

## Xatolar va degradatsiya

- SalesCoach API ishlamasa: suhbat queue’da qoladi, task yozilmaydi.
- AmoCRM token ishlamasa: tahlil saqlanadi, write retry queue’ga tushadi.
- Telegram userbot ishlamasa: source health `unhealthy`, fake zero ko‘rsatilmaydi.
- LLM JSON invalid bo‘lsa: schema retry bir marta; yana invalid bo‘lsa manual review.
- CRM mapping noaniq bo‘lsa: auto mode taqiqlanadi.

## Kuzatuv va audit

Har bir run uchun quyidagilar saqlanadi:

- hashed conversation ID;
- lead ID;
- manager ID;
- analysis fingerprint;
- source message IDs;
- score va confidence;
- recommended task type;
- rollout mode;
- approval actor;
- AmoCRM task/note ID;
- verification status;
- failure code.

Dashboardda real source badge, `last_synced_at`, confidence va evidence mavjud bo‘ladi. Synthetic/fake ko‘rsatkich ishlatilmaydi.

## Fayl chegaralari

- `src/services/core/telegram_salescoach.py`: filtering, batching, fingerprint, orchestration.
- `src/services/core/salescoach_sync.py`: conversation analysis HTTP client.
- `src/services/core/crm/salescoach_task_writer.py`: AmoCRM note/task, responsible manager, dedupe, verification.
- `src/api/routes/sales_quality.py`: Telegram conversation ingest/read endpoints.
- `salescoach-ai/apps/api/src/negotiations/*`: analyze endpoint va schema.
- `salescoach-ai/apps/worker/src/services/*`: scoring implementation.
- `tests/test_telegram_salescoach.py`: filters, batching, fingerprint.
- `tests/test_salescoach_task_writer.py`: responsible manager, dedupe, verification.
- TypeScript tests: API schema va scoring contract.

`src/main.py`ga katta biznes logika qo‘shilmaydi; faqat orchestration hook ulanadi.

## Test va acceptance criteria

- Shaxsiy/oila papkasidagi chat tahlil qilinmaydi.
- Ichki jamoa va bot chatlari chiqarib tashlanadi.
- Real biznes DM AmoCRM lead bilan to‘g‘ri bog‘lanadi.
- SalesCoach natijasi schema validationdan o‘tadi.
- Umumiy score category score’lar yig‘indisiga mos keladi.
- Task leadning `responsible_user_id` menejeriga tushadi.
- Bir xil fingerprint uchun dublikat task ochilmaydi.
- Past confidence auto write qilmaydi.
- Approval mode taskni tasdiqsiz yozmaydi.
- Task/note yozilgandan keyin verifier AmoCRM’dan qayta topadi.
- Xabar matni va maxfiy credential logga chiqmaydi.
- Python: `pytest -q` va `bandit -r src/ -ll` toza.
- TypeScript: `tsc --noEmit` va tegishli unit testlar toza.

## Production safety

- Telegram userbot faqat Oracle VM’da ishlaydi.
- Yangi Telegram session ochilmaydi.
- MCP yoki SalesCoach komponenti Telethon session’ga bevosita egalik qilmaydi.
- Feature flags: `TELEGRAM_SALESCOACH_ENABLED`, `TELEGRAM_SALESCOACH_MODE=shadow|approval|auto`.
- Rollback uchun flagni o‘chirish yetarli bo‘ladi.
