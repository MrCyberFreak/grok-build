<#
    session-menu.ps1  -  Claude Code SessionStart hook
    ---------------------------------------------------------------------------
    Renders the session inventory (global + project agents / commands / skills /
    plugins) to the USER, right AFTER the startup splash, by returning it in the
    `systemMessage` field of the hook's JSON output.

    Why a hook and not a shell wrapper: Claude Code offers no way to print custom
    text inline between the splash and the first prompt. The one user-visible,
    after-splash surface is a hook `systemMessage` (capped at 10,000 chars).

    Contract (do not break):
      * stdout must be ONLY the JSON object -> run with `powershell -NoProfile`.
      * keep output ASCII (safe on the cp1252 console and the UTF-8 TUI).
      * never throw to stdout: emit `{}` on any error so JSON parsing can't fail.

    Registered in settings.json -> hooks.SessionStart (matcher startup|resume|clear).
#>
$ErrorActionPreference = 'Stop'

# Only the JSON object may reach stdout.
function Emit($obj) {
    [Console]::Out.Write(($obj | ConvertTo-Json -Compress))
    exit 0
}

# Map common "smart" punctuation to ASCII so descriptions stay cp1252-safe.
function To-Ascii([string]$s) {
    if (-not $s) { return '' }
    $map = @{ 0x2018='"'; 0x2019="'"; 0x201C='"'; 0x201D='"';
              0x2013='-'; 0x2014='-'; 0x2192='->'; 0x2026='...' }
    $sb = New-Object System.Text.StringBuilder
    foreach ($ch in $s.ToCharArray()) {
        $code = [int]$ch
        if ($code -lt 128) { [void]$sb.Append($ch) }
        elseif ($map.ContainsKey($code)) { [void]$sb.Append($map[$code]) }
        else { [void]$sb.Append('?') }
    }
    $sb.ToString()
}

# Pull the `description:` value out of a Markdown frontmatter file.
function Get-Desc([string]$path) {
    # -Encoding UTF8 is required: Windows PowerShell 5.1 (what `powershell` runs)
    # defaults to cp1252 and corrupts UTF-8 frontmatter (em-dashes -> mojibake).
    try { $lines = Get-Content -LiteralPath $path -TotalCount 30 -Encoding UTF8 -ErrorAction Stop } catch { return '' }
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match '^\s*description\s*:\s*(.*)$') {
            $val = $Matches[1].Trim()
            if ($val -eq '' -or $val -match '^[>|][-+]?$') {
                for ($j = $i + 1; $j -lt $lines.Count; $j++) {
                    if ($lines[$j].Trim() -ne '') { $val = $lines[$j].Trim(); break }
                }
            }
            return (To-Ascii ($val.Trim('"').Trim("'")))
        }
    }
    return ''
}

try {
    # --- read hook stdin (source + cwd) ------------------------------------
    $src = 'startup'
    $cwd = (Get-Location).Path
    $raw = $input | Out-String
    if (-not [string]::IsNullOrWhiteSpace($raw)) {
        try {
            $j = $raw | ConvertFrom-Json
            if ($j.source) { $src = [string]$j.source }
            if ($j.cwd)    { $cwd = [string]$j.cwd }
        } catch {}
    }
    # Don't redraw the menu mid-work (after /compact).
    if ($src -eq 'compact') { Emit @{} }

    $cfg = $env:GROK_HOME
    if (-not $cfg) { $cfg = 'X:\Grok_Build\.grok' }
    if (-not (Test-Path (Join-Path $cfg 'agents'))) {
        # fallback for transition
        $cfg = $env:GROK_HOME
        if (-not $cfg) { $cfg = 'X:\Grok_Build\.grok' }
    }
    $projName = Split-Path -Leaf $cwd

    # --- collect items as [name, desc] pairs -------------------------------
    $agents = @(Get-ChildItem -LiteralPath (Join-Path $cfg 'agents') -Filter '*.md' -File -EA SilentlyContinue | Sort-Object Name |
                ForEach-Object { @{ n = $_.BaseName; d = (Get-Desc $_.FullName) } })

    $cmdRoot = Join-Path $cfg 'commands'
    $cmds = @(Get-ChildItem -LiteralPath $cmdRoot -Filter '*.md' -File -Recurse -EA SilentlyContinue | Sort-Object FullName |
              ForEach-Object {
                  $rel = $_.FullName.Substring($cmdRoot.Length).TrimStart('\','/').Replace('\','/') -replace '\.md$',''
                  @{ n = '/' + $rel; d = (Get-Desc $_.FullName) } })

    $skills = @(Get-ChildItem -LiteralPath (Join-Path $cfg 'skills') -Filter 'SKILL.md' -File -Recurse -EA SilentlyContinue | Sort-Object FullName |
                ForEach-Object { @{ n = $_.Directory.Name; d = (Get-Desc $_.FullName) } })

    $mkRoot = Join-Path $cfg 'plugins\marketplaces'
    $markets = @(Get-ChildItem -LiteralPath $mkRoot -Directory -EA SilentlyContinue | Sort-Object Name |
                 ForEach-Object {
                     $sk = @(Get-ChildItem -LiteralPath $_.FullName -Filter 'SKILL.md' -File -Recurse -EA SilentlyContinue).Count
                     $ag = @(Get-ChildItem -LiteralPath $_.FullName -Directory -Filter 'agents' -Recurse -EA SilentlyContinue |
                             ForEach-Object { Get-ChildItem -LiteralPath $_.FullName -Filter '*.md' -File -EA SilentlyContinue }).Count
                     @{ n = $_.Name; d = "$sk skills, $ag agents" } })

    # project-level (prefer .grok, fallback to .claude for compat)
    $projGrok = Join-Path $cwd '.grok'
    $projClaude = Join-Path $cwd '.claude'
    $projBase = if (Test-Path (Join-Path $projGrok 'agents')) { $projGrok } elseif (Test-Path (Join-Path $projClaude 'agents')) { $projClaude } else { $projGrok }
    $pAgents = @(Get-ChildItem -LiteralPath (Join-Path $projBase 'agents') -Filter '*.md' -File -EA SilentlyContinue | Sort-Object Name |
                 ForEach-Object { @{ n = $_.BaseName; d = (Get-Desc $_.FullName) } })
    $pSkills = @(Get-ChildItem -LiteralPath (Join-Path $projBase 'skills') -Filter 'SKILL.md' -File -Recurse -EA SilentlyContinue | Sort-Object FullName |
                 ForEach-Object { @{ n = $_.Directory.Name; d = (Get-Desc $_.FullName) } })
    $pCmdRoot = Join-Path $projBase 'commands'
    if (-not (Test-Path $pCmdRoot)) { $pCmdRoot = Join-Path $projClaude 'commands' }
    $pCmds = @(Get-ChildItem -LiteralPath $pCmdRoot -Filter '*.md' -File -Recurse -EA SilentlyContinue | Sort-Object FullName |
               ForEach-Object {
                   $rel = $_.FullName.Substring($pCmdRoot.Length).TrimStart('\','/').Replace('\','/') -replace '\.md$',''
                   @{ n = '/' + $rel; d = (Get-Desc $_.FullName) } })

    # --- layout helpers ----------------------------------------------------
    $W = 78                      # target max line width
    $out = New-Object System.Collections.Generic.List[string]
    $rule = '=' * $W

    function Add-Section($title, $items, [ref]$sink, $width) {
        $sink.Value.Add('')
        $sink.Value.Add($title)
        if (-not $items -or $items.Count -eq 0) { $sink.Value.Add('  (none)'); return }
        $nameW = ($items | ForEach-Object { $_.n.Length } | Measure-Object -Maximum).Maximum
        if ($nameW -gt 34) { $nameW = 34 }      # keep full identifiers; only cut pathological names
        $descMax = $width - 4 - $nameW          # 2 indent + 2 gap
        foreach ($it in $items) {
            $name = $it.n
            if ($name.Length -gt $nameW) { $name = $name.Substring(0, $nameW) }
            $line = '  ' + $name.PadRight($nameW)
            $d = $it.d
            if ($d) {
                if ($d.Length -gt $descMax) { $d = $d.Substring(0, [Math]::Max(0, $descMax - 3)) + '...' }
                $line += '  ' + $d
            }
            $sink.Value.Add($line.TrimEnd())
        }
    }

    # --- header ------------------------------------------------------------
    function P($n, $w) { "$n $w" + $(if ($n -eq 1) { '' } else { 's' }) }
    $out.Add($rule)
    $out.Add('  CLAUDE CODE  -  ' + $projName)
    $out.Add('  ' + $cwd)
    $out.Add('  global: ' + (P $agents.Count 'agent') + ' | ' + (P $cmds.Count 'command') + ' | ' +
             (P $skills.Count 'skill') + ' | ' + (P $markets.Count 'plugin') +
             ('    project: {0}/{1}/{2} (a/s/c)' -f $pAgents.Count, $pSkills.Count, $pCmds.Count))
    $out.Add($rule)

    # --- capability-drift gate: warn if an on-disk global agent/skill is missing from AGENTS.md ---
    # Lightweight heuristic (substring presence); the canonical check is /sync-capabilities.
    try {
        $idxFile = Join-Path $cfg 'AGENTS.md'
        if (Test-Path -LiteralPath $idxFile) {
            $idxTxt = Get-Content -LiteralPath $idxFile -Raw -Encoding UTF8
            $missing = @()
            foreach ($a in $agents) { if ($idxTxt -notmatch [regex]::Escape($a.n)) { $missing += $a.n } }
            foreach ($s in $skills) { if ($idxTxt -notmatch [regex]::Escape($s.n)) { $missing += $s.n } }
            if ($missing.Count -gt 0) {
                $out.Add('  ! drift: not in AGENTS.md -> ' + ($missing -join ', ') + '  (run /sync-capabilities)')
                $out.Add($rule)
            }
        }
    } catch {}

    # --- global sections ---------------------------------------------------
    Add-Section ("GLOBAL AGENTS ($($agents.Count))")    $agents  ([ref]$out) $W
    Add-Section ("GLOBAL COMMANDS ($($cmds.Count))")     $cmds    ([ref]$out) $W
    Add-Section ("GLOBAL SKILLS ($($skills.Count))")     $skills  ([ref]$out) $W
    Add-Section ("PLUGIN MARKETPLACES ($($markets.Count))") $markets ([ref]$out) $W

    # --- project section ---------------------------------------------------
    $out.Add('')
    $out.Add('-' * $W)
    $out.Add("  PROJECT: $projName")
    if (-not (Test-Path -LiteralPath $projClaude)) {
        $out.Add('  (no .grok directory in this project)')
    } else {
        Add-Section ("  agents ($($pAgents.Count))")   $pAgents ([ref]$out) $W
        Add-Section ("  skills ($($pSkills.Count))")   $pSkills ([ref]$out) $W
        Add-Section ("  commands ($($pCmds.Count))")   $pCmds   ([ref]$out) $W
    }
    $out.Add($rule)

    $menu = ($out -join "`n")

    # systemMessage is capped at 10,000 chars; if we somehow exceed, drop the
    # descriptions and keep just the names so the menu still renders in full.
    if ($menu.Length -gt 9500) {
        $out2 = $out | ForEach-Object { ($_ -split '  ', 3)[0..1] -join '  ' }
        $menu = (($out2 -join "`n"))
        if ($menu.Length -gt 9500) { $menu = $menu.Substring(0, 9500) }
    }

    Emit @{ systemMessage = $menu }
}
catch {
    # Never break JSON parsing; stderr goes to the debug log only.
    [Console]::Error.WriteLine('session-menu hook: ' + $_.Exception.Message)
    [Console]::Out.Write('{}')
    exit 0
}
