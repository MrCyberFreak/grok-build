#!/usr/bin/env pwsh
# Pre-push secret scanner - Claude Code PreToolUse hook on `git push`.
#
# Reads the hook JSON on stdin. If the intercepted Bash command is a `git push`,
# it scans the content about to leave the machine (staged diff + commits ahead of
# the upstream, or the last few commits when there is no upstream) for high-signal
# secrets. On a hit it prints an ASCII reason to stderr and exits 2, which Claude
# Code treats as a BLOCK (the push is denied and the reason is fed back to Claude).
#
# Design choices:
#  - Only ADDED lines are scanned (removing a secret must not block the cleanup push).
#  - Patterns are high-signal to keep false positives low; a noisy guard trains people
#    to bypass it. A line carrying `allowlist secret` (or `pragma: allowlist`) is skipped.
#  - FAILS OPEN: any internal error exits 0 (allow) so a scanner bug can never wedge
#    every push globally. The /handoff and /wrap commands scan explicitly too, so this
#    hook is one layer, not the only one.
#  - All console output is ASCII (the Windows console is cp1252).

# Native git calls legitimately fail (e.g. no upstream); they must NOT throw or the
# fallback scan would be skipped. SilentlyContinue + per-call 2>$null keeps them quiet;
# the try/catch below still catches real .NET exceptions (regex/IO) and fails OPEN.
$ErrorActionPreference = 'SilentlyContinue'
$PSNativeCommandUseErrorActionPreference = $false   # native git stderr must not abort (PS 7.3+)
try {
    $raw = [Console]::In.ReadToEnd()
    if ([string]::IsNullOrWhiteSpace($raw)) { exit 0 }

    $cmd = ''
    try { $cmd = [string]($raw | ConvertFrom-Json).tool_input.command } catch { exit 0 }
    if ($cmd -notmatch 'git\s+push') { exit 0 }   # guard pushes only

    # --- gather the content about to be pushed -----------------------------------
    $parts = @()
    $staged = (& git diff --cached --unified=0 2>$null) -join "`n"
    if ($staged) { $parts += $staged }

    $upstream = (& git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>$null)
    if ($LASTEXITCODE -eq 0 -and $upstream) {
        $out = (& git diff --unified=0 "$upstream..HEAD" 2>$null) -join "`n"
    } else {
        $out = (& git log -p -n 10 --no-merges 2>$null) -join "`n"   # no upstream: heuristic
    }
    if ($out) { $parts += $out }

    $blob = $parts -join "`n"
    if (-not $blob) { exit 0 }

    # only added lines (skip '---'/'+++' headers and removals), drop allowlisted lines
    $added = ($blob -split "`n") |
        Where-Object { $_ -match '^\+' -and $_ -notmatch '^\+\+\+' } |
        Where-Object { $_ -notmatch '(?i)allowlist[ -]?secret|pragma:\s*allowlist' }
    $text = ($added -join "`n")
    if (-not $text) { exit 0 }

    # --- high-signal secret patterns ---------------------------------------------
    $patterns = [ordered]@{
        'Private key block'    = '-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----'
        'AWS access key id'    = 'AKIA[0-9A-Z]{16}'
        'GitHub token'         = 'gh[pousr]_[0-9A-Za-z]{36,}'
        'Slack token'          = 'xox[baprs]-[0-9A-Za-z-]{10,}'
        'Google API key'       = 'AIza[0-9A-Za-z_\-]{35}'
        'Quoted secret assign' = '(?i)\b(?:api[_-]?key|secret|token|access[_-]?token|password|passwd|client[_-]?secret)\b["'']?\s*[:=]\s*["''][^"'']{8,}["'']'
    }

    $hits = @()
    foreach ($name in $patterns.Keys) {
        $count = [regex]::Matches($text, $patterns[$name]).Count
        if ($count -gt 0) { $hits += ("  - {0}: {1} match(es)" -f $name, $count) }
    }

    if ($hits.Count -gt 0) {
        [Console]::Error.WriteLine("PUSH BLOCKED by secret-scan hook - possible secret(s) in the outgoing diff:")
        $hits | ForEach-Object { [Console]::Error.WriteLine($_) }
        [Console]::Error.WriteLine("Remove/rotate it, or if it is a false positive add an 'allowlist secret' marker on that line, then push again.")
        exit 2
    }
    exit 0
}
catch {
    # fail OPEN - a scanner bug must never wedge every push
    [Console]::Error.WriteLine("secret-scan hook warning (allowing push): " + $_.Exception.Message)
    exit 0
}
