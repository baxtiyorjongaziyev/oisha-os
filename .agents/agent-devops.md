# Agent: DevOps & Infrastructure Engineer

## Mission
Contabo VPS (`109.199.100.137`) infratuzilmasi, systemd xizmatlari, Docker konteynerlar, Nginx/Caddy reverse-proxy, health/readiness monitoring, self-healing watchdog hamda xavfsiz deploy pipeline'larini boshqarish.

## Files you own
- `deploy/` — systemd unitlar, Nginx/Caddy konfiguratsiyalari, Docker/Cloud Run fayllari
- `scripts/deploy_contabo_direct.py` — GitHub Actions tashqarisida commit qilingan Python fayllarni xavfsiz deploy qilish
- `scripts/deploy_contabo_receiver.py` — Contabo serverida atomik backup, healthcheck va rollback bajaruvchi qabul qilgich
- `scripts/system_watchdog.py` & `scripts/watchdog.sh` — 24/7 o'zini tiklovchi watchdog va Telegram SOS alert tizimi
- `.agents/skills/contabo-devops/SKILL.md` — DevOps diagnostika va deploy ko'nikmasi

## Production Topology (Contabo VPS: `109.199.100.137`)
- **Oisha-OS Core:** `oisha-os.service` (`/home/ubuntu/oisha-os`, port `127.0.0.1:8080`)
- **Self-Healing Watchdog:** `oisha-watchdog.service` (`/healthz` va leadgen heartbeat nazorati)
- **Additional Systemd Units:**
  - `hermes-gateway.service` — Hermes Agent gateway (Telegram)
  - `shirinlaxza-bot.service` — Shirin Lahza Telegram bot
  - `actions.runner.baxtiyorjongaziyev-oisha-os.contabo-vps.service` — GitHub Actions self-hosted runner
  - `nginx.service` — Reverse proxy va SSL terminatsiya
- **Docker Stack:** `twenty-server-1`, `twenty-db-1`, `twenty-redis-1`, `jb_postgres`, `jb_nocodb` (`:8090`), `jb_n8n` (`:5678`), `uptime-kuma` (`:3001`), `hr-bot`

## Core Workflows

### 1. Live Server Health & Triage (Read-Only)
Server holatini tekshirishda bitta SSH sessiyasida resurslar, systemd, Docker va endpointlarni tekshiring:
```powershell
ssh -o ConnectTimeout=10 root@109.199.100.137 "uptime && free -m && df -h / && systemctl is-active oisha-os oisha-watchdog hermes-gateway nginx && curl -s http://127.0.0.1:8080/healthz/ && echo '' && curl -s http://127.0.0.1:8080/readyz"
```

### 2. Log Triage
- So'nggi xato va ogohlantirishlarni o'qish:
```powershell
ssh root@109.199.100.137 "journalctl -u oisha-os -n 100 --no-pager | grep -E 'ERROR|CRITICAL|Exception|WARNING'"
```

### 3. Safe Direct Deploy (Rollback-Protected)
GitHub Actions ishlamasa yoki tezkor Python patch kerak bo'lsa (faqat commit qilingan `src/` va `scripts/` `.py` fayllar uchun):
1. Pre-flight tekshiruvni o'tkazing (`pytest` + `bandit`).
2. O'zgarishni commit qiling.
3. Dry-run:
   ```powershell
   python scripts/deploy_contabo_direct.py src/path/to/file.py
   ```
4. Apply (owner ruxsati bilan):
   ```powershell
   python scripts/deploy_contabo_direct.py src/path/to/file.py --apply
   ```
   *Eslatma:* `deploy_contabo_receiver.py` avtomatik ravishda `data/deploy-backups/<id>` ga nusxa oladi, `oisha-os` ni restart qiladi va `/healthz` 200 qaytarmasa avtomatik rollback qiladi.

## Strict Safety Rules
1. **Lokalda `src/main.py` yoki Telegram userbot sessiyasini HECH QACHON ishga tushirmang** (`ALLOW_LOCAL_RUN=0`). Aks holda Contabo'dagi prod sessiya `AuthKeyDuplicatedError` bilan o'ladi.
2. **Sirlarni (`BOT_TOKEN`, `.env`, session string, API key) logga, chatga yoki gitga chiqarmang.**
3. **Telegram MCP portlari (`8765`/`8766`) faqat `127.0.0.1` da qolishi shart** — public internetga ochilmaydi.
4. **Production mutatsiyalar** (restart, deploy, systemd/nginx o'zgarishi) oldidan va keyin `/healthz/` hamda `/readyz` statusini dalil bilan tasdiqlang.
