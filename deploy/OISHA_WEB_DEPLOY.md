# oisha.jonbranding.uz — Deploy Runbook

Oracle `jon-free-micro` (163.192.10.104, Ubuntu 24.04, 1GB RAM + 2GB swap) uchun.

## Arxitektura

```
Browser ──HTTPS──▶ nginx (80/443, basic auth)
                     ├── /          ──▶ Next.js  (127.0.0.1:3000, oisha-web.service)
                     ├── /api/...   ──▶ FastAPI  (127.0.0.1:8080, oisha-os.service)
                     └── /healthz   ──▶ FastAPI  (auth'siz, monitoring uchun)
```

- **DNS**: Cloudflare'da `oisha` A record → `163.192.10.104` (allaqachon mavjud).
  Hozir DNS-only (gray cloud); Let's Encrypt sertifikat bilan ishlaydi.
  Orange cloud (proxy) yoqilsa ham ishlashda davom etadi (zone SSL = Full).
- **SSL**: Let's Encrypt (certbot --nginx), avto-yangilanish systemd timer orqali.
- **Auth**: nginx basic auth butun sayt + API'ni yopadi (`/healthz` bundan mustasno).

## Bir martalik o'rnatish

Serverga SSH bilan kiring va scriptni ishga tushiring:

```bash
ssh -i ~/.ssh/oracle_free_tier_ed25519 ubuntu@163.192.10.104

# Serverda:
git clone https://github.com/baxtiyorjongaziyev/oisha-os.git ~/oisha-os 2>/dev/null || true
cd ~/oisha-os
git fetch origin refactor/architecture-cleanup
git checkout refactor/architecture-cleanup

export ADMIN_USER=oisha
export ADMIN_PASS='KUCHLI-PAROL-QOYING'
export CERTBOT_EMAIL=baxtiyorjongaziyev@gmail.com
bash deploy/oracle-web-setup.sh
```

Script quyidagilarni qiladi:
1. nginx + certbot + Node 22 + pnpm o'rnatadi
2. Repo'ni `refactor/architecture-cleanup` branch'iga o'tkazadi
3. Python bot uchun `oisha-os.service`'ni sozlaydi (mavjud `oracle-setup.sh` orqali)
4. `.env` shablonini yaratadi (secretlar QO'LDA to'ldiriladi)
5. Next.js'ni `NEXT_PUBLIC_API_URL=https://oisha.jonbranding.uz/api/v1` bilan build qiladi
6. `oisha-web.service` (Next.js, port 3000) yoqadi
7. nginx vhost + basic auth sozlaydi
8. Let's Encrypt HTTPS sertifikat oladi

## Secretlar

`.env`'ni to'ldirishning eng oson yo'li — **eski serverdan ko'chirish**:

```bash
# Lokal kompyuterda (eski serverdan yangi serverga):
scp -i ~/.ssh/ESKI_KEY ubuntu@ESKI_IP:/home/ubuntu/oisha-os/.env /tmp/oisha.env
scp -i ~/.ssh/oracle_free_tier_ed25519 /tmp/oisha.env ubuntu@163.192.10.104:/home/ubuntu/oisha-os/.env
rm /tmp/oisha.env
```

Yoki GitHub Actions secrets'dan qo'lda ko'chiring. `.env`'ga qo'shimcha qiling:

```
ALLOWED_ORIGINS=https://oisha.jonbranding.uz
```

Keyin: `sudo systemctl restart oisha-os`

## CI/CD (keyingi bosqich)

`oracle-deploy.yml` workflow `main`'ga push'da eski serverga deploy qiladi.
Yangi serverga o'tkazish uchun GitHub repo Settings → Secrets:

- `ORACLE_HOST` → `163.192.10.104`
- `ORACLE_SSH_KEY` → `oracle_free_tier_ed25519` private key mazmuni

Bu branch main'ga merge bo'lgach avtomatik deploy ishlaydi
(workflow'ga web-build qadamini qo'shish kerak bo'ladi — hozircha
web yangilanishi qo'lda: `bash deploy/oracle-web-setup.sh`).

## Tekshirish

```bash
# Servislar
sudo systemctl status oisha-web oisha-os nginx --no-pager

# Loglar
sudo journalctl -u oisha-web -f
sudo journalctl -u oisha-os -f

# API (basic auth bilan)
curl -u oisha:PAROL https://oisha.jonbranding.uz/api/v1/admin/dashboard/stats
curl -u oisha:PAROL https://oisha.jonbranding.uz/api/v1/admin/deadlines

# Health (auth'siz)
curl https://oisha.jonbranding.uz/healthz
```

Brauzerda: **https://oisha.jonbranding.uz/admin** → basic auth login → dashboard.

## Eslatmalar / cheklovlar

- **1GB RAM**: Next.js build sekin (~5-15 daqiqa, swap bilan). Ollama bu serverda
  YOQILMAYDI (qwen2.5:3b uchun RAM yetmaydi) — free-AI Groq/Cloudflare'ga fallback qiladi.
- **Eksport amallari** (`/teznatija`, `/teznatija_amo`) jonli Telethon client talab
  qiladi — web'dagi tugmalar 503 + tushuntirish qaytaradi, Telegram buyrug'i ishlaydi.
- **Cloudflare token**: hozirgi token faqat o'qish huquqiga ega (DNS Edit yo'q).
  Orange cloud'ni dashboard'dan qo'lda yoqing yoki tokenga `Zone → DNS → Edit`
  huquqini bering.
- **Xavfsizlik**: chatda ulashilgan Cloudflare token va AWS kalitni ishlatib
  bo'lgach ROTATSIYA QILING (Cloudflare dashboard → API Tokens → Roll).
