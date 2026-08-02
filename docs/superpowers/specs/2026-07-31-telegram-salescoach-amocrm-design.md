# Telegram SalesCoach → AmoCRM Design

## Maqsad

Oracle VM’dagi Telegram userbot ko‘ra oladigan biznes dialoglarini tahlil qilish, sotuvchi ishini 100 ballik SalesCoach mezonida baholash va dalil yetarli bo‘lsa AmoCRM’dagi tegishli lead uchun aniq keyingi vazifani yozish.

Tizim mijozga o‘zi xabar yubormaydi. U faqat baho, tavsiya, tayyor javob varianti, AmoCRM note va task beradi.

## Scope

Birinchi versiya quyidagilarni qamrab oladi:

- Telegram private DM dialoglari;
- faqat AmoCRM lead/contact bilan ishonchli bog‘langan suhbatlar;
- matnli xabarlar va mavjud voice-note transcriptlari;
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
- shaxsiy/oila/do‘st dialoglarini tahlil qilish;
- yangi audio transcription engine yozish.

## Asosiy arxitektura

1. `src/handlers/message_handler.py` Telegram eventni qabul qiladi va orchestration hookni chaqiradi.
2. Yangi `src/services/core/telegram_salescoach.py` dialogni filtrlash, batching, fingerprint, CRM mapping va orchestration bilan shug‘ullanadi.
3. `src/services/core/salescoach_sync.py` SalesCoach API’ning yangi `/v1/negotiations/analyze-conversation` endpointiga strukturali payload yuboradi.
4. `salescoach-ai/apps/api` kiruvchi payloadni validatsiya qiladi va scoring service’ga uzatadi.
5. Scoring service LLM javobini schema bo‘yicha tekshiradi va structured analysis qaytaradi.
6. Oisha tahlilni yangi `conversation_analyses` jadvaliga saqlaydi. `call_analyses` ishlatilmaydi.
7. Yangi `src/services/core/crm/salescoach_task_writer.py` leadning `responsible_user_id` qiymatini ishlatadi, dublikatni tekshiradi, note/task yozadi va qayta o‘qib tasdiqlaydi.
8. Approval mode’da owner yoki `SALESCOACH_APPROVER_IDS` ro‘yxatidagi foydalanuvchi Telegram inline action orqali taskni tasdiqlaydi.

## Telegram dialog filtrlari

Tahlilga faqat quyidagi shartlarning barchasi mos kelgan dialog kiradi:

- private user chat;
- bot emas;
- ownerning Saved Messages’i emas;
- `PERSONAL_FOLDER_KEYWORDS` orqali shaxsiy/oila/do‘st papkasiga kirmaydi;
- `INTERNAL_TEAM_TELEGRAM_IDS` ro‘yxatiga kirmaydi;
- AmoCRM contact/lead bilan telefon, username yoki oldindan saqlangan mapping orqali bog‘langan;
- oxirgi batchda kamida bitta incoming va bitta outgoing xabar bor;
- yangi xabarlar oldingi `conversation_fingerprint` bilan bir xil emas.

Loglarda xabar matni, telefon, username, token yoki session string yozilmaydi. Faqat hashed identifiers, entity ID va event holati yoziladi.

## Batching va trigger

Har bir dialog uchun persistent buffer yuritiladi.

Tahlil quyidagi holatlardan birida ishga tushadi:

- yangi xabardan keyin 10 daqiqa jimlik;
- mijoz savol yoki e’tiroz bilan yakunlagan va 15 daqiqa javobsiz qolgan;
- sotuvchi uchrashuv, KP, material yoki follow-up va’da qilgan;
- owner `/sales_audit` orqali qo‘lda ishga tushirgan.

Default batch: oxirgi 50 ta matnli xabar yoki oxirgi 7 kunlik faol blok, qaysi biri kichik bo‘lsa. Voice note uchun faqat tizimda oldindan mavjud transcript qo‘shiladi; audio fayl LLM promptiga yuborilmaydi.

## CRM matching

Matching ustuvorligi:

1. saqlangan `telegram_user_id → contact_id/lead_id` mapping;
2. verified telefon raqami;
3. verified Telegram username custom field;
4. contact note yoki oldingi Telegram sync evidence;
5. nom bo‘yicha taxmin faqat approval queue uchun, auto task uchun emas.

Auto write uchun CRM matching confidence kamida `0.85` bo‘lishi kerak. `0.60–0.84` oralig‘i approval mode’ga tushadi. `0.60`dan past bo‘lsa task/note yozilmaydi va dashboardda “bog‘lanmagan” deb ko‘rsatiladi.

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

Kategoriya range’lari yuqoridagi maksimal ballardan oshmaydi. Server `overall_score`ni kategoriya ballari yig‘indisidan qayta hisoblaydi; LLM yuborgan umumiy ballga ishonmaydi.

## `conversation_analyses` storage contract

Har bir unique `(lead_id, conversation_fingerprint)` uchun bitta record saqlanadi:

- `analysis_id`;
- `lead_id`, `contact_id`, `manager_id`;
- hashed `telegram_chat_id`;
- `conversation_fingerprint`;
- `source_message_ids` JSON;
- `scores` JSON va `overall_score`;
- `strengths`, `mistakes`, `missed_questions` JSON;
- `client_intent`, `objections`, `deal_risk`;
- `next_best_action`, `recommended_reply`, `recommended_tasks` JSON;
- `analysis_confidence`, `crm_match_confidence`;
- `rollout_mode`, `approval_status`;
- `amocrm_note_id`, `amocrm_task_ids` JSON;
- `verification_status`, `failure_code`;
- `analyzed_at`, `created_at`, `updated_at`.

Transcriptning to‘liq matni bu jadvalga saqlanmaydi. Evidence sifatida Telegram message ID’lari saqlanadi.

## AmoCRM note va task qoidalari

Har bir valid tahlil leadga bitta strukturali note yozadi, `shadow` mode bundan mustasno. Note tarkibi:

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
| Mijoz javobsiz qolgan | `Mijozga javob bering` | hozir + 30 daqiqa |
| Qiziqish `hot`, uchrashuv yo‘q | `Uchrashuv vaqtini belgilang` | 18:00 Asia/Tashkent; tahlil 17:00dan keyin bo‘lsa keyingi ish kuni 10:00 |
| Narx e’tirozi | `Moslashtirilgan taklif/KP yuboring` | hozir + 2 soat |
| “O‘ylab ko‘raman” | `Follow-up qiling` | hozir + 24 soat |
| Sotuvchi material va’da qilgan | `Va’da qilingan materialni yuboring` | hozir + 1 soat |
| `deal_risk=high` yoki score < 50 | `Rahbar bilan suhbatni ko‘rib chiqing` | 18:00 Asia/Tashkent; tahlil 17:00dan keyin bo‘lsa keyingi ish kuni 10:00 |

Task `responsible_user_id` sifatida AmoCRM leadning mas’ul menejerini oladi. `OWNER_ID` hardcode ishlatilmaydi. Leadning mas’ul menejeri bo‘lmasa task approval queue’ga tushadi va owner tasdiqlaganda ownerga biriktiriladi.

## Dedupe va idempotency

Idempotency key:

```text
sha256(lead_id + task_type + conversation_fingerprint)
```

Yangi task yozilishidan oldin:

- shu lead uchun ochiq bir xil task qidiriladi;
- lokal task audit recordida idempotency key tekshiriladi;
- task mavjud bo‘lsa yangi task yozilmaydi, note yangilanadi;
- yozuv muvaffaqiyatsiz bo‘lsa bir xil key bilan retry qilinadi;
- retry yangi task emas, aynan oldingi operationni davom ettiradi.

## Write verification

AmoCRM POST muvaffaqiyatli qaytgani yakuniy success hisoblanmaydi.

Task yoki note yozilgandan keyin tizim:

1. AmoCRM’dan entityni qayta o‘qiydi;
2. task ID, text, responsible user va deadline mosligini tekshiradi;
3. note fingerprint mavjudligini tekshiradi;
4. verification natijasini `conversation_analyses`ga yozadi;
5. mismatch bo‘lsa Telegram admin alert yuboradi va shu conversation uchun auto write’ni bloklaydi.

## Rollout rejimlari

### Shadow mode

- Tahlil qilinadi va `conversation_analyses`ga yoziladi.
- Dashboard va Telegram admin digestga natija keladi.
- AmoCRM task/note yozilmaydi.

### Approval mode

- Valid CRM mapping bo‘lsa AmoCRM note avtomatik yoziladi.
- Task `SALESCOACH_APPROVER_IDS`dan biri tasdiqlagandan keyin yoziladi.
- Inline actions: `Tasdiqlash`, `Tahrirlash`, `Bekor qilish`.
- Approval 24 soatda olinmasa proposal `expired` bo‘ladi.

### Auto mode

Faqat quyidagi holatda task avtomatik yoziladi:

- CRM matching confidence ≥ 0.85;
- analysis confidence ≥ 0.80;
- task turi allowlist ichida;
- dublikat yo‘q;
- source health `healthy`;
- suhbat barcha privacy filterlardan o‘tgan.

Default production rejimi: `shadow`.

## Xatolar va degradatsiya

- SalesCoach API ishlamasa: suhbat retry queue’da qoladi, task/note yozilmaydi.
- AmoCRM token ishlamasa: tahlil saqlanadi, write retry queue’ga tushadi.
- Telegram userbot ishlamasa: source health `unhealthy`, fake zero ko‘rsatilmaydi.
- LLM JSON invalid bo‘lsa: schema retry bir marta; yana invalid bo‘lsa `manual_review`.
- CRM mapping noaniq bo‘lsa: auto mode taqiqlanadi.
- Har bir retry exponential backoff bilan maksimum 5 marta bajariladi; undan keyin admin alert yuboriladi.

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

- `src/services/core/telegram_salescoach.py`: filtering, batching, fingerprint, CRM mapping va orchestration.
- `src/services/core/salescoach_sync.py`: conversation analysis HTTP client.
- `src/services/core/crm/salescoach_task_writer.py`: AmoCRM note/task, responsible manager, dedupe va verification.
- `src/services/core/telegram_salescoach_store.py`: `conversation_analyses` schema va barcha persistence yozuvlari uchun yagona boundary; raw connection boshqa qatlamlarga chiqmaydi.
- `src/api/routes/sales_quality.py`: Telegram conversation read/ingest endpoints.
- `salescoach-ai/apps/api/src/negotiations/*`: analyze endpoint va schema.
- `salescoach-ai/apps/worker/src/services/*`: scoring implementation.
- `tests/test_telegram_salescoach.py`: filters, batching, fingerprint va confidence gates.
- `tests/test_salescoach_task_writer.py`: responsible manager, dedupe, approval va verification.
- TypeScript tests: API schema va scoring contract.

`src/main.py`ga katta biznes logika qo‘shilmaydi; faqat orchestration hook ulanadi.

## Test va acceptance criteria

- Shaxsiy/oila papkasidagi chat tahlil qilinmaydi.
- Ichki jamoa va bot chatlari chiqarib tashlanadi.
- Real biznes DM AmoCRM lead bilan to‘g‘ri bog‘lanadi.
- SalesCoach natijasi schema validationdan o‘tadi.
- Umumiy score kategoriya score’lari yig‘indisidan serverda hisoblanadi.
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
- Default: `TELEGRAM_SALESCOACH_ENABLED=0`, `TELEGRAM_SALESCOACH_MODE=shadow`.
- Rollback uchun `TELEGRAM_SALESCOACH_ENABLED=0` qilish yetarli bo‘ladi.
