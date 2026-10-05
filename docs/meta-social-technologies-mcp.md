# Meta Social Technologies MCP

Meta'ning rasmiy developer MCP serveri (avvalgi nomi: Meta Developer Tools MCP).
Oisha-OS'da u **Instagram/Meta integratsiyasini boshqarish va tekshirish** uchun
ishlatiladi: app sozlamalari, App Review holati, API rate limit / deprecation,
webhook obunalari va test payload.

> Bu server **runtime** emas — Oisha production kodi uni chaqirmaydi. U faqat
> dasturchi/agent (Claude Code, Codex, Cursor) uchun developer tooling.
> Production Meta trafik hamon `src/api/routes/instagram_routes.py` va
> `src/services/core/instagram_agent.py` orqali o'tadi.

| Atribut | Qiymat |
|---|---|
| Server nomi | `meta_social_technologies` |
| Transport | Streamable HTTP |
| Endpoint | `https://mcp.facebook.com/devtools` |
| Auth | Meta developer akkaunt orqali OAuth (App ID / Secret kerak emas) |
| Holat | Beta — tool'lar o'zgarishi mumkin, hamma uchun ochilmagan bo'lishi mumkin |

## Ulash

### Claude Code

Repo ildizidagi `.mcp.json` serverni allaqachon e'lon qiladi. Sessiyada:

```
/mcp  →  meta_social_technologies  →  Authenticate
```

Qo'lda qo'shish (global):

```bash
claude mcp add --transport http meta_social_technologies https://mcp.facebook.com/devtools
```

### Claude Desktop

**Settings → Connectors → Add custom connector** — Name: `Meta Social Technologies`,
URL: `https://mcp.facebook.com/devtools`.

### Codex

Codex MCP marshrutlari global `~/.codex/config.toml` da (`.codex/config.toml` dagi
izohga qarang). Codex App: **Settings → MCP Servers → Add servers → Streamable HTTP**,
Auth: **OAuth**, keyin **Authenticate**.

### Cursor

`~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "Meta Social Technologies": {
      "url": "https://mcp.facebook.com/devtools",
      "type": "http"
    }
  }
}
```

## OAuth va scope

1. Ulanishni boshlang (`/mcp` → Authenticate).
2. Brauzerda Meta akkaunt bilan kiring.
3. Consent ekranida **faqat Oisha'ning Meta app'ini** tanlang.
4. Klientni qayta ishga tushirganda sign-in qaytadan so'raladi.

| Scope | Nima beradi | Oisha tavsiyasi |
|---|---|---|
| **Read** | Sozlamalar, App Review, compliance, API usage, webhook ro'yxati | Default — kundalik ish uchun yetarli |
| **Manage** | Read + webhook subscribe/unsubscribe/update + test payload | Faqat webhook o'zgartirish kerak bo'lganda, keyin Read'ga qaytaring |

Scope va kirishni boshqarish: facebook.com → **Settings → Business Integrations**.

## Guardrails (Oisha qoidalari)

- **Webhook yozish = production o'zgarishi.** `devtools_webhook_manage` va
  `devtools_webhook_test` Oracle'dagi prod callback'ga real event yuboradi
  (`https://<public-host>/api/instagram/webhook`). Owner tasdig'isiz chaqirilmaydi —
  Telegram MCP mutatsiyalari bilan bir xil tamoyil.
- Test payload quiet-hours (23:00–07:00 Toshkent) vaqtida yuborilmaydi: webhook
  `instagram_agent` orqali AI javob / Telegram signal'ni ishga tushirishi mumkin.
- Callback URL'ni o'zgartirishdan oldin `META_VERIFY_TOKEN` prod'da to'g'ri
  ekanini tekshiring — aks holda Meta verification yiqiladi va DM/comment oqimi to'xtaydi.
- Token, app secret, OAuth kodlari repo, `DEV_LOG.md` yoki handoff-log'ga yozilmaydi.

## Tool'lar (11 ta, `devtools_` prefiksi)

| Tool | Action'lar | Oisha'da qachon |
|---|---|---|
| `devtools_app_list` | `list` | Birinchi qadam — `app_id` ni topish |
| `devtools_app` | `basic_settings`, `advanced_settings`, `security`, `restrictions`, `data_protection_officer` | App sozlamasini audit qilish |
| `devtools_app_review` | `status`, `history`, `privileges`, `requirements` | `instagram_manage_messages`, `instagram_manage_comments`, `ads_read` va h.k. tasdiqlanganmi |
| `devtools_compliance` | `status` | Yangi feature yoki App Review'dan oldin |
| `devtools_api_usage` | `rate_limits`, `call_volume`, `deprecations` | Weekly reporter / Graph API xatolarida; `META_GRAPH_API_VERSION` eskirganini aniqlash |
| `devtools_webhook_list` | `list_topics`, `list_subscriptions` | `instagram` topic'da `messages`, `comments`, `mentions` obuna bo'lganmi |
| `devtools_webhook_manage` | `subscribe`, `unsubscribe`, `update_fields` | **Manage + Owner tasdig'i** |
| `devtools_webhook_test` | `test_send` | **Manage + Owner tasdig'i**; callback o'zgargandan keyin |
| `devtools_api_changelog` | `list_products`, `get_changelog_url`, `get_rss_url` | Graph API versiya yangilanishini kuzatish |
| `devtools_discovery` | `search_docs` | Meta hujjatlarini qidirish |
| `devtools_skill_invocation` | `start`, `end` | Avtomatik marker, qo'lda chaqirilmaydi |

## Tayyor promptlar

```
Meta app'larimni ro'yxatla va Oisha app'ining app_id sini ko'rsat.
```

```
<app_id> uchun App Review holatini tekshir: Instagram DM, comment va ads_read
ruxsatlari tasdiqlanganmi? Nima yetishmayapti?
```

```
<app_id> rate limit'ga yaqinmi? Biz ishlatayotgan Graph API versiyasi (v19.0)
deprecation ro'yxatidami?
```

```
<app_id> ning webhook obunalarini ko'rsat. instagram topic'da messages, comments,
mentions field'lari bormi? Hech narsani o'zgartirma.
```

## Haftalik avtomatik health-check (Oracle runtime)

MCP OAuth'ni faqat interaktiv klientda bajaradi, shuning uchun Oracle'dagi Oisha
xuddi shu signallarni **to'g'ridan-to'g'ri Graph API'dan** oladi va har **dushanba
09:15 (Toshkent)** Owner'ga Telegram hisobot yuboradi. Faqat o'qish — hech narsa
o'zgartirilmaydi.

| Tekshiruv | Manba | Ogohlantirish |
|---|---|---|
| Token amal qilishi | `GET /debug_token` | Yaroqsiz ❌, 14 kundan kam qolgan ⚠️ |
| Ruxsatlar | `debug_token.scopes` | `instagram_basic`, `instagram_manage_messages`, `instagram_manage_comments` yo'q ❌ |
| Rate limit | `X-App-Usage`, `X-Business-Use-Case-Usage` header | ≥ 75% ⚠️ |
| API versiya | `facebook-api-version` header | Meta boshqa versiya bilan javob bersa (eskirgan, auto-upgrade) ⚠️ |
| Page webhook | `GET /{META_PAGE_ID}/subscribed_apps` | App obuna emas ❌, field'lar bo'sh ⚠️ |

Kod: `src/services/core/instagram/meta_health_check.py`,
`src/schedulers/meta_health_scheduler.py`. Env: `META_PAGE_ACCESS_TOKEN` (majburiy),
`META_PAGE_ID`, `META_GRAPH_API_VERSION`, `META_HEALTH_CHECK_ENABLED` (default `1`).
Token yo'q bo'lsa loop jim o'tkazib yuboradi. Hisobotda ⚠️/❌ chiqsa — batafsil
tahlilni Claude Code'da MCP orqali qiling.

## Tekshirish

1. Klientni qayta ishga tushiring.
2. Agentdan `meta social technologies` tool'larini sanab berishni so'rang — 11 ta chiqishi kerak.
3. Xavfsiz read: `devtools_app_list` yoki `devtools_api_changelog`.

| Xato | Ma'nosi |
|---|---|
| "It looks like this app isn't available" | Akkauntingizga hali kirish berilmagan (beta rollout) |
| "Facebook login is currently unavailable for this app" | Klient hali qo'llab-quvvatlanmaydi |

Bog'liq: `docs/instagram-full-integration.md`, `.env.example` (`META_*`).
Feedback: https://forms.gle/6MUgLiWU2PWVtjeM6
