---
name: contabo-devops
description: Diagnose, monitor, and manage Oisha-OS production infrastructure on Contabo VPS (109.199.100.137), including systemd services, Docker containers, healthz/readyz checks, logs, and rollback-safe direct deployments.
---

# Contabo DevOps & SRE Skill

Use this skill whenever the user asks about server status ("contabo serverda nima gap", "server ishlayaptimi", "loglarni ko'r", "deploy qil", "restart qil") or when performing infrastructure diagnostics, incident response, and deployments on Contabo VPS (`109.199.100.137`).

## 1. Quick Health & Status Check (Read-Only)

Run a single consolidated SSH probe to inspect system load, memory, disk, core systemd services, Docker containers, and `/healthz` + `/readyz` endpoints:

```powershell
ssh -o ConnectTimeout=10 root@109.199.100.137 "uptime && free -m && df -h / && systemctl status oisha-os --no-pager -l | head -n 25 && curl -s http://127.0.0.1:8080/healthz/ && echo '' && curl -s http://127.0.0.1:8080/readyz && echo '' && docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"
```

### Expected Healthy Baseline
- **Systemd services (`active (running)`):**
  - `oisha-os.service` — Main Oisha-OS runtime & Telethon userbot (`/home/ubuntu/oisha-os`)
  - `oisha-watchdog.service` — Self-healing monitor (`scripts/system_watchdog.py`)
  - `hermes-gateway.service` — Hermes Agent Telegram gateway
  - `shirinlaxza-bot.service` — Shirin Lahza bot
  - `nginx.service` — Reverse proxy
  - `actions.runner.baxtiyorjongaziyev-oisha-os.contabo-vps.service` — GitHub Actions runner
- **HTTP Health Endpoints (`127.0.0.1:8080`):**
  - `/healthz/` -> `{"status":"alive", "checks":{"event_loop":"responsive","db_instance":"present",...}}`
  - `/readyz` -> `{"ready":true,"status":"ready","checks":{"database":"ok","userbot":"authorized","amocrm":"connected",...},"problems":[]}`
- **Docker Containers (`Up / healthy`):**
  - `twenty-server-1`, `twenty-db-1`, `twenty-redis-1`, `jb_postgres`, `jb_nocodb`, `jb_n8n`, `uptime-kuma`, `hr-bot`

## 2. Log Inspection & Noise Filtering

When inspecting `oisha-os` logs, filter out high-frequency routine messages if looking for real errors:

```powershell
ssh -o ConnectTimeout=10 root@109.199.100.137 "journalctl -u oisha-os -n 200 --no-pager | grep -v 'AMOCRM TOKEN STORE' | tail -n 50"
```

For error-only triage:
```powershell
ssh -o ConnectTimeout=10 root@109.199.100.137 "journalctl -u oisha-os --since '1 hour ago' --no-pager | grep -E 'ERROR|CRITICAL|Traceback|Exception' | tail -n 40"
```

## 3. Rollback-Safe Direct Deployment (`deploy_contabo_direct.py`)

When deploying committed Python files (`src/**/*.py` or `scripts/**/*.py`) directly to Contabo:

1. **Pre-flight Gates (Local):**
   ```powershell
   $env:SKIP_LIVE=1; python -m pytest -q --tb=short
   bandit -r src/ -ll
   ```
2. **Dry-Run Verification:**
   ```powershell
   python scripts/deploy_contabo_direct.py <repo-relative-py-files>
   ```
   *(Files must be committed to `HEAD` before running `deploy_contabo_direct.py`.)*
3. **Execute Deployment (with Owner Authorization):**
   ```powershell
   python scripts/deploy_contabo_direct.py <repo-relative-py-files> --apply
   ```
   - `scripts/deploy_contabo_receiver.py` backs up replaced files to `/home/ubuntu/oisha-os/data/deploy-backups/<bundle_id>`, compiles bytecode, restarts `oisha-os`, polls `http://127.0.0.1:8080/healthz` up to 20 times, and automatically restores backups + restarts if `/healthz` fails.
4. **Post-Deploy Verification:**
   Always re-read `/healthz/` and `/readyz` after deployment and report exact evidence.

## 4. Non-Negotiable Guardrails
- **NEVER run `src/main.py` locally** (`ALLOW_LOCAL_RUN=0`). Starting Telethon locally kills Contabo's session with `AuthKeyDuplicatedError`.
- **NEVER print or log `.env` values, tokens, passwords, or session strings.**
- **NEVER expose ports `8765` or `8766` (Telegram MCP) publicly.**
- Separate **local / committed / pushed / deployed** states clearly in your report.
