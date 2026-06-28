#!/usr/bin/env pwsh
# scan-staged-diff.ps1 - secret-scan the STAGED diff before a safe-commit.
#
# Mirrors the high-signal ADDED-line patterns in hooks\scan-git-push.ps1 (keep the two
# pattern lists in sync). Scans only added lines of `git diff --cached` for the repo at
# -RepoPath. This is the deterministic gate the safe-commit skill runs before it commits.
#
# Exit codes:
#   0  - clean: no high-signal secrets staged, safe to commit
#   2  - possible secret(s) found  -> STOP, do not commit
#   3  - scanner error / not a git work tree -> STOP, investigate
#        (fails CLOSED on purpose: this is an explicit pre-commit gate the user invoked,
#         unlike the push hook which fails open so a bug can't wedge every push)
#
# ASCII-only output (the Windows console is cp1252).

[CmdletBinding()]
param([string]$RepoPath = (Get-Location).Path)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false   # native git stderr must not abort (PS 7.3+)

try {
    if (-not (Test-Path -LiteralPath $RepoPath)) {
        [Console]::Error.WriteLine("scan error: RepoPath not found: $RepoPath"); exit 3
    }
    $inside = (& git -C "$RepoPath" rev-parse --is-inside-work-tree 2>$null)
    if ($LASTEXITCODE -ne 0 -or "$inside" -ne 'true') {
        [Console]::Error.WriteLine("scan error: not a git work tree: $RepoPath"); exit 3
    }

    $diff = (& git -C "$RepoPath" diff --cached --unified=0 2>$null) -join "`n"
    if ([string]::IsNullOrWhiteSpace($diff)) {
        Write-Host "SECRET-SCAN: nothing staged - clean."; exit 0
    }

    # only ADDED lines (skip '+++' headers and removals); drop allowlisted lines
    $added = ($diff -split "`n") |
        Where-Object { $_ -match '^\+' -and $_ -notmatch '^\+\+\+' } |
        Where-Object { $_ -notmatch '(?i)allowlist[ -]?secret|pragma:\s*allowlist' }
    $text = ($added -join "`n")
    if (-not $text) { Write-Host "SECRET-SCAN: no added lines - clean."; exit 0 }

    # high-signal patterns; mirror hooks\scan-git-push.ps1 + the spec's sk_-style keys
    $patterns = [ordered]@{
        'Private key block'    = '-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----'
        'AWS access key id'    = 'AKIA[0-9A-Z]{16}'
        'GitHub token'         = 'gh[pousr]_[0-9A-Za-z]{36,}'  # allowlist secret (pattern def, not a token)
        'Slack token'          = 'xox[baprs]-[0-9A-Za-z-]{10,}'  # allowlist secret (pattern def, not a token)
        'Google API key'       = 'AIza[0-9A-Za-z_\-]{35}'
        'Stripe secret key'    = 'sk_(?:live|test)_[0-9A-Za-z]{16,}'
        'Quoted secret assign' = '(?i)\b(?:api[_-]?key|secret|token|access[_-]?token|password|passwd|client[_-]?secret)\b["'']?\s*[:=]\s*["''][^"'']{8,}["'']'
    }

    $hits = @()
    foreach ($name in $patterns.Keys) {
        $count = [regex]::Matches($text, $patterns[$name]).Count
        if ($count -gt 0) { $hits += ("  - {0}: {1} match(es)" -f $name, $count) }
    }

    if ($hits.Count -gt 0) {
        [Console]::Error.WriteLine("SECRET-SCAN BLOCKED the commit - possible secret(s) in the staged diff:")
        $hits | ForEach-Object { [Console]::Error.WriteLine($_) }
        [Console]::Error.WriteLine("Unstage/rotate it, move it to SecretStore, or (genuine false positive) add an 'allowlist secret' marker on that line, then re-run.")
        exit 2
    }
    Write-Host "SECRET-SCAN: clean - no high-signal secrets in the staged diff."
    exit 0
}
catch {
    # fail CLOSED - do not let a scanner error wave a secret through
    [Console]::Error.WriteLine("scan error (NOT committing): " + $_.Exception.Message)
    exit 3
}
