<#
    jarvis-voice.ps1 - Stop hook: auto-speak the assistant's final reply (the-voice).

    Fires on every main-agent Stop. Reads the Stop hook stdin JSON (which carries
    last_assistant_message - no transcript parsing needed), gates on the master
    toggle + guards, cleans the markdown to prose, then spawns elevenlabs-speak.ps1
    DETACHED so the session is never delayed. Always exits 0.

    Master toggle + tunables: jarvis-voice.config.json (same dir). enabled=false
    makes this a pure no-op. Guards: max_chars cap, optional only_in_paths scoping,
    code-block stripping, and de-dup so the same reply is not spoken twice.

    Stop-hook facts (claude-code-expert, live docs 2026-06-27): Stop is main-agent
    only (subagents fire SubagentStop); does NOT run on user interrupt; API-error
    turns fire StopFailure not Stop; last_assistant_message may be empty when a turn
    ends on tool_use/thinking only. ASCII-only. PS 5.1 + PS 7.
#>

$ErrorActionPreference = 'SilentlyContinue'

try { [Console]::InputEncoding = [System.Text.Encoding]::UTF8 } catch { }
$raw = [Console]::In.ReadToEnd()
if (-not $raw) { exit 0 }
try { $data = $raw | ConvertFrom-Json } catch { exit 0 }

$here    = Split-Path -Parent $MyInvocation.MyCommand.Path
$cfgPath = Join-Path $here 'jarvis-voice.config.json'
$speaker = Join-Path $here 'elevenlabs-speak.ps1'
if (-not (Test-Path -LiteralPath $cfgPath)) { exit 0 }
try { $cfg = Get-Content -LiteralPath $cfgPath -Raw | ConvertFrom-Json } catch { exit 0 }

# --- master toggle --------------------------------------------------------
if (-not $cfg.enabled) { exit 0 }

# --- text -----------------------------------------------------------------
$msg = $data.last_assistant_message
if (-not $msg -or -not "$msg".Trim()) { exit 0 }

# --- optional path scoping ------------------------------------------------
if ($cfg.only_in_paths -and @($cfg.only_in_paths).Count -gt 0) {
    $cwd = "$($data.cwd)".ToLower()
    $match = $false
    foreach ($p in @($cfg.only_in_paths)) {
        if ($cwd -and "$p" -and $cwd.StartsWith(("$p").ToLower())) { $match = $true; break }
    }
    if (-not $match) { exit 0 }
}

# --- markdown -> prose ----------------------------------------------------
$t = "$msg"
$t = [regex]::Replace($t, '(?s)```.*?```', ' ')          # fenced code blocks
$t = $t -replace '`', ''                                   # inline code ticks
$t = [regex]::Replace($t, '!\[([^\]]*)\]\([^)]*\)', '$1')  # images
$t = [regex]::Replace($t, '\[([^\]]+)\]\([^)]+\)', '$1')   # links -> text
$t = [regex]::Replace($t, '(?m)^\s{0,3}#{1,6}\s*', '')     # headings
$t = [regex]::Replace($t, '(?m)^\s*[-*+]\s+', '')          # bullets
$t = [regex]::Replace($t, '(?m)^\s*\d+\.\s+', '')          # ordered list markers
$t = $t -replace '\*\*', '' -replace '__', '' -replace '\*', '' -replace '~~', ''
$t = [regex]::Replace($t, '\s+', ' ').Trim()
if (-not $t) { exit 0 }

# --- length cap (credit + sanity guard) -----------------------------------
$max = 600
if ($cfg.max_chars) { try { $max = [int]$cfg.max_chars } catch { $max = 600 } }
if ($t.Length -gt $max) {
    $head = $t.Substring(0, $max)
    $cut  = $head.LastIndexOfAny([char[]]@('.', '!', '?'))
    if ($cut -ge 200) { $t = $head.Substring(0, $cut + 1) } else { $t = $head }
}

# --- de-dup (avoid speaking the same reply twice) -------------------------
$runDir = 'X:\Grok_Build\.grok\usage-data\jarvis-voice'
try { if (-not (Test-Path -LiteralPath $runDir)) { New-Item -ItemType Directory -Path $runDir -Force | Out-Null } } catch { }
$marker = Join-Path $runDir '.last-spoken'
$sha    = [System.Security.Cryptography.SHA1]::Create()
$hash   = [System.BitConverter]::ToString($sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($t)))
$last   = ''
if (Test-Path -LiteralPath $marker) { $last = "$(Get-Content -LiteralPath $marker -Raw)".Trim() }
if ($last -eq $hash) { exit 0 }
Set-Content -LiteralPath $marker -Value $hash -Encoding ASCII

# --- hand off to the detached speaker -------------------------------------
if (-not (Test-Path -LiteralPath $speaker)) { exit 0 }
$tmp = Join-Path $env:TEMP ('jarvis-say-' + ([guid]::NewGuid().ToString('N')) + '.txt')
Set-Content -LiteralPath $tmp -Value $t -Encoding UTF8
Start-Process -FilePath 'powershell' -WindowStyle Hidden -ArgumentList @(
    '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $speaker, '-TextFile', $tmp, '-Cleanup'
) | Out-Null

exit 0
