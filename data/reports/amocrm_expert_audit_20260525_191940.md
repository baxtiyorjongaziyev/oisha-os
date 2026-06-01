# amoCRM Expert Audit - 2026-05-25 19:19 (Asia/Tashkent)

Account: **Jon Branding Agency** (`jonbrandingagency`)
Scope: 487 leads, 6 pipelines, 54 open tasks, 4 users fetched. Read-only audit.

## Executive Summary
- Active leads: **474**
- Won leads: **3**
- Lost leads: **10**
- Created today: **3**
- Created last 7 days: **31**
- Active without open task: **424**
- Active stale 24h+: **357**
- Active stale 72h+: **292**
- Overdue open tasks: **40**
- Active without contact: **21**
- Active price = 0: **438**
- Active without tags: **8**
- Duplicate contact groups: **8**

## Pipeline Health
| Pipeline | Total | Active | Won | Lost | No task | 24h+ stale | 72h+ stale | No contact | Price 0 | No tags |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Hunter bosqichlari | 381 | 374 | 1 | 6 | 341 | 273 | 223 | 17 | 378 | 3 |
| Farmer bosqichlari | 58 | 56 | 1 | 1 | 49 | 49 | 41 | 2 | 33 | 3 |
| Closer bosqichlari | 33 | 29 | 1 | 3 | 22 | 25 | 20 | 1 | 30 | 1 |
| Sifat Nazorati bosqichlari | 15 | 15 | 0 | 0 | 12 | 10 | 8 | 1 | 9 | 1 |
| Reactivation bosqichlari | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Partnership bosqichlari | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## Bottleneck Statuses
| Pipeline | Status | Active | No task | 24h+ | 72h+ | 7d+ | Median age h | Max age h |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Hunter bosqichlari | Yangi so'rov | 238 | 228 | 144 | 104 | 94 | 25.9 | 1369.7 |
| Hunter bosqichlari | Uchrashuv belgilandi | 83 | 70 | 81 | 74 | 74 | 1173.6 | 4010.5 |
| Hunter bosqichlari | Bog'lanib bo'lmadi | 26 | 24 | 26 | 25 | 24 | 1146.0 | 3796.4 |
| Hunter bosqichlari | Muloqot boshlandi | 27 | 19 | 22 | 20 | 18 | 954.3 | 3743.0 |
| Farmer bosqichlari | Topshirish & 50% To'lov | 21 | 20 | 21 | 19 | 18 | 1172.1 | 1176.7 |
| Farmer bosqichlari | Taqdimot & Pravkalar | 15 | 14 | 13 | 10 | 10 | 315.5 | 1172.2 |
| Sifat Nazorati bosqichlari | NPS / Fikr olish | 15 | 12 | 10 | 8 | 8 | 223.2 | 930.3 |
| Closer bosqichlari | Muzokara / Shartnoma | 14 | 10 | 10 | 8 | 8 | 552.7 | 1173.7 |
| Farmer bosqichlari | Loyiha va Brief | 9 | 9 | 9 | 6 | 6 | 1126.8 | 1174.0 |
| Closer bosqichlari | Konsultatsiya o‘tdi | 9 | 8 | 9 | 7 | 6 | 930.3 | 1175.9 |
| Farmer bosqichlari | Ish jarayonida | 11 | 6 | 6 | 6 | 5 | 74.9 | 1171.9 |
| Closer bosqichlari | Prezentatsiya & KP | 5 | 3 | 5 | 4 | 2 | 148.4 | 954.3 |
| Closer bosqichlari | 50% Avans olindi | 1 | 1 | 1 | 1 | 0 | 148.4 | 148.4 |

## Manager Load
| Manager | Active leads | Total leads | Open tasks | Overdue tasks |
|---|---:|---:|---:|---:|
| Baxtiyorjon Gaziyev | 474 | 487 | 54 | 40 |

## P0/P1 Recommendations
- **P0 Har bir active leadga ochiq task shart**: 424 ta active leadda ochiq task yo'q. Action: Oisha scheduler: statusga kirganda task yaratish va task yopilmasa manager/escalation.
- **P0 24 soatdan oshgan leadlarni tiriltirish**: 357 ta active lead 24 soatdan ko'p yangilanmagan. Action: Yangi so'rov uchun 15 daqiqa, Birinchi kontakt uchun 2 soat, Sifatli lead uchun 24 soat SLA qo'yish.
- **P0 Overdue tasklarni yopish yoki qayta rejalash**: 40 ta ochiq task muddati o'tgan. Action: Kuniga 2 marta task debt digest: mas'ul, lead, muddati va keyingi harakat.
- **P1 Kontaktsiz leadlarni tozalash**: 21 ta active leadda kontakt yo'q. Action: Telefon/Telegram yo'q bo'lsa 'Needs data' tag va task; 48 soatda topilmasa Lost reason.
- **P1 Narx/forecast intizomi**: 438 ta active leadda price 0. Action: Closer bosqichlariga o'tishda taxminiy deal value majburiy bo'lsin.
- **P1 Segment teglari yetishmayapti**: 8 ta active leadda teg yo'q. Action: Oisha call/text analyzer: Shaxsiy/Oila/Jamoa/Mijoz/Spam/Qayta aloqa/Premium kabi taglarni avtomatik qo'ysin.
- **P1 Duplikat kontaktlardan kelgan sdelkalarni tekshirish**: 8 ta kontakt bir nechta leadga bog'langan. Action: Avtomatik merge emas; avval Oisha duplicate note + mas'ulga review task.
- **P2 Custom field modelini to'ldirish**: Manba/sifat/transcript/next-step kabi konseptlar fieldlarda to'liq ko'rinmadi. Action: Lead Source, Lead Quality, Call Summary, Transcript URL/Text, Next Step, Segment fieldlarini standartlashtirish.

## Top Stale Active Leads
| Lead | Pipeline | Status | Responsible | Updated age h | Updated | URL |
|---|---|---|---|---:|---|---|
| Звонок на +998774001007 (Отвечен) | Hunter bosqichlari | Uchrashuv belgilandi | Baxtiyorjon Gaziyev | 4010.5 | 2025-12-09 16:48 | https://jonbrandingagency.amocrm.ru/leads/detail/39856795 |
| Звонок на +998957770202 (Не дозвонился) | Hunter bosqichlari | Uchrashuv belgilandi | Baxtiyorjon Gaziyev | 3937.2 | 2025-12-12 18:05 | https://jonbrandingagency.amocrm.ru/leads/detail/40034041 |
| Звонок на +998972333333 (Не дозвонился) | Hunter bosqichlari | Uchrashuv belgilandi | Baxtiyorjon Gaziyev | 3887.8 | 2025-12-14 19:29 | https://jonbrandingagency.amocrm.ru/leads/detail/40110969 |
| Звонок от +998200221361 (Пропущен) | Hunter bosqichlari | Uchrashuv belgilandi | Baxtiyorjon Gaziyev | 3797.4 | 2025-12-18 13:52 | https://jonbrandingagency.amocrm.ru/leads/detail/40267797 |
| Звонок на +998910076700 (Не дозвонился) | Hunter bosqichlari | Uchrashuv belgilandi | Baxtiyorjon Gaziyev | 3796.6 | 2025-12-18 14:44 | https://jonbrandingagency.amocrm.ru/leads/detail/40087359 |
| Заявка от (Abdurafiq Aka TN4 Sam) | Hunter bosqichlari | Uchrashuv belgilandi | Baxtiyorjon Gaziyev | 3796.4 | 2025-12-18 14:56 | https://jonbrandingagency.amocrm.ru/leads/detail/40270343 |
| Звонок от +998995377098 (Пропущен) | Hunter bosqichlari | Uchrashuv belgilandi | Baxtiyorjon Gaziyev | 3796.4 | 2025-12-18 14:58 | https://jonbrandingagency.amocrm.ru/leads/detail/40270399 |
| Звонок на +998880200003 (Отвечен) | Hunter bosqichlari | Bog'lanib bo'lmadi | Baxtiyorjon Gaziyev | 3796.4 | 2025-12-18 14:58 | https://jonbrandingagency.amocrm.ru/leads/detail/38592015 |
| Заявка от (Shuhrat Aka Buhoriy Mebel Samarqanda TN4) | Hunter bosqichlari | Uchrashuv belgilandi | Baxtiyorjon Gaziyev | 3796.2 | 2025-12-18 15:08 | https://jonbrandingagency.amocrm.ru/leads/detail/40270751 |
| Звонок на +998339963630 (Не дозвонился) | Hunter bosqichlari | Uchrashuv belgilandi | Baxtiyorjon Gaziyev | 3796.1 | 2025-12-18 15:10 | https://jonbrandingagency.amocrm.ru/leads/detail/40270833 |
| Заявка от (Shaxboz Uktamov TN4) | Hunter bosqichlari | Uchrashuv belgilandi | Baxtiyorjon Gaziyev | 3763.4 | 2025-12-19 23:54 | https://jonbrandingagency.amocrm.ru/leads/detail/40318473 |
| Oybek Aka Deklorant +998911187007 | Hunter bosqichlari | Bog'lanib bo'lmadi | Baxtiyorjon Gaziyev | 3746.1 | 2025-12-20 17:12 | https://jonbrandingagency.amocrm.ru/leads/detail/36660307 |
| Musoxon aka Tuxumjon +998330103737 | Hunter bosqichlari | Muloqot boshlandi | Baxtiyorjon Gaziyev | 3743.0 | 2025-12-20 20:18 | https://jonbrandingagency.amocrm.ru/leads/detail/38453939 |
| Звонок на +998941232681 (Не дозвонился) | Hunter bosqichlari | Uchrashuv belgilandi | Baxtiyorjon Gaziyev | 1439.5 | 2026-03-26 19:50 | https://jonbrandingagency.amocrm.ru/leads/detail/39051653 |
| Звонок от +998900547494 (Пропущен) | Hunter bosqichlari | Uchrashuv belgilandi | Baxtiyorjon Gaziyev | 1377.3 | 2026-03-29 10:00 | https://jonbrandingagency.amocrm.ru/leads/detail/40493419 |

## Notes
- Audit read-only bajarildi: lead, status, task, tag yoki field o'zgartirilmadi.
- `get leads` default API natijasi asosida hisoblandi; arxiv/permission cheklovi bo'lsa, raqamlar CRM UI bilan farq qilishi mumkin.
- Full details JSON fileda saqlandi.
