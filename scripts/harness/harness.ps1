# Harness Loop Wrapper for Windows PowerShell
param(
    [string]$Target = "",
    [switch]$Loop,
    [switch]$Commit
)

$ErrorActionPreference = "Stop"
$OutputEncoding = [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
$root = (git rev-parse --show-toplevel).Trim()
Set-Location $root

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

$scriptName = if ($Loop) { "agent_loop.py" } else { "run_harness.py" }
$scriptPath = Join-Path $root "scripts\harness\$scriptName"

$harnessArgs = @()
if ($Target) {
    $harnessArgs += $Target
}
if ($Commit) {
    $harnessArgs += "--commit"
}

& $python $scriptPath @harnessArgs
exit $LASTEXITCODE
