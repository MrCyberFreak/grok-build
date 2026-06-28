#!/usr/bin/env pwsh
# lock-guard.ps1 - inspect (and optionally remove) a STALE .git/index.lock.
#
# Mirrors the global CLAUDE.md stale-lock rule: delete the lock ONLY if there is no live
# git.exe AND the lock's mtime is older than ~30s. NEVER blind-delete a lock a live git
# may own. Without -Delete it only REPORTS. With -Delete it removes a confirmed-stale lock
# via [System.IO.File]::Delete (the documented method).
#
# IMPORTANT: the delete only reaches the REAL drive when this script is run with the
# sandbox disabled (dangerouslyDisableSandbox on the tool call). A sandboxed delete reports
# success but leaves the file in place; this script detects that case and reports BUSY.
#
# Read the STATUS: line. Statuses / exit codes:
#   STATUS: NONE       - no lock; clear to proceed                              exit 0
#   STATUS: STALE-SAFE - lock present, no live git, age > threshold; removable  exit 0
#   STATUS: REMOVED    - stale lock was removed (-Delete)                       exit 0
#   STATUS: BUSY       - live git OR lock too fresh OR delete failed; wait/report exit 1
#
# ASCII-only output (the Windows console is cp1252).

[CmdletBinding()]
param(
    [string]$RepoPath = (Get-Location).Path,
    [int]$MinAgeSeconds = 30,
    [switch]$Delete
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false

try {
    $gitDir = (& git -C "$RepoPath" rev-parse --git-dir 2>$null)
    if ($LASTEXITCODE -ne 0 -or -not $gitDir) {
        Write-Host "STATUS: BUSY (not a git repo at $RepoPath)"; exit 1
    }
    # rev-parse may return a path relative to RepoPath; make it absolute
    if (-not [System.IO.Path]::IsPathRooted($gitDir)) {
        $gitDir = Join-Path $RepoPath $gitDir
    }
    $lock = Join-Path $gitDir 'index.lock'
    if (-not (Test-Path -LiteralPath $lock)) {
        Write-Host "STATUS: NONE (no .git/index.lock)"; exit 0
    }

    $liveGit = @(Get-Process -Name git -ErrorAction SilentlyContinue)
    $ageSec  = [int]((Get-Date) - (Get-Item -LiteralPath $lock).LastWriteTime).TotalSeconds

    if ($liveGit.Count -gt 0 -or $ageSec -le $MinAgeSeconds) {
        $why = if ($liveGit.Count -gt 0) { "$($liveGit.Count) live git process(es)" }
               else { "lock age ${ageSec}s <= ${MinAgeSeconds}s" }
        Write-Host "STATUS: BUSY ($why) - do NOT delete; wait and re-check."; exit 1
    }

    if ($Delete) {
        [System.IO.File]::Delete($lock)
        if (Test-Path -LiteralPath $lock) {
            Write-Host "STATUS: BUSY (delete reported success but the lock is still present - the sandbox likely intercepted it; re-run this with the sandbox disabled)."; exit 1
        }
        Write-Host "STATUS: REMOVED (stale lock deleted; no live git, age was ${ageSec}s)."; exit 0
    }

    Write-Host "STATUS: STALE-SAFE (no live git, age ${ageSec}s > ${MinAgeSeconds}s). Re-run with -Delete UNDER dangerouslyDisableSandbox to remove it."; exit 0
}
catch {
    Write-Host ("STATUS: BUSY (lock-guard error: " + $_.Exception.Message + ")"); exit 1
}
