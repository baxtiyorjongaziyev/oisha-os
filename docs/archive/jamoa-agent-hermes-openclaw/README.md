# Arxiv: Hermes + OpenClaw jamoa agenti (bekor qilingan, 2026-10-26)

**Holat:** bekor qilingan. Hech qachon serverga o'rnatilmagan.

## Nima edi

Jamoa Telegram guruhi uchun Oisha'dan alohida ikki bot: **Hamroh** (Hermes Agent) va
**Navbatchi** (OpenClaw). Ular Contabo VPS'ga bash o'rnatuvchi (`ornatish.sh`) orqali
o'rnatilishi kerak edi.

## Nega bekor qilindi (owner qarori, 2026-10-26)

- Prod VPS'ga begona servislar, alohida Node 24 va qo'shimcha portlar qo'shish shart emas.
- BotFather'da yangi botlar ochish va bot-to-bot sozlash kerak emas: Oisha (@jonairobot) jamoa
  guruhida allaqachon bor.
- Oisha-OS'da scheduler, AI router va Telegram infratuzilmasi allaqachon ishlab turibdi.

## O'rniga nima qilindi

Funksiya Oisha-OS'ning o'ziga qo'shildi (branch `feat/jamoa-ritm-hamroh`):

| Qism | Fayl |
|---|---|
| Jadval (09:00 start, 17:30 kun yakuni, juma retro va egaga tahlil) | `src/schedulers/jamoa_ritm_scheduler.py` |
| Guruhni kuzatish va @mention'ga javob | `src/handlers/jamoa_hamroh.py` |
| Sozlamalar, xotira, matnlar, AI | `src/services/core/jamoa_ritm/` |
| Testlar | `tests/test_jamoa_ritm.py` |

## Shu papkada

- `JADVAL.md` — dastlabki jadval va uning sabablari. Jadval Oisha integratsiyasida o'zgarishsiz qoldi.
  Ichidagi `hermes/cron.sh` va `openclaw/cron.sh` havolalari endi mavjud emas.
- `hamroh-persona.md` — Hamroh personasining asl matni. Uning qisqartirilgan versiyasi
  `src/services/core/jamoa_ritm/texts.py` dagi `HAMROH_SYSTEM` da ishlatiladi.

To'liq bash o'rnatuvchi (`ornatish.sh`, `tekshirish.sh`, `lib/tg.py` va testlari) faqat lokal
`feat/jamoa-agent-contabo` branch'idagi `197d3455` commit'ida saqlangan. U push qilinmagan.
