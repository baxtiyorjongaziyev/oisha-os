# Jon CRM — amoCRM Professional paritet rejasi (Twenty asosida)

Qaror (owner, 2026-10-20): amoCRM "Профессиональный" (1 799 ₽) tarifining barcha
funksiyalari + 4 qo'shimcha paket. Asos — self-hosted Twenty (`crm.jonbranding.uz`).

## Mavjud holat (tekshirilgan 2026-10-20)

| Narsa | Joy | Holat |
|---|---|---|
| Twenty server | `crm.jonbranding.uz` → `127.0.0.1:3000` (`deploy/crm.jonbranding.uz.conf`) | `/healthz` = 200 |
| Twenty REST client | `src/services/core/crm/twenty_client.py` | people, opportunities, notes, tasks |
| amoCRM → Twenty migratsiya | `scripts/migrate_amocrm_to_twenty.py` | kontakt, bitim, izoh, qo'ng'iroq, vazifa; idempotent, `--resume`, `--dry-run` |
| Dialer / Kanban | `/sotuv`, `/dialer` (Oisha, :8080) | ishlaydi |
| Moizvonki → Twenty | `src/api/routes/twenty_moizvonki.py` | qo'ng'iroq timeline'ga |
| Doimiy sinxron | `deploy/oisha-crm-sync.service` → `src.workers.run_crm_sync` | tekshirilmagan |

## Bosqichlar

### 1. Asos (data paritet)
- Kompaniyalar (amo `companies` → Twenty `companies`), kontakt/bitim bog'lash.
- Bir nechta voronka: har amo pipeline → Twenty `opportunity.pipeline` select + bosqichlar.
- Custom maydonlar: amo `custom_fields` → Twenty metadata API (`/rest/metadata/fields`) avtomatik yaratish.
- Teglar: multi-select maydon.
- Fayllar: amo attachment → Twenty attachments.
- Rollar: Twenty workspace roles (admin / menejer / ko'ruvchi), "faqat o'z bitimlari".

### 2. Yagona inbox
Telegram (userbot + bot), Instagram DM, WhatsApp → bitim timeline'iga xabar; CRM'dan javob.

### 3. Avtomatika
- Digital Pipeline: bosqich triggeri → vazifa, xabar, maydon o'zgarishi (Twenty workflows + Oisha webhook).
- Salesbot: Oisha agent_loop orqali bot ssenariylari.

### 4. Telefoniya va hisobotlar
Moizvonki (bor), voronka konversiyasi, menejer KPI, yo'qotish sabablari, kunlik hisobot.

### 5. Qo'shimcha paketlar
| amo paketi | Bizda |
|---|---|
| AI agent tokenlari | free_ai_router orqali agentlar; token hisobi `ai_usage` jadvalida, kvota |
| API limit / filtrlash | Oisha API gateway: rate-limit, kengaytirilgan filtr endpointlari |
| Super-maydonlar | formula, bog'langan, hisoblanadigan maydonlar (Twenty computed + worker) |
| Fayl xotirasi | Twenty storage → MinIO/S3, kvota monitoringi |

## Qoidalar
- Sirlar (`TWENTY_API_KEY`, amo token) faqat `.env`; hujjatga yozilmaydi.
- Migratsiya avval `--dry-run`, keyin real.
- amoCRM o'chirilmaydi: paritet tasdiqlanmaguncha parallel ishlaydi.
