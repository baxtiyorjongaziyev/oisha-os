# Instagram Full Integration

Oisha-OS Instagramni browser bot orqali emas, rasmiy Meta Graph API orqali ulaydi.

## Scope

1. DM: webhook keladi, Oisha AI javob beradi, suhbat DBga yoziladi.
2. Comments: post/Reels comment keladi, AI javob beradi, sifatli signal leadga aylanadi.
3. Mentions/tags: brand mention ushlanadi va Telegram/AmoCRM signal bo'ladi.
4. Publishing: photo, Reels, Stories API orqali chiqariladi.
5. Insights: account/media reach, engagement va KPI olinadi.
6. Profile/media sync: oxirgi postlar, caption, permalink, media statistikasi olinadi.
7. AmoCRM + Telegram: sifatli signal CRM lead/note va Telegram xabarga aylanadi.

## Required Meta Setup

- Instagram account: Business yoki Creator.
- Facebook Page: Instagram account shu Pagega ulangan bo'lishi kerak.
- Meta App: Instagram Platform / Graph API ishlaydigan app.
- Webhook callback: `https://<public-host>/api/instagram/webhook`
- Verify token: `.env`dagi `META_VERIFY_TOKEN`.
- Webhook signature: Meta yuboradigan `x-hub-signature-256`, app secret bilan tekshiriladi.

Kerakli env:

```env
META_VERIFY_TOKEN=...
META_PAGE_ACCESS_TOKEN=...
META_APP_SECRET=...
META_INSTAGRAM_ACCOUNT_ID=...
META_PAGE_ID=...
META_GRAPH_API_VERSION=v19.0
OISHA_API_SECRET=...
```

Meta permission/app review odatda shu capabilitylarga bog'liq:

- Messaging: Instagram DM uchun.
- Comments/mentions: comment va mention webhooklari uchun.
- Content publishing: post/Reels/Stories chiqarish uchun.
- Insights: account va media KPI olish uchun.
- Page access: Instagram Business account ulangan Page orqali token olish uchun.

Aniq permission nomlari Meta App turiga qarab farq qilishi mumkin, shuning uchun yakuniy App Review ro'yxatini Meta dashboard va rasmiy docs bilan tekshiring.

## Oisha API Endpoints

Webhook:

- `GET /api/instagram/webhook` — Meta verify challenge.
- `POST /api/instagram/webhook` — DM/comment/mention eventlari.

Protected read/write endpoints, `Authorization: Bearer $OISHA_API_SECRET` kerak:

- `GET /api/instagram/status`
- `GET /api/instagram/profile`
- `GET /api/instagram/media?limit=25`
- `GET /api/instagram/media/{media_id}`
- `GET /api/instagram/media/{media_id}/comments`
- `GET /api/instagram/insights`
- `GET /api/instagram/media/{media_id}/insights`
- `GET /api/instagram/snapshot`
- `POST /api/instagram/comments/{comment_id}/reply`
- `POST /api/instagram/publish/photo`
- `POST /api/instagram/publish/reel`
- `POST /api/instagram/publish/story`

## Verification

Config-only:

```powershell
python scripts/probe_instagram_integration.py
```

Live read-only Meta probe:

```powershell
python scripts/probe_instagram_integration.py --live --media-limit 3
```

API server orqali:

```powershell
$headers = @{ Authorization = "Bearer $env:OISHA_API_SECRET" }
Invoke-RestMethod -Uri "https://<public-host>/api/instagram/status" -Headers $headers
Invoke-RestMethod -Uri "https://<public-host>/api/instagram/snapshot" -Headers $headers
```

## Safety

- Instagram password bilan login qiladigan browser bot ishlatilmaydi.
- Public write endpointlar `OISHA_API_SECRET` bilan yopilgan.
- Webhook POST raw body bo'yicha HMAC bilan tekshiriladi.
- Meta/AmoCRM/Telegram xatolari lead oqimini imkon qadar fail-open ushlaydi: xabar yo'qolmasligi birinchi o'rinda.
