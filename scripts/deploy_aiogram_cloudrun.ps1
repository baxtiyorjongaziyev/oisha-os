param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectId,
    [string]$Region = "us-central1",
    [string]$ServiceName = "oisha-aiogram-head",
    [string]$OwnerId = "150074828"
)

$ErrorActionPreference = "Stop"

if ($env:OISHA_ALLOW_GCP -ne "1") {
    throw "Deployment blocked. Set OISHA_ALLOW_GCP=1 only after owner approval."
}

$image = "gcr.io/$ProjectId/$ServiceName`:latest"

gcloud builds submit `
    --project $ProjectId `
    --config deploy/cloudbuild-aiogram.yaml `
    --substitutions "_IMAGE=$image" `
    .

gcloud run deploy $ServiceName `
    --project $ProjectId `
    --region $Region `
    --platform managed `
    --image $image `
    --allow-unauthenticated `
    --min-instances 0 `
    --max-instances 1 `
    --concurrency 1 `
    --cpu 1 `
    --memory 512Mi `
    --timeout 60 `
    --set-env-vars "OWNER_ID=$OwnerId,TELEGRAM_BOT_RUNTIME_BACKEND=aiogram,TELEGRAM_BOT_INGRESS_MODE=webhook,TELEGRAM_ADMIN_AIOGRAM_DISPATCHER_ENABLED=true" `
    --set-secrets "BOT_TOKEN=BOT_TOKEN:latest,TELEGRAM_WEBHOOK_SECRET=TELEGRAM_WEBHOOK_SECRET:latest,TURSO_DATABASE_URL=TURSO_DATABASE_URL:latest,TURSO_AUTH_TOKEN=TURSO_AUTH_TOKEN:latest"

$serviceUrl = gcloud run services describe $ServiceName `
    --project $ProjectId `
    --region $Region `
    --format "value(status.url)"

if (-not $serviceUrl.StartsWith("https://")) {
    throw "Cloud Run did not return a public HTTPS service URL."
}

gcloud run services update $ServiceName `
    --project $ProjectId `
    --region $Region `
    --update-env-vars "AIOGRAM_WEBHOOK_BASE_URL=$serviceUrl"

Write-Output "Aiogram cloud head deployed. Verify: $serviceUrl/healthz"
