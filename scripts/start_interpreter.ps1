$ErrorActionPreference = "Stop"

$repoRoot = "C:\Users\baxti\playground\oisha-os"
Set-Location $repoRoot

[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = "utf-8"

$python = Join-Path $repoRoot ".venv_oi\Scripts\python.exe"
if (-not (Test-Path $python)) {
  Write-Host "[INFO] Open Interpreter uchun .venv_oi (Python 3.12) yaratilmoqda..."
  & py -3.12 -m venv .venv_oi
  $python = Join-Path $repoRoot ".venv_oi\Scripts\python.exe"
  if (-not (Test-Path $python)) {
    throw "Python 3.12 topilmadi yoki .venv_oi yaratib bo'lmadi."
  }
}

& $python -m pip show open-interpreter *> $null
if ($LASTEXITCODE -ne 0) {
  Write-Host "[INFO] open-interpreter o'rnatilmoqda..."
  & $python -m pip install -U open-interpreter
}

& (Join-Path $repoRoot ".venv_oi\\Scripts\\interpreter.exe") --auto_run --safe_mode off
