# Oisha Agent Routing — OpenClaw Workspace

Barcha kiruvchi xabarlar quyidagi qoidalar asosida yo'naltiriladi.

## Agent xaritasi

| Agent      | Vazifa                                          | Kalit so'zlar                                          |
|------------|-------------------------------------------------|--------------------------------------------------------|
| `sales`    | Narx, xizmat, buyurtma, shartnoma, muzokaralar  | narx, qancha, buyurtma, xizmat, klient, taklif, deal  |
| `support`  | FAQ, texnik savol, shikoyat, umumiy yordam       | muammo, yordam, tushunmadim, xato, ishlamayapti        |
| `strategist` | Loyiha holati, reja, KPI, jamoaviy audit      | reja, strategiya, holat, hisobot, audit, KPI           |
| `researcher` | Bozor tahlili, OSINT, raqobatchilar           | tadqiqot, bozor, raqobatchi, trend, tahlil             |

## Kanal-spetsifik qoidalar

- **WhatsApp**: Odatda yangi mijozlar — `sales` agenti ustun
- **Slack**: Odatda ichki jamoa — `strategist` yoki `support` ustun
- **Discord**: Aralash — intent bo'yicha yo'naltir
- **Telegram**: Barcha holat — asosiy kanalimiz, to'liq qo'llab-quvvatlash

## Eslatmalar

- Noaniq xabarlarda `sales` agentiga yo'naltir (default)
- Bir xabarda bir nechta intent bo'lsa, asosiyni tanlash
- Har bir javobdan so'ng `check_and_summarize` orqa fonda ishlaydi
