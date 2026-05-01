# Oisha-OS — Session Context

> Claude har sessiya boshida bu faylni o'qiydi. Muhim kontekstni shu yerga yozadi.
> Token tejash uchun: conversation ichida takrorlamasdan, bu faylga murojaat qiladi.

---

## Tizim holati (oxirgi yangilash: 2026-04-26)

### Deploy holati
- **Cloud Run**: `oisha-master-bot` | `europe-west3` | project: `jonbranding-85662071-ea38e`
- **Userbot**: `ENABLE_CLOUD_USERBOT=True` — deploy trigerlandi, GitHub Actions ishlamoqda
- **Session string**: `.env` da bor — GCP Secret Manager ga qo'shish uchun GitHub secret kerak

### GitHub
- **Repo**: `baxtiyorjongaziyev/oisha-os`
- **Asosiy branch**: `main`
- **Ish branchi**: `claude/investigate-openclaw-query-HdLAv`
- **Oxirgi commit**: `48a541c` — userbot enable + secret sync step

### OpenClaw integratsiyasi (tugallangan)
- `/webhook/openclaw` — HMAC-SHA256 xavfsiz webhook
- `/v1/chat/completions` + `/v1/models` — OpenAI-compatible endpoint
- `src/openclaw_bridge.py` — kanal → agent routing
- `deploy/openclaw/` — config, workspace, skills, setup.sh

---

## Muhim sozlamalar

| O'zgaruvchi | Qiymat/Joylashuvi |
|---|---|
| `API_ID` | 30643078 |
| `API_HASH` | ***REDACTED*** |
| `BOT_TOKEN` | 8343217526:AAH0odkrzt9hF2xCIxbYped2OnYnP0Txe-4 |
| `GEMINI_API_KEY` | `.env` da |
| `OISHA_API_SECRET` | ***REDACTED*** |
| `OPENCLAW_SECRET` | ***REDACTED*** |
| `USERBOT_SESSION_STRING` | `.env` da (353 belgi, DC2) |

---

## Arxitektura

```
Telegram / WhatsApp / Slack / Discord
        ↓
   OpenClaw Gateway (Node.js)
        ↓
   /webhook/openclaw  (HMAC)
   /v1/chat/completions (OpenAI-compat)
        ↓
   AgentOrchestrator → Gemini 1.5 Flash/Pro
        ↓
   AmoCRM / Google Calendar / Telegram Bot
```

---

## Pending tasklar

- [ ] GitHub secret `USERBOT_SESSION_STRING` qo'shish (repo Settings → Secrets)
- [ ] Deploy natijasini tekshirish (GitHub Actions log)
- [ ] Userbot ulanganini tasdiqlash (Telegram da Oisha ga yozish)

---

## NotebookLM uchun eksport

`docs/context/NOTEBOOKLM_EXPORT.md` — to'liq tizim tavsifi NotebookLM ga yuklash uchun
