# Card watch — karta yuborildi → toʻlov kuzatuvchisi

Modul: `src/services/core/card_watch/`, loop: `src/schedulers/card_payment_watch_scheduler.py`.
Har soatda (quiet hours 23:00–07:00 va yakshanbadan tashqari):

1. Har menejerning **alohida** Telegram sessiyasi bilan shaxsiy chatlar va `X | Jon Branding`
   guruhlaridagi oʻzi yuborgan xabarlardan kompaniya kartasini qidiradi.
2. Egasi aʼzo boʻlgan `X | Jon Branding` guruhlarini prod klient orqali **shu jarayon ichida**
   oʻqiydi (ikkinchi ulanish ochilmaydi, `AuthKeyDuplicatedError` xavfi yoʻq).
3. Airtable `Tranzaksiyalar` (`app8xoyx1XCumYFXV` / `tblrqxqIzyrvg7XpQ`) kirimlari bilan
   solishtiradi: mijoz/brend nomi yoki summa (±2%), sana ≥ karta yuborilgan kun − 1.
4. `CARD_WATCH_GRACE_DAYS` (standart 2) kun ichida kirim boʻlmasa, sotuv guruhida
   (`-1003854308552`) menejer topicʼiga bir marta eslatma yuboradi.
5. Har kuni `CARD_WATCH_REPORT_HOUR` (standart 18) dan keyin har menejerga oʻz topicʼida
   alohida hisobot: karta yuborilgan / toʻlagan / kutilmoqda roʻyxati.

Topiclar: Rayxona 2976, Mumtozmaxal 120, Shahnoza 122, Hasanboy 17141, Baxtiyorjon (egasi) 118 —
yuboruvchisi aniqlanmagan guruh xabarlari shu yerga.

Holat: `data/card_watch_state.json` — har yozuvda `manager` maydoni (menejer boʻyicha ajratilgan
kuzatuv roʻyxati), `paid`, `reminded_at`, mijoz, summa. Airtable `Tranzaksiyalar` ga yozilmaydi va
view yaratilmaydi; kerak boʻlsa `Sotuvchi` maydoni boʻyicha har menejerga view qoʻlda ochiladi.

## Sozlamalar (env)

| Kalit | Standart | Izoh |
|---|---|---|
| `CARD_WATCH_ENABLED` | `0` | `1` boʻlsa loop ishlaydi |
| `CARD_WATCH_CARDS` | ikki kompaniya kartasi | vergul bilan |
| `CARD_WATCH_GRACE_DAYS` | `2` | eslatmagacha kun |
| `CARD_WATCH_REPORT_HOUR` | `18` | kunlik hisobot soati (Toshkent) |
| `CARD_WATCH_LOOKBACK_DAYS` | `14` | Telegram tarixida qancha orqaga qarash |
| `CARD_WATCH_OWNER_GROUPS` | `1` | egasi guruhlarini skan qilish |
| `CARD_WATCH_MANAGERS` | 4 menejer | JSON: `[{"key","name","username","topic_id"}]` |
| `CARD_WATCH_SESSION_<KEY>` | — | menejer sessiyasi (**sir**, faqat serverda) |

Sessiya kalitlari: `CARD_WATCH_SESSION_SHAHNOZA`, `_RAYXONA`, `_MUMTOZMAXAL`, `_HASANBOY`.
Ular `USERBOT_SESSION_STRING` / `TELEGRAM_MCP_SESSION_STRING` bilan bir xil boʻlsa, kod ularni rad etadi.

## Menejer login (bir martalik, serverda)

```bash
ssh hetzner-oisha
cd /home/deploy/oisha-os    # oisha.service WorkingDirectory (tekshiring: systemctl cat oisha)
set -a; . ./.env; set +a    # API_ID / API_HASH uchun
python scripts/card_watch_login.py --manager shahnoza
```

- Menejer telefon raqamini va Telegramʼga kelgan kodni **oʻzi** kiritadi (2FA boʻlsa paroli ham).
- Sessiya faqat `/etc/oisha/card_watch.env` ga (0600) yoziladi, ekranga chiqmaydi, repoga tushmaydi.
- Menejer Telegram → Settings → Devices da yangi qurilmani koʻradi; uni oʻchirsa, loginni qaytarish kerak.

## Deploy

1. PR merge → odatiy deploy (`oracle-deploy.yml` / serverda `git pull`).
2. `oisha.service` ga env faylni ulash (bir marta):
   ```bash
   sudo mkdir -p /etc/systemd/system/oisha.service.d
   printf '[Service]\nEnvironmentFile=-/etc/oisha/card_watch.env\n' | sudo tee /etc/systemd/system/oisha.service.d/card-watch.conf
   sudo systemctl daemon-reload
   ```
3. Har menejer uchun login skripti (yuqorida).
4. `/etc/oisha/card_watch.env` ga `CARD_WATCH_ENABLED=1` qoʻshing.
5. `sudo systemctl restart oisha` → `journalctl -u oisha -f | grep CARD_WATCH`.

Oʻchirish: `CARD_WATCH_ENABLED=0` va restart. Sessiyani bekor qilish: env fayldan qatorni
oʻchirish + menejer Telegram Devices dan qurilmani chiqarib yuboradi.
