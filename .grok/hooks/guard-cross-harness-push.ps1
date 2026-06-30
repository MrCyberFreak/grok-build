#!/usr/bin/env pwsh
# Cross-harness push guard - git pre-push hook (repo-aware).
#
# Blocks a push that drags the OTHER harness's path convention into THIS repo,
# preventing Claude Code config <-> Grok Build harness crossover (the recurring
# root cause behind GROK_HOME / X:\Grok_Build paths leaking into claude-code-config,
# and the reverse leaking into grok-build).
#
# Picks the forbidden set from the origin remote:
#   - claude-code-config  -> forbid Grok markers   (GROK_HOME, X:\Grok_Build\)
#   - grok-build          -> forbid Claude markers (CLAUDE_CONFIG_DIR, X:\Claude_Code\Global\)
#   - any other repo      -> no-op (exit 0)
#
# Scans ONLY added lines in the commits about to be pushed (read from the pre-push
# stdin: "<localref> <localsha> <remoteref> <remotesha>" per line). Skips
# documentation / data areas (library, handoffs, memory, projects, ...) and the two
# self-referential files (this guard + the backup-config skill), and any line tagged
# 'allowlist cross-harness'. FAILS OPEN on any internal error (exit 0) so a bug here
# can never wedge every push. All console output is ASCII (cp1252 console).

$ErrorActionPreference = 'SilentlyContinue'
$PSNativeCommandUseErrorActionPreference = $false   # no-op on WinPS 5.1; safe on PS 7.3+
$ZERO = '^0{40,64}$'

try {
    $stdin = [Console]::In.ReadToEnd()

    $remote = (& git remote get-url origin 2>$null)
    if (-not $remote) { exit 0 }

    if ($remote -match 'claude-code-config') {
        $label = 'Grok-harness'
        $forbidden = [ordered]@{
            'GROK_HOME variable'  = 'GROK_HOME'
            'X:\Grok_Build\ path' = 'X:[\\/]Grok_Build[\\/]'
        }
    }
    elseif ($remote -match 'grok-build') {
        $label = 'Claude-config'
        $forbidden = [ordered]@{
            'CLAUDE_CONFIG_DIR variable'  = 'CLAUDE_CONFIG_DIR'
            'X:\Claude_Code\Global\ path' = 'X:[\\/]Claude_Code[\\/]Global'
        }
    }
    else { exit 0 }   # not one of the two harness repos - do nothing

    # docs / data / self-referential paths that may legitimately name the other harness
    $skipRe = '(^|/)(library|handoffs|plugins|plugins-seed|cache|raw_src|_ref|projects|sessions|file-history|backups|paste-cache)/|/memory/|backup-config/SKILL\.md$|guard-cross-harness-push\.ps1$'

    # --- collect the diffs of the commits about to be pushed ---------------------
    $diffs = New-Object System.Collections.Generic.List[string]
    foreach ($line in ($stdin -split "`n")) {
        $f = ($line.Trim() -split '\s+')
        if ($f.Count -lt 4) { continue }
        $localSha = $f[1]; $remoteSha = $f[3]
        if ($localSha -match $ZERO) { continue }                 # ref being deleted
        if ($remoteSha -match $ZERO) {
            # new branch on the remote: scan only commits not already on any origin ref
            $new = (& git rev-list $localSha --not --remotes=origin 2>$null) -split "`n" | Where-Object { $_ }
            if (-not $new) { continue }
            $oldest = $new[-1]
            $base = (& git rev-parse "$oldest^" 2>$null)
            if (-not $base -or $LASTEXITCODE -ne 0) { $base = '4b825dc642cb6eb9a060e54bf8d69288fbee4904' } # empty tree
            $d = (& git diff --unified=0 "$base..$localSha" 2>$null) -join "`n"
        }
        else {
            $d = (& git diff --unified=0 "$remoteSha..$localSha" 2>$null) -join "`n"
        }
        if ($d) { $diffs.Add($d) }
    }
    # fallback for a manual/ad-hoc run with no stdin: compare HEAD to its upstream
    if ($diffs.Count -eq 0) {
        $up = (& git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>$null)
        if ($LASTEXITCODE -eq 0 -and $up) {
            $d = (& git diff --unified=0 "$up..HEAD" 2>$null) -join "`n"
            if ($d) { $diffs.Add($d) }
        }
    }
    if ($diffs.Count -eq 0) { exit 0 }

    # --- walk the unified diff: track file, scan added lines ----------------------
    $curFile = ''
    $hits = [ordered]@{}
    foreach ($ln in (($diffs -join "`n") -split "`n")) {
        if ($ln -like '+++ b/*') { $curFile = $ln.Substring(6); continue }
        if ($ln -like '+++*') { continue }            # +++ /dev/null etc.
        if ($ln -notmatch '^\+') { continue }          # only ADDED lines
        if ($curFile -match $skipRe) { continue }       # docs / self-referential
        if ($ln -match '(?i)allowlist cross-harness') { continue }
        foreach ($name in $forbidden.Keys) {
            if ($ln -match $forbidden[$name]) {
                if (-not $hits.Contains($name)) { $hits[$name] = 0 }
                $hits[$name]++
            }
        }
    }

    if ($hits.Count -gt 0) {
        [Console]::Error.WriteLine("PUSH BLOCKED by cross-harness guard - $label path(s) in the outgoing diff of this repo:")
        foreach ($k in $hits.Keys) { [Console]::Error.WriteLine(("  - {0}: {1} added line(s)" -f $k, $hits[$k])) }
        [Console]::Error.WriteLine("This repo must not reference the other harness. Convert the path (GROK_HOME <-> CLAUDE_CONFIG_DIR,")
        [Console]::Error.WriteLine("X:\Grok_Build\.grok <-> X:\Claude_Code\Global), or tag an intentional line 'allowlist cross-harness', then push again.")
        exit 1
    }
    exit 0
}
catch {
    [Console]::Error.WriteLine("cross-harness guard warning (allowing push): " + $_.Exception.Message)
    exit 0
}
