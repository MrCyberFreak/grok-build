<#
    build-verify-gate.ps1
    Stop hook. If this session made BIG code/UI changes that were never verified
    (state recorded by build-verify-record.ps1), soft-BLOCK finishing and tell
    Claude to run a verify pass and iterate. Stronger than a nudge - it actually
    blocks - but ONLY on big changes, and it is capped so it can never hard-lock
    a session.

      big        = accumulated change weight >= $BigWeight  OR
                   distinct code/UI files changed >= $BigFiles
      soft-block = returns {decision: block} up to $MaxBlocks times; if Claude
                   runs a verify in between, the recorder resets the weight and
                   this gate goes quiet on its own. After the cap, it degrades to
                   a one-time non-blocking nudge and clears the state.

    Below the "big" line it stays completely silent (small edits do not gate).
    Fail-open, ASCII-only.
#>
$ErrorActionPreference = 'Continue'

# --- thresholds (tune here) ------------------------------------------------
$BigWeight = 60     # ~lines of code/UI changed without a verify
$BigFiles  = 4      # OR this many distinct code/UI files touched without a verify
$MaxBlocks = 2      # never block more than this many times -> no hard-lock

try {
    $raw = [Console]::In.ReadToEnd()
    if (-not $raw) { exit 0 }
    $data = $raw | ConvertFrom-Json
} catch { exit 0 }

try {
    $sid = [string]$data.session_id
    if (-not $sid) { $sid = 'nosession' }
    $state = Join-Path (Join-Path $env:TEMP 'claude-build-verify') ($sid + '.json')
    if (-not (Test-Path $state)) { exit 0 }

    try { $s = Get-Content $state -Raw -Encoding utf8 | ConvertFrom-Json } catch { exit 0 }
    $weight = [int]$s.weight
    $files  = @($s.files)
    $blocks = [int]$s.blocks

    $big = ($weight -ge $BigWeight) -or ($files.Count -ge $BigFiles)
    if (-not $big) { exit 0 }

    $list = (($files | Select-Object -First 8) -join '; ')
    if (-not $list) { $list = '(code/UI)' }

    if ($blocks -lt $MaxBlocks) {
        # soft-block: bump the counter, refuse to stop, tell Claude what to do
        $s2 = [pscustomobject]@{ weight = $weight; files = @($files); blocks = ($blocks + 1) }
        ($s2 | ConvertTo-Json -Compress) | Set-Content -Path $state -Encoding utf8

        $reason = "BUILD-VERIFY GATE: big changes this session ($($files.Count) code/UI file(s), ~$weight lines) with NO verify run since. " +
            "Do not finish yet - verify the affected slice and iterate: render the UI with " +
            "skills/iterate/scripts/visual-verify.ps1 and Read the PNG, and/or run the tests / run the app, " +
            "fix whatever it surfaces, and repeat until it meets the bar. Changed: $list. " +
            "(Running any verify command clears this gate. If you truly cannot verify here, say so explicitly and why.)"

        (@{ decision = 'block'; reason = $reason } | ConvertTo-Json -Compress -Depth 5)
        exit 0
    }
    else {
        # cap reached: stop blocking so the session can actually end. Surface a
        # one-time NON-blocking warning to the USER via the universal systemMessage
        # field (additionalContext would instead force the turn to continue, like a
        # block - confirmed against the hooks docs), then clear state so it stops nagging.
        Remove-Item $state -Force -ErrorAction SilentlyContinue
        $msg = "BUILD-VERIFY: big changes this session went unverified ($list). " +
            "Recommend a verify pass (visual-verify screenshot + Read, tests, or run the app) before trusting it."
        (@{ systemMessage = $msg } | ConvertTo-Json -Compress -Depth 5)
        exit 0
    }
} catch { }

exit 0
