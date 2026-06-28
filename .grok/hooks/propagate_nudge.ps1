<#
    propagate_nudge.ps1
    Stop hook. If this session recorded a value-bearing edit to a fact-bearing file
    this turn (marker written by propagate_record.ps1), inject a ONE-TIME reminder
    for Claude to propagate the change to stale references (literal AND paraphrased),
    then clear the marker. Detector / messenger only - never edits, never blocks.
    Fail-open, ASCII-only.
#>
$ErrorActionPreference = 'Stop'

try {
    $raw = [Console]::In.ReadToEnd()
    if (-not $raw) { exit 0 }
    $data = $raw | ConvertFrom-Json
} catch { exit 0 }

try {
    # Loop guard: do not re-fire when this Stop is itself a hook-induced continuation.
    if ($data.stop_hook_active -eq $true) { exit 0 }

    $sid = [string]$data.session_id
    if (-not $sid) { $sid = 'nosession' }
    $marker = Join-Path (Join-Path $env:TEMP 'claude-propagate') ($sid + '.txt')
    if (-not (Test-Path $marker)) { exit 0 }

    $files = @(Get-Content $marker -ErrorAction SilentlyContinue |
        Where-Object { $_ -and $_.Trim() } | Select-Object -Unique)
    Remove-Item $marker -Force -ErrorAction SilentlyContinue
    if ($files.Count -eq 0) { exit 0 }

    $list = (($files | Select-Object -First 12) -join '; ')
    $msg = "PROPAGATION CHECK: this turn changed value-bearing content in fact-bearing file(s): $list. " +
        "Before finishing, check whether any value / cadence / name / threshold / path / decision you changed is " +
        "referenced ELSEWHERE - as a literal OR a paraphrase (e.g. 'every 2 hours' == '7 runs/day' == 'PT2H'). " +
        "If stale references exist, run the /propagate skill to update them with reviewed diffs. " +
        "If you already reconciled them, or there are none, ignore this."

    $out = @{
        hookSpecificOutput = @{
            hookEventName     = 'Stop'
            additionalContext = $msg
        }
    }
    $out | ConvertTo-Json -Compress -Depth 5
} catch { }

exit 0
