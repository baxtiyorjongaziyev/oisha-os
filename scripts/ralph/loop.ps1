# Ralph Dev Loop runner (Windows PowerShell 5.1+)
# Usage: powershell -File scripts/ralph/loop.ps1 [-Plan PLAN.md] [-MaxIterations 20] [-MaxStalls 3]
#        -Plan PLAN.janitor.md  -> weekly cleanup loop (golden principles)
param(
    [string]$Plan = 'PLAN.md',
    [int]$MaxIterations = 20,
    [int]$MaxStalls = 3
)

$ErrorActionPreference = 'Stop'
$root = (git rev-parse --show-toplevel).Trim()
Set-Location $root

$dir      = Join-Path $root 'scripts/ralph'
$prompt   = (Get-Content (Join-Path $dir 'PROMPT.md') -Raw) -replace 'scripts/ralph/PLAN\.md', "scripts/ralph/$Plan"
$planPath = Join-Path $dir $Plan
$progress = Join-Path $dir 'PROGRESS.md'
$logDir   = Join-Path $dir 'logs'
New-Item -ItemType Directory -Force $logDir | Out-Null

# Guard: never loop on main
$branch = (git rev-parse --abbrev-ref HEAD).Trim()
if ($branch -in @('main', 'master')) {
    Write-Error "Refusing to run on '$branch'. Create a feat/ or fix/ branch first."
}

$env:SKIP_LIVE = '1'
$env:ALLOW_LOCAL_RUN = '0'

$allowed = @(
    'Read', 'Edit', 'Write', 'Glob', 'Grep',
    'Bash(python -m pytest*)', 'Bash(pytest*)', 'Bash(bandit*)',
    'Bash(git status*)', 'Bash(git diff*)', 'Bash(git log*)',
    'Bash(git add*)', 'Bash(git commit*)', 'Bash(git checkout -- *)'
) -join ','

$start = (git rev-parse HEAD).Trim()
$stalls = 0
for ($i = 1; $i -le $MaxIterations; $i++) {
    if (-not (Select-String -Path $planPath -Pattern '^\s*- \[ \]' -Quiet)) {
        Write-Host "All PLAN items done or blocked. Stopping."; break
    }
    if (Select-String -Path $progress -Pattern 'RALPH_DONE' -Quiet) {
        Write-Host "RALPH_DONE found. Stopping."; break
    }

    $before = (git rev-parse HEAD).Trim()
    $log = Join-Path $logDir ("iter-{0:D3}.log" -f $i)
    Write-Host "=== Iteration $i / $MaxIterations ($branch) ==="

    claude -p $prompt --allowedTools $allowed --max-turns 60 *>&1 | Tee-Object -FilePath $log

    if (Select-String -Path $log -Pattern 'Failed to authenticate|Invalid API key|Please run /login' -Quiet) {
        Write-Host "Claude CLI not authenticated. Run 'claude' then '/login', and restart the loop."; break
    }

    $after = (git rev-parse HEAD).Trim()
    if ($after -eq $before) {
        $stalls++
        Write-Host "No commit this iteration (stall $stalls / $MaxStalls)."
        if ($stalls -ge $MaxStalls) { Write-Host "Too many stalls. Stopping."; break }
    } else {
        $stalls = 0
    }
}

Write-Host "`nLoop finished. Review: git log --oneline $start..HEAD ; scripts/ralph/PROGRESS.md"

