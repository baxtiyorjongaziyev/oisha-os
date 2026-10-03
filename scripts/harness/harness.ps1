# Harness Loop Wrapper for Windows PowerShell
param(
    [string]$Target = ""
)

$ErrorActionPreference = "Stop"
$OutputEncoding = [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
$root = (git rev-parse --show-toplevel).Trim()
Set-Location $root

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Error "Virtual environment not found at .venv\Scripts\python.exe"
}

$harnessArgs = @()
if ($Target) {
    $harnessArgs += $Target
}
& $python (Join-Path $root "scripts\harness\run_harness.py") @harnessArgs
exit $LASTEXITCODE
