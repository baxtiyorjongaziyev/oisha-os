# Oisha-OS Enterprise Deploy Script
# Usage: ./scripts/deploy.ps1

$VM_NAME = "oisha-os-master"
$ZONE = "europe-west3-c" 
$REMOTE_PATH = "/home/baxti/oisha-os"

Write-Host "Syncing files to VPS..." -ForegroundColor Cyan

# 1. Sync files
gcloud compute scp --recurse . "${VM_NAME}:${REMOTE_PATH}" --zone=$ZONE

if ($LASTEXITCODE -eq 0) {
    Write-Host "Files uploaded successfully." -ForegroundColor Green
    
    Write-Host "Installing dependencies (pip install)..." -ForegroundColor Yellow
    gcloud compute ssh $VM_NAME --zone=$ZONE --command="cd /home/baxti/oisha-os && ./venv/bin/pip install -r requirements.txt"

    Write-Host "Restarting service..." -ForegroundColor Yellow
    gcloud compute ssh $VM_NAME --zone=$ZONE --command="sudo systemctl daemon-reload && sudo systemctl restart oisha.service && sudo systemctl status oisha.service"
    
    Write-Host "Deployment complete! Oisha-OS is active on VPS." -ForegroundColor Magenta
} else {
    Write-Host "Error during deployment. Check gcloud settings." -ForegroundColor Red
}
