<#
    build-verify-record.ps1
    PostToolUse(Edit|MultiEdit|Write|Bash|PowerShell) hook. Tracks how much
    code / UI has changed this session WITHOUT a verify, in a per-session state
    file. The paired Stop hook (build-verify-gate.ps1) reads it and soft-BLOCKS
    finishing once the change is "big" and still unverified.

      - Edit/MultiEdit/Write of a code/UI source file  -> add change weight.
      - Bash/PowerShell command that looks like a verify (render screenshot,
        tests, typecheck, lint, run the app, node --check) -> RESET the weight
        (a verify happened).

    Detector only - never edits, never blocks. Fail-open, ASCII-only.
    Tune the two thresholds in build-verify-gate.ps1; tune what counts as
    code/UI or as a verify in the two regexes below.
#>
$ErrorActionPreference = 'Continue'

try {
    $raw = [Console]::In.ReadToEnd()
    if (-not $raw) { exit 0 }
    $data = $raw | ConvertFrom-Json
} catch { exit 0 }

try {
    $tool = [string]$data.tool_name
    if (-not $tool) { exit 0 }

    # --- gates (tune here) -------------------------------------------------
    # Source code + UI files (NOT docs/config: .md/.json/.yaml are excluded - the
    # propagate hook covers those). Editing these is "building/writing" code.
    $CodeExt = '(?i)\.(js|jsx|ts|tsx|mjs|cjs|vue|svelte|astro|html?|css|scss|sass|less|py|go|rs|java|kt|kts|cs|rb|php|swift|c|cc|cpp|cxx|hh?|hpp|sh|bash|ps1|psm1|sql|graphql|gql)$'
    # A command that constitutes "verifying" the work.
    $VerifySig = '(?i)(visual-verify|--screenshot|--headless|msedge.*headless|chrome.*headless|npm\s+(run\s+)?(test|build|dev|preview|start|lint|typecheck)|(pnpm|yarn|bun)\s+(run\s+)?(test|build|dev|preview|lint)|npx\s+(playwright|vitest|jest|tsc|eslint)|\bplaywright\b|\bvitest\b|\bjest\b|\bpytest\b|python\s+-m\s+pytest|\btsc\b|\beslint\b|go\s+test|cargo\s+(test|build|run)|dotnet\s+(test|build|run)|node\s+--check|localhost:\d|127\.0\.0\.1:\d)'

    $sid = [string]$data.session_id
    if (-not $sid) { $sid = 'nosession' }
    $cacheDir = Join-Path $env:TEMP 'claude-build-verify'
    if (-not (Test-Path $cacheDir)) { New-Item -ItemType Directory -Path $cacheDir -Force | Out-Null }
    $state = Join-Path $cacheDir ($sid + '.json')

    function Read-State($p) {
        if (Test-Path $p) {
            try {
                $o = Get-Content $p -Raw -Encoding utf8 | ConvertFrom-Json
                return [pscustomobject]@{
                    weight = [int]$o.weight
                    files  = @($o.files)
                    blocks = [int]$o.blocks
                }
            } catch { }
        }
        return [pscustomobject]@{ weight = 0; files = @(); blocks = 0 }
    }
    function Write-State($p, $s) {
        ([pscustomobject]@{ weight = [int]$s.weight; files = @($s.files); blocks = [int]$s.blocks } |
            ConvertTo-Json -Compress) | Set-Content -Path $p -Encoding utf8
    }
    function Count-Lines([string]$t) {
        if (-not $t) { return 0 }
        return (($t -split "`n").Count)
    }

    $s = Read-State $state

    # --- verify signal: reset the accumulator ------------------------------
    if ($tool -eq 'Bash' -or $tool -eq 'PowerShell') {
        $cmd = [string]$data.tool_input.command
        if ($cmd -and ($cmd -match $VerifySig)) {
            $s.weight = 0
            $s.files = @()
            $s.blocks = 0   # a verify resolves this episode; next batch gets a fresh cap
            Write-State $state $s
        }
        exit 0
    }

    # --- code/UI change: add weight ----------------------------------------
    $path = [string]$data.tool_input.file_path
    if (-not $path) { exit 0 }
    if ($path -notmatch $CodeExt) { exit 0 }

    $add = 0
    if ($tool -eq 'Write') {
        $add = Count-Lines ([string]$data.tool_input.content)
        if ($add -lt 20) { $add = 20 }   # a new/replaced file is substantial
    }
    elseif ($tool -eq 'Edit') {
        $old = Count-Lines ([string]$data.tool_input.old_string)
        $new = Count-Lines ([string]$data.tool_input.new_string)
        $add = [Math]::Max($old, $new)
        if ($add -lt 1) { $add = 1 }
    }
    elseif ($tool -eq 'MultiEdit') {
        foreach ($e in @($data.tool_input.edits)) {
            $old = Count-Lines ([string]$e.old_string)
            $new = Count-Lines ([string]$e.new_string)
            $add += [Math]::Max($old, $new)
        }
        if ($add -lt 1) { $add = 1 }
    }
    else { exit 0 }

    $s.weight = [int]$s.weight + [int]$add
    $s.files = @($s.files + $path | Select-Object -Unique)
    Write-State $state $s
} catch { }

exit 0
