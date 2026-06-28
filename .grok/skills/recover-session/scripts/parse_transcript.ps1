<#
.SYNOPSIS
  Read-only tail-parser for a Claude Code session transcript (.jsonl).

.DESCRIPTION
  Helper for the recover-session skill. When a session crashed with no handoff,
  this reconstructs "where you were" from the prior session's transcript. It
  tail-reads the last N lines, tolerantly JSON-parses each, and surfaces:

    - the LAST real user request (the typed prompt, not a tool result / meta tag)
    - the recent assistant activity (text + tool_use + tool_result), in order
    - any IN-FLIGHT tool calls (a tool_use near the end with no matching result)

  Strictly READ-ONLY: it never writes, edits, or deletes anything. ASCII-only
  output (the cp1252 console throws on curly quotes / em-dashes / emoji), so
  non-ASCII is stripped, whitespace collapsed, and long values truncated.

  Works on Windows PowerShell 5.1 and PowerShell 7.

.PARAMETER Path
  Absolute path to the .jsonl transcript to parse.

.PARAMETER Last
  How many trailing lines to scan (default 40). If the last user request is not
  found in that window (a long run of tool results pushed it out of the tail),
  the script falls back to a full-file scan just to recover that one line.

.EXAMPLE
  powershell -File parse_transcript.ps1 -Path X:\...\projects\<enc>\<id>.jsonl
.EXAMPLE
  powershell -File parse_transcript.ps1 -Path <transcript> -Last 80
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Path,
    [int]$Last = 40
)

# Read-only helper: no $ErrorActionPreference='Stop' so a single bad line never aborts.

# ---- ASCII-safe normalizer -------------------------------------------------
function Clean {
    param([string]$s, [int]$max = 200)
    if ($null -eq $s) { return '' }
    $s = $s -replace '[^\x20-\x7E\t]', ''   # drop non-ASCII (curly quotes, em-dashes, emoji)
    $s = $s -replace '\s+', ' '
    $s = $s.Trim()
    if ($s.Length -gt $max) { $s = $s.Substring(0, $max) + '...' }
    return $s
}

# ---- pull the display parts out of one message's .content -------------------
# .content may be a plain string OR a list of {type: text|tool_use|tool_result}.
function Get-Parts {
    param($content)
    $parts = New-Object System.Collections.Generic.List[object]
    if ($null -eq $content) { return $parts }
    if ($content -is [string]) {
        $parts.Add([pscustomobject]@{ Kind = 'text'; Text = $content; Name = $null; Id = $null; ResultId = $null })
        return $parts
    }
    foreach ($it in $content) {
        if ($null -eq $it) { continue }
        $t = $it.type
        if ($t -eq 'text') {
            $parts.Add([pscustomobject]@{ Kind = 'text'; Text = [string]$it.text; Name = $null; Id = $null; ResultId = $null })
        }
        elseif ($t -eq 'tool_use') {
            $inp = ''
            try { $inp = ($it.input | ConvertTo-Json -Compress -Depth 4) } catch { $inp = [string]$it.input }
            $parts.Add([pscustomobject]@{ Kind = 'tool_use'; Text = $inp; Name = [string]$it.name; Id = [string]$it.id; ResultId = $null })
        }
        elseif ($t -eq 'tool_result') {
            $rtext = ''
            $rc = $it.content
            if ($rc -is [string]) { $rtext = $rc }
            elseif ($rc) { foreach ($r in $rc) { if ($r.type -eq 'text') { $rtext += ' ' + [string]$r.text } } }
            $parts.Add([pscustomobject]@{ Kind = 'tool_result'; Text = $rtext; Name = $null; Id = $null; ResultId = [string]$it.tool_use_id })
        }
        # 'thinking' and any other part type are intentionally skipped
    }
    return $parts
}

# ---- parse an array of raw lines into user/assistant entries ----------------
function Parse-Lines {
    param([string[]]$lines)
    # non-message bookkeeping entries that carry no user/assistant turn
    $skip = @('queue-operation', 'last-prompt', 'ai-title', 'mode', 'permission-mode', 'attachment')
    $entries = New-Object System.Collections.Generic.List[object]
    foreach ($line in $lines) {
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        $o = $null
        try { $o = $line | ConvertFrom-Json } catch { continue }   # partial / non-JSON line
        if ($null -eq $o) { continue }
        if ($skip -contains $o.type) { continue }
        $msg = $o.message
        if ($null -eq $msg) { continue }                            # system / file-history-snapshot / etc.
        $role = $msg.role
        if ($role -ne 'user' -and $role -ne 'assistant') { continue }
        $entries.Add([pscustomobject]@{ Role = $role; Parts = (Get-Parts $msg.content) })
    }
    return $entries
}

# ---- last REAL user request (typed prompt, not a tool_result / meta wrapper) -
function Get-LastUserText {
    param($entries)
    for ($i = $entries.Count - 1; $i -ge 0; $i--) {
        if ($entries[$i].Role -ne 'user') { continue }
        foreach ($p in $entries[$i].Parts) {
            if ($p.Kind -eq 'text') {
                $txt = Clean $p.Text 400
                if ($txt -and -not ($txt -match '^<(command-|local-command|system-reminder)')) { return $txt }
            }
        }
    }
    return ''
}

# ============================ main ==========================================
if (-not (Test-Path -LiteralPath $Path)) {
    Write-Output "ERROR: transcript not found: $Path"
    exit 1
}

$tail = @(Get-Content -LiteralPath $Path -Encoding UTF8 | Select-Object -Last $Last)
$entries = Parse-Lines $tail

Write-Output '=== TRANSCRIPT TAIL ANALYSIS (read-only) ==='
Write-Output ("file        : " + $Path)
Write-Output ("tail lines  : " + $tail.Count + " (of last " + $Last + " requested)")
Write-Output ("turns parsed: " + $entries.Count)
Write-Output ''

# --- last user request ---
$lastUser = Get-LastUserText $entries
if (-not $lastUser) {
    # fell out of the tail window: recover just this one line from the full file
    $allEntries = Parse-Lines (@(Get-Content -LiteralPath $Path -Encoding UTF8))
    $lastUser = Get-LastUserText $allEntries
}
Write-Output '--- LAST USER REQUEST ---'
if ($lastUser) { Write-Output $lastUser } else { Write-Output '(none found)' }
Write-Output ''

# --- recent activity (chronological tail) ---
$events = New-Object System.Collections.Generic.List[string]
foreach ($e in $entries) {
    foreach ($p in $e.Parts) {
        if ($p.Kind -eq 'text') {
            $tx = Clean $p.Text
            if ($tx) { $events.Add('[' + $e.Role + ' text] ' + $tx) }
        }
        elseif ($p.Kind -eq 'tool_use') {
            $events.Add('[tool_use ' + $p.Name + '] ' + (Clean $p.Text))
        }
        elseif ($p.Kind -eq 'tool_result') {
            $events.Add('[tool_result] ' + (Clean $p.Text))
        }
    }
}
Write-Output '--- RECENT ACTIVITY (oldest -> newest) ---'
$showN = 16
$start = [Math]::Max(0, $events.Count - $showN)
if ($events.Count -eq 0) { Write-Output '(no activity in tail)' }
for ($i = $start; $i -lt $events.Count; $i++) { Write-Output $events[$i] }
Write-Output ''

# --- in-flight tool calls (tool_use with no matching tool_result) ---
$useOrder = New-Object System.Collections.Generic.List[string]
$useText = @{}
$resultIds = New-Object 'System.Collections.Generic.HashSet[string]'
foreach ($e in $entries) {
    foreach ($p in $e.Parts) {
        if ($p.Kind -eq 'tool_use' -and $p.Id) {
            $useText[$p.Id] = ($p.Name + '  ' + (Clean $p.Text))
            [void]$useOrder.Add($p.Id)
        }
        elseif ($p.Kind -eq 'tool_result' -and $p.ResultId) {
            [void]$resultIds.Add($p.ResultId)
        }
    }
}
$inflight = New-Object System.Collections.Generic.List[string]
foreach ($id in $useOrder) { if (-not $resultIds.Contains($id)) { $inflight.Add($useText[$id]) } }

Write-Output '--- IN-FLIGHT TOOL CALLS (started, no result captured) ---'
if ($inflight.Count -eq 0) { Write-Output '(none - last tool call completed)' }
else { foreach ($f in $inflight) { Write-Output $f } }
