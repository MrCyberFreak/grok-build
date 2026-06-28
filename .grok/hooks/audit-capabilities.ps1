<#
    audit-capabilities.ps1
    Consistency check for the HAND-MAINTAINED capability surfaces.

    The filesystem (skills/, commands/, agents/) and the runtime session menu
    (session-menu.ps1 / session-inventory.ps1) are the source of truth and update
    themselves. Two derivatives are hand-maintained and silently drift:

      1. AGENTS.md - the canonical index every CLAUDE.md points at. Capabilities can
         exist on disk but never get listed here (e.g. skill-builder never adds them).
      2. The shared "Capabilities - see the global index" block, copied into
         CLAUDE.template.md and each project's CLAUDE.md, can drift from the canonical
         block in the global CLAUDE.md.

    This script REPORTS both. With -Fix it syncs the shared CLAUDE.md block from the
    global canonical into the template + project CLAUDE.md files. It NEVER rewrites
    AGENTS.md (curated prose) - it only tells you what to add there.

    Exit code: 0 if clean (or all drift fixed), 1 if unresolved drift remains.
    ASCII-only output. Works on Windows PowerShell 5.1 and PowerShell 7.

    Usage:
      audit-capabilities.ps1                 # report only
      audit-capabilities.ps1 -Fix            # also sync the CLAUDE.md shared block
      audit-capabilities.ps1 -ProjectsRoot D:\code   # where to scan for project CLAUDE.md
#>
[CmdletBinding()]
param(
    [switch]$Fix,
    [string]$ConfigDir   = $(if ($env:GROK_HOME) { $env:GROK_HOME } else { 'X:\Grok_Build\.grok' }),
    [string]$ProjectsRoot = 'X:\Grok_Build\Projects'
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false   # native stderr (e.g. python warnings) must not abort
$drift = 0

function Write-Head([string]$t) { Write-Host ''; Write-Host $t -ForegroundColor Cyan }
function Write-Ok  ([string]$t) { Write-Host ('  OK   ' + $t) -ForegroundColor DarkGray }
function Write-Bad ([string]$t) { Write-Host ('  DRIFT ' + $t) -ForegroundColor Yellow }

# --- extract the Capabilities section ---------------------------------------
# Returns a normalized (whitespace-collapsed) body string for comparison, or $null
# if the file is missing. An absent section yields '' (which will read as drift).
function Get-CapBodyNorm([string]$path) {
    if (-not (Test-Path -LiteralPath $path)) { return $null }
    $text = Get-Content -LiteralPath $path -Raw
    if (-not $text) { return $null }
    $m = [regex]::Match($text, '(?ms)^##[ \t]+Capabilities\b[^\n]*\r?\n(.*?)(?=^##[ \t]|\z)')
    if (-not $m.Success) { return '' }
    return (($m.Groups[1].Value) -replace '\s+', ' ').Trim()
}

# Returns the full section text (heading through end-of-section), or $null.
function Get-CapSectionRaw([string]$text) {
    $m = [regex]::Match($text, '(?ms)^##[ \t]+Capabilities\b[^\n]*\r?\n.*?(?=^##[ \t]|\z)')
    if ($m.Success) { return $m.Value } else { return $null }
}

# =====================================================================
# Check 0: agent frontmatter validity + description hygiene
# =====================================================================
Write-Head 'Check 0 - agent frontmatter validity + description hygiene'
$checker = Join-Path $ConfigDir 'hooks\check_agents.py'
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command py -ErrorAction SilentlyContinue }
if ($py -and (Test-Path -LiteralPath $checker)) {
    $env:PYTHONUTF8 = '1'
    $out = & $py.Source $checker $ConfigDir 2>&1
    $code = $LASTEXITCODE
    foreach ($line in $out) { Write-Host $line }
    if ($code -ne 0) {
        Write-Bad 'one or more agent files have INVALID frontmatter - they silently de-register. Fix them.'
        $drift++
    } else {
        Write-Ok 'all agent frontmatter parses (hygiene warnings, if any, are listed above)'
    }
} else {
    Write-Host '  (python or hooks\check_agents.py not found - frontmatter validity check skipped)' -ForegroundColor DarkGray
}

# =====================================================================
# Check 1: capabilities on disk that are missing from AGENTS.md
# =====================================================================
Write-Head 'Check 1 - AGENTS.md registration'
$agentsPath = Join-Path $ConfigDir 'AGENTS.md'
$agentsText = if (Test-Path -LiteralPath $agentsPath) { Get-Content -LiteralPath $agentsPath -Raw } else { '' }
if (-not $agentsText) { Write-Bad ('AGENTS.md not found at ' + $agentsPath); $drift++ }

$onDisk = New-Object System.Collections.Generic.List[object]
# global skills: skills\<name>\SKILL.md  -> name = dir
Get-ChildItem -LiteralPath (Join-Path $ConfigDir 'skills') -Filter 'SKILL.md' -File -Recurse -ErrorAction SilentlyContinue |
    ForEach-Object { $onDisk.Add([pscustomobject]@{ Kind='skill';   Name=$_.Directory.Name }) }
# global commands: commands\**\*.md -> name = leaf without .md
Get-ChildItem -LiteralPath (Join-Path $ConfigDir 'commands') -Filter '*.md' -File -Recurse -ErrorAction SilentlyContinue |
    ForEach-Object { $onDisk.Add([pscustomobject]@{ Kind='command'; Name=$_.BaseName }) }
# global agents: agents\*.md -> name = basename
Get-ChildItem -LiteralPath (Join-Path $ConfigDir 'agents') -Filter '*.md' -File -ErrorAction SilentlyContinue |
    ForEach-Object { $onDisk.Add([pscustomobject]@{ Kind='agent';   Name=$_.BaseName }) }

$missing = @()
foreach ($cap in $onDisk) {
    # match the name as a token (allow surrounding backticks / slash / quotes)
    $rx = '(?i)(^|[^a-z0-9_-])' + [regex]::Escape($cap.Name) + '([^a-z0-9_-]|$)'
    if ($agentsText -notmatch $rx) { $missing += $cap }
}
if ($missing.Count -eq 0) {
    Write-Ok ('all ' + $onDisk.Count + ' on-disk capabilities are listed in AGENTS.md')
} else {
    foreach ($cap in ($missing | Sort-Object Kind, Name)) {
        Write-Bad ($cap.Kind + ' "' + $cap.Name + '" is on disk but NOT listed in AGENTS.md')
        $drift++
    }
    Write-Host '       -> add them to AGENTS.md (curated by hand; not auto-edited).' -ForegroundColor DarkGray
}

# =====================================================================
# Check 2: shared "Capabilities" block drift across CLAUDE.md files
# =====================================================================
Write-Head 'Check 2 - shared Capabilities block (CLAUDE.md template + projects vs global)'
$globalClaude = Join-Path $ConfigDir 'CLAUDE.md'
$canonNorm = Get-CapBodyNorm $globalClaude
if ($null -eq $canonNorm) {
    Write-Bad ('global CLAUDE.md not found at ' + $globalClaude); $drift++
} else {
    $targets = @()
    $tpl = Join-Path $ConfigDir 'CLAUDE.template.md'
    if (Test-Path -LiteralPath $tpl) { $targets += $tpl }
    if (Test-Path -LiteralPath $ProjectsRoot) {
        Get-ChildItem -LiteralPath $ProjectsRoot -Directory -ErrorAction SilentlyContinue |
            ForEach-Object {
                $c = Join-Path $_.FullName 'CLAUDE.md'
                if (Test-Path -LiteralPath $c) { $targets += $c }
            }
    }

    # canonical full section text (for -Fix), trimmed trailing whitespace
    $canonRaw = (Get-CapSectionRaw (Get-Content -LiteralPath $globalClaude -Raw)).TrimEnd()

    foreach ($t in $targets) {
        $tn = Get-CapBodyNorm $t
        $label = $t.Replace($ConfigDir, '<cfg>')
        if ($tn -eq $canonNorm) {
            Write-Ok ('in sync: ' + $label)
        } else {
            if ($Fix) {
                $txt = Get-Content -LiteralPath $t -Raw
                $sec = Get-CapSectionRaw $txt
                if ($sec) {
                    $new = $txt.Replace($sec.TrimEnd(), $canonRaw)
                } else {
                    # section absent: append it
                    $new = $txt.TrimEnd() + "`r`n`r`n" + $canonRaw + "`r`n"
                }
                Set-Content -LiteralPath $t -Value $new -Encoding UTF8 -NoNewline:$false
                Write-Host ('  FIXED ' + $label + ' (synced from global)') -ForegroundColor Green
            } else {
                Write-Bad ('out of sync: ' + $label)
                $drift++
            }
        }
    }
}

# --- next steps (roster wrap-up) -------------------------------------------
Write-Head 'Next (roster wrap-up)'
Write-Host '  - Restart the Claude Code session so agent add/edits reload (subagents load at session start).'
Write-Host '  - Smoke-test a couple of UNPROMPTED requests to confirm auto-delegation fires (do not name the agent).'
Write-Host '  - If the global config changed, run /backup-config to commit + push it (scans the staged diff for secrets).'

# --- summary ----------------------------------------------------------------
Write-Host ''
if ($drift -eq 0) {
    Write-Host 'RESULT: capability surfaces are consistent.' -ForegroundColor Green
    exit 0
} else {
    Write-Host ('RESULT: ' + $drift + ' drift item(s) found' + $(if ($Fix) { ' (CLAUDE.md blocks fixed; AGENTS.md gaps still need a hand edit).' } else { '. Re-run with -Fix to sync CLAUDE.md blocks; edit AGENTS.md by hand.' })) -ForegroundColor Yellow
    exit 1
}
