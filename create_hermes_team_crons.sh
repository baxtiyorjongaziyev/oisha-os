#!/bin/bash
set -euo pipefail
H=/home/hermes/.local/bin/hermes
T=telegram:-1003792973489
$H cron create '0 9 * * *' --name 'ertalab-standup' --deliver "$T" --reasoning-effort low --continuity \
  'Har ish kuni soat 09:00 Asia/Tashkent da Biznes asisstant guruhida muloyim ertalabki standup otkaz. AmoCRM, Airtable, Moizvonki, Telegram, Google Calendar, Google Drive, Gmail, Sheets, Docs, Todoist va Oisha-OS dagi mavjud malumotlarni faqat oqish rejimida tekshir. Har bir xodim uchun bugungi aniq vazifa, deadline, kutilgan natija va mavjud blokerni fakt bilan yoz. Manbasi yoki sanasi yoq malumotni fakt deb yozma. Vazifani xodim nomi bilan individual va muloyim ber. Tashqi tizimlarda hech qanday yozuv ozgartirma.'
$H cron create '30 18 * * *' --name 'kunlik-fakt-hisoboti' --deliver "$T" --reasoning-effort low --continuity \
  'Har ish kuni soat 18:30 Asia/Tashkent da Biznes asisstant guruhida kunlik fakt-hisobot ber. AmoCRM, Airtable, Moizvonki, Telegram, Google Calendar, Google Drive, Gmail, Sheets, Docs, Todoist va Oisha-OS ni faqat oqish rejimida solishtir. Har bir xodim nima qilganini faqat kamida bitta manba bilan tasdiqlangan dalil asosida yoz: bajarilgan ish, manba, vaqt va natija. Tasdiqlanmagan ishni bajarildi deb yozma. Har bir tasdiqlangan natija uchun xodimni individual, samimiy va muloyim tabrikla hamda keyingi qadamga motivatsiya ber. Javobsizlik, deadline otishi yoki blokerni muloyim eskalatsiya qil. Hech qanday tashqi tizimda yozuv ozgartirma.'
