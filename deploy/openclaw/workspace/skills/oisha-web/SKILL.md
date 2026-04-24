# oisha-web

Oisha-OS veb-sayt va marketing kanallaridan kelgan leadlarni qabul qilish.

## Nima qiladi

Vebsayt formalaridan, landing page lardan va marketing kampaniyalaridan
kelgan leadlarni avtomatik AmoCRM ga yuboradi.

## Qo'llab-quvvatlanadigan amallar

```
# Vebsaytdan lead qabul qilish
POST ${OISHA_API_URL}/api/leads
{
  "name": "Mijoz ismi",
  "phone": "+998901234567",
  "note": "Qaysi xizmat haqida",
  "secret_key": "${OISHA_API_SECRET}"
}

# Webhook orqali call tahlili yuborish
POST ${OISHA_API_URL}/api/ai/process-call
{
  "call_id": "call_001",
  "lead_id": 12345,
  "manager_name": "Sardor",
  "duration_seconds": 300,
  "transcript": "Suhbat matni..."
}

# Savdo sifati dashboardi
GET ${OISHA_API_URL}/api/sales-quality/overview
```

## Cheklovlar

- Faqat autentifikatsiyalangan so'rovlar qabul qilinadi
- Telefon raqam formati tekshiriladi
