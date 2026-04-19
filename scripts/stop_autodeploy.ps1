$ErrorActionPreference = "Stop"

# Stops the background auto-push watcher if it is running safely and cleanly.
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pidPath = Join-Path $projectRoot "tmp\autodeploy.pid"

if (-not (Test-Path $pidPath)) {
    Write-Output "Auto-deploy watcher is not running."
    exit 0
}

$pidValue = (Get-Content $pidPath -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
if (-not $pidValue) {
    Remove-Item $pidPath -ErrorAction SilentlyContinue
    Write-Output "Auto-deploy watcher pid file was empty."
    exit 0
}

$process = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
if (-not $process) {
    Remove-Item $pidPath -ErrorAction SilentlyContinue
    Write-Output "Auto-deploy watcher was not running."
    exit 0
}

Stop-Process -Id $pidValue -Force
Remove-Item $pidPath -ErrorAction SilentlyContinue
Write-Output "Auto-deploy watcher stopped. PID: $pidValue"
