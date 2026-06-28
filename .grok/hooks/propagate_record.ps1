<#
    propagate_record.ps1
    PostToolUse(Edit) hook. When Claude edits a "fact-bearing" file (CLAUDE.md,
    AGENTS.md, a memory note, settings/config, a workflow/cron yaml, a doc) in a
    way that changes a value-like token (a number, ISO8601 duration, clock time,
    version, cron, or ALLCAPS identifier), record the file in a per-session marker.
    The paired Stop hook (propagate_nudge.ps1) reads the marker and reminds Claude
    to propagate the change to any stale references.

    Detector only - never edits anything, never blocks. Fail-open, ASCII-only.
    Tune the three regexes below to widen/narrow what counts as a fact-bearing,
    value-bearing edit.
#>
$ErrorActionPreference = 'Stop'

try {
    $raw = [Console]::In.ReadToEnd()
    if (-not $raw) { exit 0 }
    $data = $raw | ConvertFrom-Json
} catch { exit 0 }

try {
    if ([string]$data.tool_name -ne 'Edit') { exit 0 }

    $path = [string]$data.tool_input.file_path
    if (-not $path) { exit 0 }
    $old = [string]$data.tool_input.old_string
    $new = [string]$data.tool_input.new_string

    # --- gates (tune here) -------------------------------------------------
    # Files whose values are commonly duplicated / paraphrased elsewhere.
    $FactFile = '(?i)(CLAUDE\.md|AGENTS\.md|[\\/]memory[\\/].*\.md|settings(\.local)?\.json|\.github[\\/]workflows[\\/].*\.ya?ml|[\\/]docs[\\/].*\.md)$'
    # Config files are always value-bearing; prose files (CLAUDE.md/memory/docs)
    # only count when the edited region actually changed a value-like token.
    $AlwaysConfig = '(?i)(settings(\.local)?\.json|\.ya?ml)$'
    # value-bearing edit = the edited region contains a number (covers durations
    # like PT2H, counts, clock times, versions, cron steps, thresholds).
    $ValueToken = '\d'

    if ($path -notmatch $FactFile) { exit 0 }

    $valueChanged = ($old -match $ValueToken) -or ($new -match $ValueToken)
    if (($path -notmatch $AlwaysConfig) -and (-not $valueChanged)) { exit 0 }

    # --- record ------------------------------------------------------------
    $sid = [string]$data.session_id
    if (-not $sid) { $sid = 'nosession' }
    $cacheDir = Join-Path $env:TEMP 'claude-propagate'
    if (-not (Test-Path $cacheDir)) { New-Item -ItemType Directory -Path $cacheDir -Force | Out-Null }
    $marker = Join-Path $cacheDir ($sid + '.txt')
    Add-Content -Path $marker -Value $path -Encoding utf8
} catch { }

exit 0
