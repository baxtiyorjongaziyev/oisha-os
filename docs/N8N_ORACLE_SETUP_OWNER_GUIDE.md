# JonBranding / Oisha-OS: Oracle serverga n8n o'rnatish

Bu qo'llanma dasturchi bo'lmagan egalar uchun yozilgan. Maqsad: Oracle serverda n8n'ni ishga tushirish va keyin Telegram → AI → CRM avtomatlashtirishlarini qurish.

## Muhim xavfsizlik qoidalari

1. API_ID, API_HASH, USERBOT_SESSION_STRING, parol va tokenlarni ChatGPT, Telegram yoki notanish odamga yubormang.
2. Real `.env` faylni GitHub'ga commit qilmang.
3. Telegram userbot session faqat bitta joyda ishlasin: Oracle serverda.
4. Avval n8n'ni o'rnatamiz, keyin Telegram workflow'ni ulaymiz.

---

## 1-qadam: Serverga kirish

Kompyuteringiz terminalida yoki server panelidagi console'da Oracle serverga kiring.

```bash
ssh ubuntu@YOUR_SERVER_IP
```

Agar user `ubuntu` bo'lmasa, Oracle'dagi haqiqiy userni ishlating.

---

## 2-qadam: Docker bor-yo'qligini tekshirish

```bash
docker --version
docker compose version
```

Agar versiya chiqsa, keyingi qadamga o'ting.

Agar Docker yo'q desa, o'rnating:

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-plugin
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER
```

Keyin serverdan chiqib qayta kiring:

```bash
exit
```

va yana:

```bash
ssh ubuntu@YOUR_SERVER_IP
```

---

## 3-qadam: Repo'ni yangilash

```bash
cd ~/oisha-os
git pull
```

Agar repo boshqa joyda bo'lsa, o'sha papkaga kiring.

---

## 4-qadam: n8n .env faylini yaratish

```bash
cd ~/oisha-os/deploy/n8n
cp .env.example .env
```

Encryption key yarating:

```bash
openssl rand -hex 32
```

Chiqqan uzun kodni nusxa qiling.

`.env` faylni oching:

```bash
nano .env
```

Quyidagilarni almashtiring:

- `CHANGE_ME_STRONG_PASSWORD` → kuchli parol
- `CHANGE_ME_64_HEX_CHARS` → openssl chiqargan kod
- `YOUR_SERVER_IP_OR_DOMAIN` → Oracle server IP manzili yoki domen

Saqlash:

- `Ctrl + O`
- `Enter`
- `Ctrl + X`

---

## 5-qadam: n8n'ni ishga tushirish

```bash
cd ~/oisha-os/deploy/n8n
docker compose up -d
```

Tekshirish:

```bash
docker compose ps
```

Ikkala container ham `running` yoki `healthy` bo'lishi kerak:

- `oisha_n8n`
- `oisha_n8n_postgres`

Log ko'rish:

```bash
docker compose logs -f n8n
```

---

## 6-qadam: Brauzerda ochish

Brauzerda oching:

```text
http://YOUR_SERVER_IP:5678
```

n8n birinchi marta ochilganda account yaratishni so'raydi. Email/parolni o'zingiz kiriting.

---

## 7-qadam: Oracle Firewall / Security List

Agar sahifa ochilmasa, Oracle Cloud panelida port 5678 ochilishi kerak.

Kerakli port:

```text
TCP 5678
```

Keyin yana brauzerda tekshiring.

---

## 8-qadam: Keyingi bosqich

n8n ochilgandan keyin JonBranding uchun birinchi workflow quriladi:

```text
Manual Trigger
↓
Telegram / lead source
↓
AI Lead Analyzer
↓
Airtable yoki AmoCRM
↓
Telegram hisobot
```

Birinchi biznes vazifa:

```text
Bugun 5 ta iliq lead topish → follow-up matn chiqarish → kamida 1 ta uchrashuv belgilash.
```

---

## Muammo bo'lsa menga shuni tashlang

```bash
cd ~/oisha-os/deploy/n8n
docker compose ps
docker compose logs --tail=80 n8n
```

Chiqgan natijani ChatGPT'ga yuboring. Sirli token/parollar ko'rinsa, avval o'chirib tashlang.
