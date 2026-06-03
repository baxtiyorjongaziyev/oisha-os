@echo off
chcp 65001 >nul
if /I not "%OISHA_ALLOW_GCP%"=="1" (
    echo BLOCKED: Oisha production Oracle VMda ishlaydi. Google Cloud deploy o'chirilgan.
    echo Agar juda zarur bo'lsa: set OISHA_ALLOW_GCP=1
    exit /b 1
)
echo ==========================================
echo  Oisha-OS Deploy Script
echo ==========================================
echo.

:: Create temp directory
if not exist C:\tmp mkdir C:\tmp

:: Create BOT_TOKEN secret
echo [1/10] Creating BOT_TOKEN...
gcloud secrets versions access latest --secret=oisha-bot-token > C:\tmp\bot_token.txt 2>nul
if %errorlevel% == 0 (
    gcloud secrets create BOT_TOKEN --data-file=C:\tmp\bot_token.txt --quiet 2>nul
    if %errorlevel% == 0 (echo   OK) else (echo   Already exists or updated)
) else (
    echo   SKIPPED (source not found)
)

:: Create API_ID secret
echo [2/10] Creating API_ID...
gcloud secrets versions access latest --secret=oisha-api-id > C:\tmp\api_id.txt 2>nul
if %errorlevel% == 0 (
    gcloud secrets create API_ID --data-file=C:\tmp\api_id.txt --quiet 2>nul
    if %errorlevel% == 0 (echo   OK) else (echo   Already exists or updated)
) else (
    echo   SKIPPED (source not found)
)

:: Create API_HASH secret
echo [3/10] Creating API_HASH...
gcloud secrets versions access latest --secret=oisha-api-hash > C:\tmp\api_hash.txt 2>nul
if %errorlevel% == 0 (
    gcloud secrets create API_HASH --data-file=C:\tmp\api_hash.txt --quiet 2>nul
    if %errorlevel% == 0 (echo   OK) else (echo   Already exists or updated)
) else (
    echo   SKIPPED (source not found)
)

:: Create GEMINI_API_KEY secret
echo [4/10] Creating GEMINI_API_KEY...
gcloud secrets versions access latest --secret=oisha-gemini-key > C:\tmp\gemini.txt 2>nul
if %errorlevel% == 0 (
    gcloud secrets create GEMINI_API_KEY --data-file=C:\tmp\gemini.txt --quiet 2>nul
    if %errorlevel% == 0 (echo   OK) else (echo   Already exists or updated)
) else (
    echo   SKIPPED (source not found)
)

:: Create placeholder secrets for remaining
echo [5/10] Creating OISHA_API_SECRET (placeholder)...
echo "changeme" | gcloud secrets create OISHA_API_SECRET --data-file=- --quiet 2>nul
echo   OK or exists

echo [6/10] Creating AMOCRM_CLIENT_ID (placeholder)...
echo "changeme" | gcloud secrets create AMOCRM_CLIENT_ID --data-file=- --quiet 2>nul
echo   OK or exists

echo [7/10] Creating AMOCRM_CLIENT_SECRET (placeholder)...
echo "changeme" | gcloud secrets create AMOCRM_CLIENT_SECRET --data-file=- --quiet 2>nul
echo   OK or exists

echo [8/10] Creating AMOCRM_REDIRECT_URL (placeholder)...
echo "https://localhost" | gcloud secrets create AMOCRM_REDIRECT_URL --data-file=- --quiet 2>nul
echo   OK or exists

echo [9/10] Creating GCS_BUCKET (placeholder)...
echo "oisha-data" | gcloud secrets create GCS_BUCKET --data-file=- --quiet 2>nul
echo   OK or exists

echo [10/10] Creating GOOGLE_SERVICE_ACCOUNT_JSON (placeholder)...
echo "{}" | gcloud secrets create GOOGLE_SERVICE_ACCOUNT_JSON --data-file=- --quiet 2>nul
echo   OK or exists

echo.
echo ==========================================
echo  Deploying to Cloud Run...
echo ==========================================
echo.

cd /d "%~dp0\.."

gcloud run deploy oisha-master-bot ^
  --source . ^
  --region europe-west3 ^
  --allow-unauthenticated ^
  --memory 2Gi ^
  --cpu 2 ^
  --timeout 3600 ^
  --max-instances 3 ^
  --set-env-vars="RUNNING_IN_CLOUD=True,ENVIRONMENT=production" ^
  --set-secrets="BOT_TOKEN=BOT_TOKEN:latest,API_ID=API_ID:latest,API_HASH=API_HASH:latest,GEMINI_API_KEY=GEMINI_API_KEY:latest,OISHA_API_SECRET=OISHA_API_SECRET:latest,AMOCRM_CLIENT_ID=AMOCRM_CLIENT_ID:latest,AMOCRM_CLIENT_SECRET=AMOCRM_CLIENT_SECRET:latest,AMOCRM_REDIRECT_URL=AMOCRM_REDIRECT_URL:latest,GCS_BUCKET=GCS_BUCKET:latest,GOOGLE_SERVICE_ACCOUNT_JSON=GOOGLE_SERVICE_ACCOUNT_JSON:latest,TURSO_DATABASE_URL=TURSO_DATABASE_URL:latest,TURSO_AUTH_TOKEN=TURSO_AUTH_TOKEN:latest"

echo.
echo ==========================================
echo  Done!
echo ==========================================
pause
