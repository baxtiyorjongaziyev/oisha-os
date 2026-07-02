# Oisha Callmaster MVP

Maqsad: Smartcall/Callmaster kabi tashqi servisga bog'lanmasdan, Oisha-OS ichida
o'zimizning avto-qo'ng'iroq boshqaruv qatlamini qurish.

## Hozir bor imkoniyatlar

- Kampaniya yaratish: audio URL, nom, parallel qo'ng'iroq limiti.
- Kontakt import qilish: telefon normalizatsiya, duplicate ajratish, AmoCRM lead ID saqlash.
- Kampaniyani launch qilish: kontaktlar uchun qo'ng'iroq attempt queue yaratish.
- Webhook qabul qilish: answered, failed, no_answer, digit/DTMF natijalarini saqlash.
- `1` bosgan mijozni yuqori prioritet actionga aylantirish.
- AmoCRM uchun tayyor payload: lead note + follow-up task matni.
- JSON state store: `data/callmaster_state.json`.

## Endpointlar

Admin endpointlar `Authorization: Bearer <CALLMASTER_API_SECRET>` talab qiladi.

```http
POST /api/callmaster/campaigns
POST /api/callmaster/campaigns/{campaign_id}/contacts
POST /api/callmaster/campaigns/{campaign_id}/launch
GET  /api/callmaster/campaigns/{campaign_id}
```

Webhook endpoint:

```http
POST /api/callmaster/webhook
X-Callmaster-Signature: sha256=<hmac_sha256_body>
```

Yoki ichki testlarda:

```http
X-Callmaster-Webhook-Secret: <CALLMASTER_WEBHOOK_SECRET>
```

## Muhim env

```env
CALLMASTER_API_SECRET=...
CALLMASTER_WEBHOOK_SECRET=...
CALLMASTER_STATE_FILE=data/callmaster_state.json
```

## Haqiqiy qo'ng'iroq qilish uchun

Bu MVP hozir Oisha ichidagi miya va nazorat qatlami. Telefon liniyasi uchun eng arzon
self-hosted yo'llar:

1. Asterisk/FreePBX + SIP trunk
2. GSM modem pool + Asterisk chan_dongle
3. Android telefonlar + SIP/ADB bridge

Tavsiya: Oracle/Contabo VM ga Asterisk qo'yiladi, Oisha `queued_attempts`ni dialerga beradi,
dialer esa natijani `/api/callmaster/webhook`ga qaytaradi.

## Oisha biznes oqimi

1. Oisha AmoCRMdan kerakli leadlarni tanlaydi.
2. Yopilgan, oila/shaxsiy, blacklist va dublikat leadlar chiqarib tashlanadi.
3. Kampaniya yaratiladi va raqamlar import qilinadi.
4. Dialer qo'ng'iroq qiladi.
5. Mijoz `1` bossa, Oisha AmoCRMda task/note yaratadi va sales managerga signal beradi.

