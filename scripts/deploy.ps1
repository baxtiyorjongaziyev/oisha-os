# Oisha-OS Enterprise Deploy Script
# Usage: ./scripts/deploy.ps1

$VM_NAME = "oisha-os-master"
$ZONE = "europe-west3-c" 
$REMOTE_PATH = "/home/baxti/oisha-os"

Write-Host "[DEPLOY] Preparing Oisha for Cloud Sync..." -ForegroundColor Cyan

# 2. Sync files efficiently (skip venv, data/bot.db, and logs)
Write-Host "[SYNC] Uploading core files..." -ForegroundColor Yellow
$INCLUDE_FILES = @("src", "scripts", "main.py", "requirements.txt", "Dockerfile", ".env", "oisha_userbot.session")

foreach ($file in $INCLUDE_FILES) {
    Write-Host "Sending $file..." -ForegroundColor Gray
    gcloud compute scp --recurse $file "${VM_NAME}:${REMOTE_PATH}/" --zone=$ZONE
}

Write-Host "[SUCCESS] Files uploaded." -ForegroundColor Green

Write-Host "[DEPENDENCIES] Refreshing requirements..." -ForegroundColor Yellow
gcloud compute ssh $VM_NAME --zone=$ZONE --command="cd /home/baxti/oisha-os ; ./venv/bin/pip install -r requirements.txt"

Write-Host "[RESTART] Waking up Oisha on VPC..." -ForegroundColor Yellow
gcloud compute ssh $VM_NAME --zone=$ZONE --command="sudo systemctl daemon-reload ; sudo systemctl restart oisha.service"

Write-Host "[COMPLETE] Oisha-OS is now fully Cloud-Native!" -ForegroundColor Magenta
gcloud compute ssh $VM_NAME --zone=$ZONE --command="sudo systemctl status oisha.service"
