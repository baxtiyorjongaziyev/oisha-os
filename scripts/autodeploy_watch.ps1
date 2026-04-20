param(
    [string]$ProjectRoot = "",
    [int]$QuietSeconds = 12
)

$ErrorActionPreference = "Stop"
$CanonicalBranch = "main"

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

$script:isSyncing = $false
$script:isBlocked = $false
$script:lastEventAt = Get-Date
$script:watcher = $null
$script:timer = $null
$script:subscriptions = @()
$script:touchedPaths = New-Object 'System.Collections.Generic.HashSet[string]'
$script:baselineDirty = New-Object 'System.Collections.Generic.HashSet[string]'

$logDir = Join-Path $ProjectRoot "tmp"
$logPath = Join-Path $logDir "autodeploy.log"
$pidPath = Join-Path $logDir "autodeploy.pid"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null
Set-Content -Path $pidPath -Value $PID

function Write-Log {
    param([string]$Message)

    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$timestamp] $Message"
    Add-Content -Path $logPath -Value $line
    Write-Output $line
}

function Get-RepoRelativePath {
    param([string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return $null
    }

    $root = [System.IO.Path]::GetFullPath($ProjectRoot)
    $full = [System.IO.Path]::GetFullPath($Path)

    if (-not $full.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $null
    }

    return $full.Substring($root.Length).TrimStart('\', '/').Replace('/', '\')
}

function Should-WatchPath {
    param([string]$ChangedPath)

    if ([string]::IsNullOrWhiteSpace($ChangedPath)) {
        return $false
    }

    $fullPath = [System.IO.Path]::GetFullPath($ChangedPath)
    $normalized = $fullPath.Replace("/", "\")

    $ignoredParts = @(
        "\.git\",
        "\.venv\",
        "\__pycache__\",
        "\tmp\",
        "\tests\",
        "\docs\",
        "\data\",
        "\.pytest_cache\",
        "\node_modules\"
    )

    foreach ($part in $ignoredParts) {
        if ($normalized -like "*$part*") {
            return $false
        }
    }

    $rootFiles = @(
        (Join-Path $ProjectRoot "Dockerfile"),
        (Join-Path $ProjectRoot "requirements.txt"),
        (Join-Path $ProjectRoot "cloudbuild.yaml"),
        (Join-Path $ProjectRoot ".gcloudignore")
    )
    if ($rootFiles -contains $fullPath) {
        return $true
    }

    $watchedDirs = @("src", "scripts", "deploy", ".github")
    foreach ($dir in $watchedDirs) {
        $fullDir = (Join-Path $ProjectRoot $dir)
        if ($normalized.StartsWith($fullDir.Replace("/", "\") + "\")) {
            return $true
        }
    }

    return $false
}

function Parse-ChangedPathsFromStatusLine {
    param([string]$Line)

    if ([string]::IsNullOrWhiteSpace($Line)) {
        return @()
    }

    $payload = if ($Line.Length -gt 3) { $Line.Substring(3).Trim() } else { "" }
    if ([string]::IsNullOrWhiteSpace($payload)) {
        return @()
    }

    if ($payload -like "* -> *") {
        return $payload.Split(" -> ")
    }

    return @($payload)
}

function Get-WatchedDirtyPaths {
    Push-Location $ProjectRoot
    try {
        $statusLines = & git status --porcelain --untracked-files=all
        $paths = New-Object 'System.Collections.Generic.HashSet[string]'
        foreach ($line in $statusLines) {
            foreach ($path in (Parse-ChangedPathsFromStatusLine -Line $line)) {
                $fullPath = Join-Path $ProjectRoot $path
                if (Should-WatchPath -ChangedPath $fullPath) {
                    [void]$paths.Add($path.Replace('/', '\'))
                }
            }
        }
        return $paths
    } finally {
        Pop-Location
    }
}

function Block-Watcher {
    param([string]$Reason)

    if ($script:isBlocked) {
        return
    }

    $script:isBlocked = $true
    Write-Log "BLOCKED: $Reason"

    if ($script:timer) {
        $script:timer.Stop()
    }
    if ($script:watcher) {
        $script:watcher.EnableRaisingEvents = $false
    }
}

function Test-CanonicalBranchState {
    Push-Location $ProjectRoot
    try {
        $currentBranch = (& git branch --show-current).Trim()
        if ($currentBranch -ne $CanonicalBranch) {
            Block-Watcher "Current branch '$currentBranch' is not canonical '$CanonicalBranch'."
            return $false
        }

        & git fetch origin $CanonicalBranch --quiet
        if ($LASTEXITCODE -ne 0) {
            Block-Watcher "git fetch origin $CanonicalBranch failed."
            return $false
        }

        $counts = (& git rev-list --left-right --count "HEAD...origin/$CanonicalBranch").Trim().Split(" ", [System.StringSplitOptions]::RemoveEmptyEntries)
        if ($counts.Count -lt 2) {
            Block-Watcher "Could not compare HEAD with origin/$CanonicalBranch."
            return $false
        }

        $behind = [int]$counts[1]
        if ($behind -gt 0) {
            Block-Watcher "Local branch is behind or diverged from origin/$CanonicalBranch. Manual rebase required."
            return $false
        }

        return $true
    } finally {
        Pop-Location
    }
}

function Queue-Change {
    param([string]$ChangedPath, [string]$ChangeType)

    if ($script:isBlocked) {
        return
    }
    if (-not (Should-WatchPath -ChangedPath $ChangedPath)) {
        return
    }

    $relative = Get-RepoRelativePath -Path $ChangedPath
    if ([string]::IsNullOrWhiteSpace($relative)) {
        return
    }

    if ($script:baselineDirty.Contains($relative)) {
        [void]$script:baselineDirty.Remove($relative)
    }

    [void]$script:touchedPaths.Add($relative)
    $script:lastEventAt = Get-Date
    Write-Log "Queued auto-push after ${ChangeType}: $relative"
}

function Invoke-GitSync {
    if ($script:isSyncing -or $script:isBlocked) {
        return
    }

    $script:isSyncing = $true
    try {
        if (-not (Test-CanonicalBranchState)) {
            return
        }

        Push-Location $ProjectRoot
        try {
            $statusLines = & git status --porcelain --untracked-files=all
            $stagedPaths = New-Object 'System.Collections.Generic.HashSet[string]'

            foreach ($line in $statusLines) {
                foreach ($path in (Parse-ChangedPathsFromStatusLine -Line $line)) {
                    $normalized = $path.Replace('/', '\')
                    $fullPath = Join-Path $ProjectRoot $normalized
                    if (
                        (Should-WatchPath -ChangedPath $fullPath) -and
                        $script:touchedPaths.Contains($normalized) -and
                        (-not $script:baselineDirty.Contains($normalized))
                    ) {
                        [void]$stagedPaths.Add($normalized)
                    }
                }
            }

            if ($stagedPaths.Count -eq 0) {
                Write-Log "No eligible watched changes to push."
                return
            }

            $pythonFiles = @(
                $stagedPaths | Where-Object {
                    $_.ToLower().EndsWith(".py") -and (Test-Path (Join-Path $ProjectRoot $_))
                }
            )
            if ($pythonFiles.Count -gt 0) {
                $fullPyFiles = $pythonFiles | ForEach-Object { Join-Path $ProjectRoot $_ }
                & python -m py_compile $fullPyFiles
                if ($LASTEXITCODE -ne 0) {
                    Write-Log "Syntax check failed. Auto-push aborted."
                    return
                }
            }

            $pathSpecs = @($stagedPaths | Sort-Object)
            & git add -A -- $pathSpecs
            & git diff --cached --quiet --exit-code
            if ($LASTEXITCODE -eq 0) {
                Write-Log "No staged watched changes after filtering."
                return
            }

            $commitMessage = "chore(auto): sync $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
            & git commit -m $commitMessage
            if ($LASTEXITCODE -ne 0) {
                Write-Log "git commit failed."
                return
            }

            & git push origin "HEAD:refs/heads/$CanonicalBranch"
            if ($LASTEXITCODE -ne 0) {
                Write-Log "git push failed."
                return
            }

            foreach ($path in $pathSpecs) {
                [void]$script:touchedPaths.Remove($path)
            }
            Write-Log "Auto-push completed successfully to $CanonicalBranch."
        } finally {
            Pop-Location
        }
    } catch {
        Write-Log "Auto-push crashed: $($_.Exception.Message)"
    } finally {
        $script:isSyncing = $false
    }
}

Write-Log "Auto-push watcher starting for $ProjectRoot"
Write-Log "Canonical branch: $CanonicalBranch"

$initialDirty = Get-WatchedDirtyPaths
foreach ($path in $initialDirty) {
    [void]$script:baselineDirty.Add($path)
}
if ($script:baselineDirty.Count -gt 0) {
    Write-Log "Baseline dirty watched set captured: $($script:baselineDirty.Count) path(s)."
}

$script:watcher = New-Object System.IO.FileSystemWatcher
$script:watcher.Path = $ProjectRoot
$script:watcher.IncludeSubdirectories = $true
$script:watcher.NotifyFilter = [System.IO.NotifyFilters]'FileName, LastWrite, DirectoryName, CreationTime'
$script:watcher.EnableRaisingEvents = $true

$script:subscriptions += Register-ObjectEvent -InputObject $script:watcher -EventName Changed -Action {
    Queue-Change -ChangedPath $Event.SourceEventArgs.FullPath -ChangeType "changed"
}
$script:subscriptions += Register-ObjectEvent -InputObject $script:watcher -EventName Created -Action {
    Queue-Change -ChangedPath $Event.SourceEventArgs.FullPath -ChangeType "created"
}
$script:subscriptions += Register-ObjectEvent -InputObject $script:watcher -EventName Deleted -Action {
    Queue-Change -ChangedPath $Event.SourceEventArgs.FullPath -ChangeType "deleted"
}
$script:subscriptions += Register-ObjectEvent -InputObject $script:watcher -EventName Renamed -Action {
    Queue-Change -ChangedPath $Event.SourceEventArgs.OldFullPath -ChangeType "renamed-old"
    Queue-Change -ChangedPath $Event.SourceEventArgs.FullPath -ChangeType "renamed-new"
}

$script:timer = New-Object System.Timers.Timer
$script:timer.Interval = 3000
$script:timer.AutoReset = $true
$script:subscriptions += Register-ObjectEvent -InputObject $script:timer -EventName Elapsed -Action {
    if ($script:isBlocked -or $script:isSyncing -or $script:touchedPaths.Count -eq 0) {
        return
    }

    $secondsSinceLastEvent = ((Get-Date) - $script:lastEventAt).TotalSeconds
    if ($secondsSinceLastEvent -lt $using:QuietSeconds) {
        return
    }

    Invoke-GitSync
}
$script:timer.Start()

Write-Log "Watcher is active. Waiting for source changes."

try {
    while (-not $script:isBlocked) {
        Start-Sleep -Seconds 30
    }
} finally {
    foreach ($subscription in $script:subscriptions) {
        if ($subscription) {
            Unregister-Event -SubscriptionId $subscription.Id -ErrorAction SilentlyContinue
        }
    }
    if ($script:timer) {
        $script:timer.Stop()
        $script:timer.Dispose()
    }
    if ($script:watcher) {
        $script:watcher.EnableRaisingEvents = $false
        $script:watcher.Dispose()
    }
    Write-Log "Watcher stopped."
}
