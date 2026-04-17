param(
    [string]$ProjectRoot = "",
    [int]$QuietSeconds = 12
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

$script:pendingChange = $false
$script:isDeploying = $false
$script:lastEventAt = Get-Date
$script:watcher = $null
$script:timer = $null
$script:subscriptions = @()

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

function Invoke-GitSync {
    if ($script:isDeploying) {
        Write-Log "Sync already running. New request queued."
        return
    }

    $script:isDeploying = $true
    try {
        Write-Log "🚀 Git Sync started."
        Push-Location $ProjectRoot

        # Check if there are changes
        $status = & git status --porcelain
        if ([string]::IsNullOrWhiteSpace($status)) {
            Write-Log "No changes detected. Skipping push."
            return
        }

        # 1. Compile check (optional but good for Python)
        $srcDir = Join-Path $ProjectRoot "src"
        if (Test-Path $srcDir) {
            Write-Log "Checking syntax..."
            $pyFiles = Get-ChildItem -Path $srcDir -Recurse -Filter *.py -File | Select-Object -ExpandProperty FullName
            if ($pyFiles) {
                & python -m py_compile $pyFiles
                if ($LASTEXITCODE -ne 0) {
                    Write-Log "❌ Syntax error detected. Push aborted."
                    return
                }
            }
        }

        # 2. Git Automation
        Write-Log "Committing changes..."
        & git add .
        & git commit -m "🚀 auto-deploy: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
        
        Write-Log "Pushing to GitHub..."
        & git pull --rebase origin main
        & git push origin main
        
        if ($LASTEXITCODE -eq 0) {
            Write-Log "✅ Sync & Push successful!"
        } else {
            Write-Log "⚠️ Push failed (Exit Code: $LASTEXITCODE). Check for conflicts."
        }
    } catch {
        Write-Log "🚨 Sync crashed: $($_.Exception.Message)"
    } finally {
        Pop-Location
        $script:isDeploying = $false
    }
}

function Queue-Deploy {
    param([string]$ChangedPath, [string]$ChangeType)

    if (-not (Should-WatchPath -ChangedPath $ChangedPath)) {
        return
    }

    $script:lastEventAt = Get-Date
    $script:pendingChange = $true
    Write-Log "Queued deploy after ${ChangeType}: $ChangedPath"
}

Write-Log "Auto-deploy watcher starting for $ProjectRoot"

$script:watcher = New-Object System.IO.FileSystemWatcher
$script:watcher.Path = $ProjectRoot
$script:watcher.IncludeSubdirectories = $true
$script:watcher.NotifyFilter = [System.IO.NotifyFilters]'FileName, LastWrite, DirectoryName, CreationTime'
$script:watcher.EnableRaisingEvents = $true

$script:subscriptions += Register-ObjectEvent -InputObject $script:watcher -EventName Changed -Action {
    Queue-Deploy -ChangedPath $Event.SourceEventArgs.FullPath -ChangeType "changed"
}
$script:subscriptions += Register-ObjectEvent -InputObject $script:watcher -EventName Created -Action {
    Queue-Deploy -ChangedPath $Event.SourceEventArgs.FullPath -ChangeType "created"
}
$script:subscriptions += Register-ObjectEvent -InputObject $script:watcher -EventName Deleted -Action {
    Queue-Deploy -ChangedPath $Event.SourceEventArgs.FullPath -ChangeType "deleted"
}
$script:subscriptions += Register-ObjectEvent -InputObject $script:watcher -EventName Renamed -Action {
    Queue-Deploy -ChangedPath $Event.SourceEventArgs.FullPath -ChangeType "renamed"
}

$script:timer = New-Object System.Timers.Timer
$script:timer.Interval = 3000
$script:timer.AutoReset = $true
$script:subscriptions += Register-ObjectEvent -InputObject $script:timer -EventName Elapsed -Action {
    if (-not $script:pendingChange) {
        return
    }
    if ($script:isDeploying) {
        return
    }
    $secondsSinceLastEvent = ((Get-Date) - $script:lastEventAt).TotalSeconds
    if ($secondsSinceLastEvent -lt $using:QuietSeconds) {
        return
    }

    $script:pendingChange = $false
    Invoke-GitSync
}
$script:timer.Start()

Write-Log "Watcher is active. Waiting for source changes."

try {
    while ($true) {
        Start-Sleep -Seconds 60
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
