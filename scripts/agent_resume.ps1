# Agent resume snapshot: prints everything a new agent needs to continue
# a previous agent's work. Read-only; changes nothing. Usage: powershell -NoProfile -File scripts/agent_resume.ps1
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Output '=== BRANCH ==='
git branch --show-current

Write-Output "`n=== GIT STATUS ==="
git status --short

Write-Output "`n=== DIFF STAT ==="
git diff --stat

Write-Output "`n=== ACTIVE LOCKS (AGENTS.md) ==="
$agents = Get-Content AGENTS.md
$start = ($agents | Select-String -Pattern '^## Locks' | Select-Object -First 1).LineNumber
if ($start) { $agents[$start..([Math]::Min($start + 12, $agents.Count - 1))] }

Write-Output "`n=== LAST HANDOFF ENTRY ==="
$log = Get-Content docs/agents/handoff-log.md
$idx = @(); for ($i = 0; $i -lt $log.Count; $i++) { if ($log[$i] -match '^(#{2,3}\s|- \*\*\d{4}-\d{2}-\d{2}|\d+\.\s\*\*\d{4}|- \d{4}-\d{2}-\d{2})') { $idx += $i } }
if ($idx.Count -gt 0) { $log[$idx[-1]..($log.Count - 1)] } else { $log | Select-Object -Last 40 }
