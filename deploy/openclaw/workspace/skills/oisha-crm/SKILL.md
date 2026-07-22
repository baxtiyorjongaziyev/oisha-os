# oisha-crm

Oisha-OS CRM va biznes avtomatlashtirish tizimi bilan to'g'ridan-to'g'ri ishlash.

## Nima qiladi

AmoCRM pipeline boshqaruvi, lead kuzatuvi, savdo avtomatlashtirish va jamoa
muvofiqlashtirish operatsiyalarini bajaradi. Oisha-OS FastAPI backenddagi
agentlarga so'rov yuboradi.

## O'rnatish

Hech qanday tashqi binary kerak emas. Faqat `OISHA_API_URL` va
`OISHA_API_SECRET` muhit o'zgaruvchilari sozlanishi lozim.

## Qo'llab-quvvatlanadigan amallar

### Lead boshqaruvi

```
# Yangi lead yaratish
POST ${OISHA_API_URL}/api/leads
{ "name": "...", "phone": "...", "note": "...", "secret_key": "${OISHA_API_SECRET}" }

# Lead holatini tekshirish
GET ${OISHA_API_URL}/api/chat/lookup/{phone}?secret_key=${OISHA_API_SECRET}
```

### AI agentga savol

```
POST ${OISHA_API_URL}/webhook/openclaw
{
  "text": "Foydalanuvchi xabari",
  "sender": "ism",
  "sender_id": "id",
  "channel": "whatsapp|slack|discord|telegram",
  "session": "main"
}
```

### Sifat tahlili

```
# Suhbatni tahlil qilish
POST ${OISHA_API_URL}/api/ai/analyze-conversation
{ "conversation_text": "...", "conversation_id": "...", "manager_name": "..." }

# Dashboard ko'rsatkichlari
GET ${OISHA_API_URL}/api/ai/metasell-dashboard?days=7
```

### Tizim holati

```
GET ${OISHA_API_URL}/webhook/openclaw/health
GET ${OISHA_API_URL}/health
GET ${OISHA_API_URL}/api/system/status
```

## Cheklovlar

- Faqat `OISHA_API_SECRET` bilan himoyalangan endpointlarga kirish
- Shaxsiy mijoz ma'lumotlari tashqi sistemalarga uzatilmaydi
- Barcha amallar audit logga yoziladi
