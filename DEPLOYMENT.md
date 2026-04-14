# 🚀 Oisha-OS Deployment Guide

## Avtomatik CI/CD (Tavsiya etiladi)

Har bir `git push` bilan avtomatik deploy!

### 1. Bir martalik sozlash

```bash
# Skriptni ishga tushirish
bash scripts/setup-ci-cd.sh
```

Bu skript quyidagilarni bajaradi:
- ✅ Google Cloud API'larni yoqadi
- ✅ Secret Manager'da maxfiy kalitlarni saqlaydi
- ✅ GitHub Actions uchun Service Account yaratadi
- ✅ Kerakli ruxsatlarni beradi

### 2. GitHub Secrets qo'shish

GitHub repository'ga o'ting:
`Settings → Secrets and variables → Actions → New repository secret`

Quyidagi secret'larni qo'shing:

| Secret | Tavsif |
|--------|--------|
| `GCP_SA_KEY` | `github-actions-key.json` fayl ichidagi JSON |
| `OWNER_ID` | Sizning Telegram ID'ingiz |

### 3. Deploy!

```bash
git add .
git commit -m "Oisha-OS v2.3 - 10/10 Perfect Edition"
git push origin main
```

GitHub Actions avtomatik ishga tushadi:
1. 🧪 Testlarni ishga tushiradi
2. 🏗️ Docker image yaratadi
3. 🚀 Cloud Run'ga deploy qiladi
4. 📢 Telegram'ga xabar yuboradi

---

## Qo'lda Deploy (Cloud Build)

```bash
gcloud builds submit --config cloudbuild.yaml
```

## Qo'lda Deploy (gcloud)

```bash
# Image yaratish
gcloud builds submit --tag gcr.io/jonbranding-85662071-ea38e/oisha-master-bot .

# Deploy qilish
gcloud run deploy oisha-master-bot \
  --image gcr.io/jonbranding-85662071-ea38e/oisha-master-bot \
  --platform managed \
  --region europe-west3 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 3600
```

---

## Sozlamalar

### Secret Manager'da saqlanadiganlar:

```bash
# Barcha secret'larni ko'rish
gcloud secrets list

# Yangi secret qo'shish
echo "SECRET_VALUE" | gcloud secrets create SECRET_NAME --data-file=-

# Secret o'qish
gcloud secrets versions access latest --secret=SECRET_NAME
```

### Muhit o'zgaruvchilari (Environment Variables):

| O'zgaruvchi | Qayerda | Tavsif |
|-------------|---------|--------|
| `RUNNING_IN_CLOUD` | Cloud Run | Cloud muhitida ishlashini bildiradi |
| `ENVIRONMENT` | Cloud Run | `production` yoki `development` |
| `GCS_BUCKET` | Secret Manager | Sessiya fayllari uchun bucket |

---

## Monitoring

### Cloud Run logs:
```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=oisha-master-bot" --limit=50
```

### GitHub Actions status:
GitHub repository → Actions tab

### Telegram orqali:
Bot avtomatik ravishda deployment status haqida xabar yuboradi

---

## Troubleshooting

### Issue: "Permission denied"
**Yechim:** Service account'ga ruxsatlarni tekshiring:
```bash
gcloud projects get-iam-policy jonbranding-85662071-ea38e
```

### Issue: "Secret not found"
**Yechim:** Secret Manager'da secret'larni tekshiring:
```bash
gcloud secrets list
```

### Issue: "Build failed"
**Yechim:** Cloud Build logs'ni ko'ring:
```bash
gcloud builds list
gcloud builds log BUILD_ID
```

---

## Arkitektura

```
GitHub Push
    ↓
GitHub Actions
    ├── 🧪 Run Tests
    └── 🚀 Deploy
            ↓
    Google Cloud Build
            ↓
    Container Registry
            ↓
    Cloud Run (Auto-scaling)
            ↓
    Telegram Bot + FastAPI
```

---

## Yangilanishlar (Updates)

Har bir yangilanish avtomatik deploy bo'ladi:

1. Kod o'zgartiring
2. `git commit`
3. `git push origin main`
4. ⏳ 3-5 daqiqa kuting
5. ✅ Tayyor!

Yoki qo'lda ishga tushirish:
GitHub → Actions → "🚀 Oisha-OS Auto Deploy (CI/CD)" → Run workflow
