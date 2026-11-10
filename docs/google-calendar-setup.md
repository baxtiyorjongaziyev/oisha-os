# Google Calendar integratsiyasi

Oisha Telegram suhbatidan uchrashuvni ajratib, Google Calendar tizimiga event yaratadi.
Vaqt oʻzgarsa eski event oʻchiriladi va yangisi kiritiladi.

## Ikkita yoʻl

**1-yoʻl — service account + ulashilgan kalendar (tavsiya, OAuthʼsiz).**
Service account oʻzining `primary` kalendariga ega emas, lekin egasi kalendarni
service account emailiga ulashsa, u oʻsha kalendarga event yozadi.
Bu yoʻlda brauzer ruxsati va `token.json` kerak emas.

**2-yoʻl — shaxsiy akkauntning OAuth tokeni (`token.json`).**
Service account yaratish imkoni boʻlmasa yoki eventlar aynan shaxsiy
akkauntning asosiy kalendarida koʻrinishi shart boʻlsa ishlatiladi.

## 1-yoʻl: service account bilan ulash

1. Service account JSON faylini serverga qoʻying:
   `/home/ubuntu/.secrets/service_account_calendar.json` (`chmod 600`).
2. Google Calendar'da kerakli kalendarni oching:
   **Settings and sharing -> Share with specific people -> Add people**.
   Email: service account manzili (`client_email`).
   Permission: **Make changes to events**.
3. Kalendar ID ni oling: **Settings and sharing -> Integrate calendar ->
   Calendar ID**.
4. `.env` ga yozing:

   ```text
   GOOGLE_CALENDAR_ID=<calendar-id>@group.calendar.google.com
   GOOGLE_CALENDAR_CREDENTIALS_PATH=service_account_calendar.json
   ```

5. Servisni restart qiling. Logda quyidagilar boʻlishi kerak:

   ```text
   [GCALENDAR OK] Service Account ulandi.
   [GCALENDAR] Kalendar ID: <calendar-id>
   ```

Deploy `service_account_calendar.json` ni `/home/ubuntu/.secrets/` dan
avtomatik nusxalaydi va `GOOGLE_` bilan boshlanadigan `.env` qatorlarini saqlaydi.

## Owner bajaradigan qadamlar (2-yoʻl, bir marta)

1. [Google Cloud Console](https://console.cloud.google.com/) da loyiha tanlang
   yoki yangi loyiha yarating.
2. **APIs & Services → Library** dan **Google Calendar API** ni yoqing.
3. **OAuth consent screen** ni sozlang:
   - User type: **External** (oddiy Gmail uchun) yoki **Internal** (Workspace).
   - Scope: `calendar.events`, `contacts`, `directory.readonly` (bitta token Calendar va Contacts uchun).
   - Test users ga eventlar tushadigan Google akkauntni qoʻshing.
4. **Credentials → Create credentials → OAuth client ID → Desktop app**.
   JSON faylni yuklab, lokal kompyuterda `credentials.json` deb saqlang.
5. Lokal kompyuterda tokenni yarating:

   ```powershell
   python scripts/google_calendar_auth.py `
     --client-secrets credentials.json `
     --token token.json
   ```

   Brauzer ochiladi. Eventlar tushadigan Google akkaunt bilan ruxsat bering.
6. `token.json` ni prod serverga qoʻying:

   ```bash
   scp token.json root@109.199.100.137:/home/ubuntu/oisha-os/token.json
   ssh root@109.199.100.137 "chown ubuntu:ubuntu /home/ubuntu/oisha-os/token.json && chmod 600 /home/ubuntu/oisha-os/token.json"
   ```

7. Servisni restart qiling va logni tekshiring:

   ```bash
   ssh root@109.199.100.137 "systemctl restart oisha-os.service && journalctl -u oisha-os.service -n 80 --no-pager | grep GCALENDAR"
   ```

   Kutilgan satrlar:

   ```text
   [GCALENDAR OK] Shaxsiy Google akkaunti (Token) ishga tushdi.
   [GCALENDAR] Kalendar ID: primary
   ```

## Tekshiruv

1. Telegramda Oisha bilan uchrashuv vaqtini kelishing:
   `"Ertaga soat 15:00 da logo boʻyicha uchrashuvga kelolasizmi?"` → `"Ha, kelaman"`.
2. Kalendarda event paydo boʻlishi kerak. Sarlavha formati:
   `Mijoz ismi - Uchrashuv sababi` (masalan, `Ozodbek - Logo dizayni`).
3. Vaqtni oʻzgartiring: `"15:00 emas, 17:00 ga oʻtkazamiz"`.
   Eski event oʻchib, yangisi `17:00` da paydo boʻlishi kerak.
4. Admin guruhiga `Tushundim, uchrashuv taqvimga kiritildi` xabari keladi.

## Sozlamalar

| Env | Default | Maʼnosi |
|---|---|---|
| `GOOGLE_CALENDAR_ID` | `primary` | Event yoziladigan kalendar ID. |
| `GOOGLE_CALENDAR_TOKEN_PATH` | `token.json` | OAuth token fayli yoʻli. |
| `ENABLE_CALENDAR_AUTOSCHEDULE` | `1` | Har bir xabarda avtomatik aniqlash. |
| `ENABLE_CALENDAR_AUTOSCAN` | `1` | Davriy dialog skani. |

## Muammolar

- `Avtorizatsiya fayli topilmadi` — `token.json` yoʻq yoki notoʻgʻri yoʻlda.
- `Token yangilashda xato` — token bekor qilingan; `--force` bilan qayta yarating.
- Event yaratilmadi, lekin token bor — scope yetarli emas yoki kalendar ID
  notoʻgʻri. `GOOGLE_CALENDAR_ID` ni tekshiring.
- Service account ishlatilsa, `GOOGLE_CALENDAR_ID` ga service account emailiga
  ulashilgan kalendar ID sini yozing; `primary` ishlamaydi.
