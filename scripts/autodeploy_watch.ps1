param(
    [string]$ProjectRoot = "",
    [int]$QuietSeconds = 12,
    [int]$PollSeconds = 6,
    [string]$Branch = "",
    [string]$GcpProject = "jonbranding-85662071-ea38e",
    [string]$ServiceName = "oisha-master-bot",
    [string]$Region = "europe-west3",
    [bool]$RunCloudDeploy = $true
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

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

function Resolve-Branch {
    if (-not [string]::IsNullOrWhiteSpace($Branch)) {
        return $Branch.Trim()
    }

    $resolved = (& git branch --show-current 2>$null | Select-Object -First 1).Trim()
    if ([string]::IsNullOrWhiteSpace($resolved)) {
        throw "Current git branch aniqlanmadi."
    }
    return $resolved
}

function Should-WatchPath {
    param([string]$ChangedPath)

    if ([string]::IsNullOrWhiteSpace($ChangedPath)) {
        return $false
    }

    $fullPath = [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot $ChangedPath))
    $normalized = $fullPath.Replace("/", "\")

    $ignoredParts = @(
        "\.git\",
        "\.venv\",
        "\__pycache__\",
        "\tmp\",
        "\data\",
        "\.pytest_cache\",
        "\node_modules\"
    )

    foreach ($part in $ignoredParts) {
        if ($normalized -like "*$part*") {
            return $false
        }
    }

    return $true
}

function Get-RepoStatusEntries {
    $raw = & git -c core.quotepath=off status --porcelain=v1 --untracked-files=all
    $entries = @()

    foreach ($line in $raw) {
        if ([string]::IsNullOrWhiteSpace($line) -or $line.Length -lt 4) {
            continue
        }

        $status = $line.Substring(0, 2)
        $pathPart = $line.Substring(3)
        $paths = @()

        if ($pathPart -like "* -> *") {
            $split = $pathPart -split " -> "
            foreach ($piece in $split) {
                if (-not [string]::IsNullOrWhiteSpace($piece)) {
                    $paths += $piece.Trim()
                }
            }
        } else {
            $paths += $pathPart.Trim()
        }

        foreach ($path in $paths) {
            if (Should-WatchPath -ChangedPath $path) {
                $entries += [PSCustomObject]@{
                    Status = $status
                    Path = $path
                }
            }
        }
    }

    return $entries
}

function Get-PathFingerprint {
    param([string]$RelativePath)

    $fullPath = Join-Path $ProjectRoot $RelativePath
    if (-not (Test-Path -LiteralPath $fullPath)) {
        return "__MISSING__"
    }

    try {
        return (Get-FileHash -Algorithm SHA256 -LiteralPath $fullPath).Hash
    } catch {
        return "__UNREADABLE__"
    }
}

function New-BaselineSnapshot {
    $snapshot = @{}
    $entries = Get-RepoStatusEntries
    foreach ($entry in $entries) {
        $snapshot[$entry.Path] = Get-PathFingerprint -RelativePath $entry.Path
    }
    return $snapshot
}

function Get-CommitCandidates {
    param([hashtable]$BaselineSnapshot)

    $entries = Get-RepoStatusEntries
    $grouped = @{}

    foreach ($entry in $entries) {
        $path = $entry.Path
        $fingerprint = Get-PathFingerprint -RelativePath $path
        $isCandidate = $false

        if (-not $BaselineSnapshot.ContainsKey($path)) {
            $isCandidate = $true
        } elseif ($BaselineSnapshot[$path] -ne $fingerprint) {
            $isCandidate = $true
        }

        if ($isCandidate) {
            $grouped[$path] = $entry.Status
        }
    }

    return $grouped.Keys | Sort-Object
}

function Has-RemoteBranch {
    param([string]$TargetBranch)
    & git ls-remote --exit-code --heads origin $TargetBranch *> $null
    return ($LASTEXITCODE -eq 0)
}

function Invoke-GitSync {
    param(
        [string[]]$Paths,
        [string]$TargetBranch
    )

    if (-not $Paths -or $Paths.Count -eq 0) {
        Write-Log "No new watched changes to commit."
        return $false
    }

    Write-Log "🚀 Auto sync started for branch '$TargetBranch' ($($Paths.Count) path)."
    Push-Location $ProjectRoot
    try {
        $addArgs = @("add", "-A", "--") + $Paths
        & git @addArgs
        if ($LASTEXITCODE -ne 0) {
            Write-Log "⚠️ git add failed."
            return $false
        }

        & git diff --cached --quiet --exit-code
        if ($LASTEXITCODE -eq 0) {
            Write-Log "No staged diff after filtering. Skipping commit."
            return $false
        }

        $commitMessage = "chore(auto): sync $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
        & git commit -m $commitMessage
        if ($LASTEXITCODE -ne 0) {
            Write-Log "⚠️ git commit failed."
            return $false
        }

        if (Has-RemoteBranch -TargetBranch $TargetBranch) {
            & git fetch origin $TargetBranch
            if ($LASTEXITCODE -ne 0) {
                Write-Log "⚠️ git fetch failed."
                return $false
            }

            $remoteRef = "refs/remotes/origin/$TargetBranch"
            $remoteSha = (& git rev-parse $remoteRef 2>$null | Select-Object -First 1).Trim()
            $mergeBase = (& git merge-base HEAD $remoteRef 2>$null | Select-Object -First 1).Trim()

            if (-not [string]::IsNullOrWhiteSpace($remoteSha) -and $mergeBase -ne $remoteSha) {
                Write-Log "⚠️ Remote branch oldinga ketgan yoki diverged. Manual rebase kerak."
                return $false
            }

            & git push origin "HEAD:refs/heads/$TargetBranch"
        } else {
            & git push -u origin "HEAD:refs/heads/$TargetBranch"
        }

        if ($LASTEXITCODE -eq 0) {
            Write-Log "✅ Auto push muvaffaqiyatli bo'ldi."
            return $true
        }

        Write-Log "⚠️ git push failed (Exit Code: $LASTEXITCODE)."
        return $false
    } catch {
        Write-Log "🚨 Auto sync crashed: $($_.Exception.Message)"
        return $false
    } finally {
        Pop-Location
    }
}

function Invoke-CloudDeploy {
    if (-not $RunCloudDeploy) {
        Write-Log "Cloud deploy disabled. Push only mode."
        return $true
    }

    Write-Log "☁️ Cloud Build deploy boshlandi."
    Push-Location $ProjectRoot
    $deployRoot = Join-Path $logDir "deploy_worktree"
    try {
        if (Test-Path -LiteralPath $deployRoot) {
            & git worktree remove --force $deployRoot *> $null
            Remove-Item -LiteralPath $deployRoot -Recurse -Force -ErrorAction SilentlyContinue
        }

        & git worktree add --detach $deployRoot HEAD
        if ($LASTEXITCODE -ne 0) {
            Write-Log "⚠️ Clean deploy worktree yaratilmadi."
            return $false
        }

        & gcloud builds submit `
            --project=$GcpProject `
            --config=cloudbuild.yaml `
            --substitutions="_SERVICE_NAME=$ServiceName,_DEPLOY_REGION=$Region" `
            $deployRoot

        if ($LASTEXITCODE -eq 0) {
            Write-Log "✅ Cloud deploy muvaffaqiyatli bo'ldi."
            return $true
        }

        Write-Log "⚠️ Cloud deploy failed (Exit Code: $LASTEXITCODE)."
        return $false
    } catch {
        Write-Log "🚨 Cloud deploy crashed: $($_.Exception.Message)"
        return $false
    } finally {
        & git worktree remove --force $deployRoot *> $null
        Remove-Item -LiteralPath $deployRoot -Recurse -Force -ErrorAction SilentlyContinue
        Pop-Location
    }
}

Write-Log "Auto-deploy watcher starting for $ProjectRoot"
Push-Location $ProjectRoot
try {
    $targetBranch = Resolve-Branch
    Write-Log "Watching current branch: $targetBranch"
    $baselineSnapshot = New-BaselineSnapshot
    if ($baselineSnapshot.Count -gt 0) {
        Write-Log "Baseline dirty set captured: $($baselineSnapshot.Count) path. Ular o'zgarmaguncha auto-push qilinmaydi."
    }

    $lastCandidateSignature = ""
    $firstSeenAt = $null

    while ($true) {
        $candidatePaths = @(Get-CommitCandidates -BaselineSnapshot $baselineSnapshot)

        if ($candidatePaths.Count -eq 0) {
            $lastCandidateSignature = ""
            $firstSeenAt = $null
            Start-Sleep -Seconds $PollSeconds
            continue
        }

        $signature = ($candidatePaths -join "|")
        if ($signature -ne $lastCandidateSignature) {
            $lastCandidateSignature = $signature
            $firstSeenAt = Get-Date
            Write-Log "Queued auto-push for: $($candidatePaths -join ', ')"
            Start-Sleep -Seconds $PollSeconds
            continue
        }

        if (-not $firstSeenAt) {
            $firstSeenAt = Get-Date
            Start-Sleep -Seconds $PollSeconds
            continue
        }

        $elapsed = ((Get-Date) - $firstSeenAt).TotalSeconds
        if ($elapsed -lt $QuietSeconds) {
            Start-Sleep -Seconds $PollSeconds
            continue
        }

        $successful = Invoke-GitSync -Paths $candidatePaths -TargetBranch $targetBranch
        if ($successful) {
            Invoke-CloudDeploy | Out-Null
            foreach ($path in $candidatePaths) {
                $baselineSnapshot[$path] = Get-PathFingerprint -RelativePath $path
            }
        }

        $lastCandidateSignature = ""
        $firstSeenAt = $null
        Start-Sleep -Seconds $PollSeconds
    }
} finally {
    Pop-Location
    Write-Log "Watcher stopped."
}
