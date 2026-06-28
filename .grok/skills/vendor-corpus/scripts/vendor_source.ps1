<#
.SYNOPSIS
  Fetch ONE source URL as RAW BYTES, save it under a library's raw_src/, and
  return a SHA256 + byte count + an integrity classification as a JSON line.

.DESCRIPTION
  Helper for the /vendor-corpus skill. It does ONLY the fetch + hash + integrity
  gate for a single source; the _meta.json upsert and the source-cited corpus
  prose are owned by the SKILL.md procedure (delegated), not this script.

  It never throws on a bad fetch - a TLS failure, an HTTP error, an empty body,
  a JS single-page-app shell, a bot-challenge / interstitial, or a login wall all
  return status "pending" with a reason, and (for the suspect content cases) the
  bytes are NOT written, so a non-source is never vendored. Only genuinely-fetched
  source bytes are written to disk and reported as "vendored".

  RAW BYTES, not a lossy summary: the response body is captured verbatim via
  Invoke-WebRequest -UseBasicParsing (RawContentStream) and written byte-for-byte.
  The SHA256 is computed from the in-memory bytes AND re-verified against the bytes
  re-read from disk, so the recorded checksum provably matches what was saved.

  Windows PowerShell 5.1 compatible. Get-FileHash is tried first and falls back to
  a .NET SHA256 (Get-FileHash can be unavailable in some sessions). All output is
  ASCII-safe (cp1252 console) and the file is written UTF-8 / raw bytes. No Claude /
  AI identity is set anywhere.

.PARAMETER Url
  The source URL to fetch (mandatory).

.PARAMETER OutFile
  Absolute path to write the raw bytes to, e.g.
  X:\Grok_Build\.grok\library\<x>\raw_src\<file>.html  (mandatory).
  HTML -> .html, PDF -> .pdf, robots -> .txt (the caller chooses the extension).

.PARAMETER UserAgent
  Browser UA string. Defaults to a current desktop-Chrome UA.

.PARAMETER Fetched
  The fetch date to echo back into the JSON (e.g. 2026-06-27). The script does NOT
  invent a date - if omitted, "fetched" is null and the caller must supply it.

.PARAMETER TimeoutSec
  Per-request timeout. Default 60.

.PARAMETER KeepSuspect
  Also write the bytes for a suspect (interstitial / js-shell / login-wall)
  classification, for manual inspection. Off by default so raw_src/ stays clean of
  non-sources. (Status is still reported "pending" either way.)

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File vendor_source.ps1 -Url https://www.law.cornell.edu/uscode/text/18/1030 `
    -OutFile X:\Grok_Build\.grok\library\data-acquisition-legal-risk-expert\raw_src\cfaa-18usc1030.html `
    -Fetched 2026-06-27
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Url,
    [Parameter(Mandatory)][string]$OutFile,
    [string]$UserAgent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    [string]$Fetched,
    [int]$TimeoutSec = 60,
    [switch]$KeepSuspect
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$ProgressPreference = 'SilentlyContinue'

# Best-effort: enable the strongest TLS this PowerShell/schannel supports. Some
# sites require TLS 1.3 (not negotiable by Windows PS 5.1 schannel) and will fail
# here - that is reported as a pending fetch-error, not a crash.
try {
    [Net.ServicePointManager]::SecurityProtocol = `
        [Net.SecurityProtocolType]::Tls12 -bor `
        [Net.SecurityProtocolType]::Tls11 -bor `
        [Net.SecurityProtocolType]::Tls
} catch { }

function ConvertTo-Ascii([string]$s) {
    if ($null -eq $s) { return '' }
    return ($s -replace '[^\x20-\x7E]', '?')
}

function Get-Sha256OfBytes([byte[]]$b) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $hash = $sha.ComputeHash($b)
        return (([System.BitConverter]::ToString($hash)) -replace '-', '').ToLowerInvariant()
    } finally { $sha.Dispose() }
}

function Get-Sha256OfFile([string]$p) {
    try {
        $h = Get-FileHash -LiteralPath $p -Algorithm SHA256 -ErrorAction Stop
        return $h.Hash.ToLowerInvariant()
    } catch {
        $fb = [System.IO.File]::ReadAllBytes($p)
        return (Get-Sha256OfBytes $fb)
    }
}

function Write-Result($obj) {
    # Single compact JSON line on stdout for the skill to parse.
    Write-Output ($obj | ConvertTo-Json -Compress)
}

$result = [ordered]@{
    url            = $Url
    outFile        = $OutFile
    fetched        = $(if ($Fetched) { $Fetched } else { $null })
    status         = 'pending'
    classification = $null
    contentType    = $null
    bytes          = 0
    sha256         = $null
    reason         = $null
}

# --- fetch ------------------------------------------------------------------
$resp = $null
try {
    $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -UserAgent $UserAgent -TimeoutSec $TimeoutSec
} catch {
    $result.classification = 'fetch-error'
    $result.reason = 'Fetch failed (TLS / network / HTTP error): ' + (ConvertTo-Ascii $_.Exception.Message)
    Write-Result $result
    return
}

# --- read raw bytes ---------------------------------------------------------
$bytes = $null
try {
    $stream = $resp.RawContentStream
    if ($null -ne $stream) {
        $stream.Position = 0
        $ms = New-Object System.IO.MemoryStream
        $stream.CopyTo($ms)
        $bytes = $ms.ToArray()
        $ms.Dispose()
    }
    if (($null -eq $bytes) -or ($bytes.Length -eq 0)) {
        # Fallback: string Content -> UTF8 bytes.
        if ($resp.Content -is [byte[]]) {
            $bytes = $resp.Content
        } elseif ($resp.Content) {
            $bytes = [System.Text.Encoding]::UTF8.GetBytes([string]$resp.Content)
        }
    }
} catch {
    $result.classification = 'read-error'
    $result.reason = 'Could not read response body: ' + (ConvertTo-Ascii $_.Exception.Message)
    Write-Result $result
    return
}

if (($null -eq $bytes) -or ($bytes.Length -eq 0)) {
    $result.classification = 'empty-response'
    $result.reason = 'HTTP returned an empty body - nothing to vendor.'
    Write-Result $result
    return
}

$result.bytes = $bytes.Length
try { $result.contentType = [string]$resp.Headers['Content-Type'] } catch { }

# --- classify (is this a real source, or a shell / challenge / wall?) -------
$classification = 'ok'
$reason = $null

# PDF (and other binary) by magic bytes: not subject to HTML interstitial checks.
$magic = ''
$take = [Math]::Min(8, $bytes.Length)
for ($i = 0; $i -lt $take; $i++) {
    $c = $bytes[$i]
    if ($c -ge 32 -and $c -le 126) { $magic += [char]$c } else { $magic += '.' }
}
$isPdf = $magic.StartsWith('%PDF')

if (-not $isPdf) {
    $text = [System.Text.Encoding]::UTF8.GetString($bytes)
    $low = $text.ToLowerInvariant()
    $looksHtml = ($low -match '<html' -or $low -match '<!doctype html' -or ($result.contentType -match 'text/html'))

    $interstitialMarkers = @(
        'just a moment', 'checking your browser', 'cf-browser-verification',
        'challenge-platform', 'enable javascript', 'please enable javascript',
        'please wait while we', 'one moment', 'ddos protection by', 'attention required',
        'verifying you are human', 'captcha'
    )
    $hitMarker = $null
    foreach ($m in $interstitialMarkers) {
        if ($low.Contains($m)) { $hitMarker = $m; break }
    }

    # Visible text = body with <script>/<style> and all tags stripped.
    $stripped = [regex]::Replace($text, '(?is)<script.*?</script>', ' ')
    $stripped = [regex]::Replace($stripped, '(?is)<style.*?</style>', ' ')
    $stripped = [regex]::Replace($stripped, '(?s)<[^>]+>', ' ')
    $stripped = [regex]::Replace($stripped, '\s+', ' ').Trim()
    $visibleLen = $stripped.Length
    $hasScript = $low.Contains('<script')
    $hasPassword = ($low -match 'type\s*=\s*["'']?password')

    if ($hitMarker) {
        $classification = 'interstitial'
        $reason = "Bot-challenge / interstitial detected (marker: '$hitMarker'); this is not the source content - capture via a headless browser. NOT vendored."
    } elseif ($looksHtml -and $hasScript -and $visibleLen -lt 200 -and $bytes.Length -lt 20000) {
        $classification = 'js-shell'
        $reason = "Looks like a JavaScript single-page-app shell ($visibleLen chars of visible text, $($bytes.Length) bytes, all script); the real content renders client-side. Capture with a headless browser. NOT vendored."
    } elseif ($hasPassword -and $visibleLen -lt 500) {
        $classification = 'login-wall'
        $reason = "Looks like a login wall (password field, $visibleLen chars of visible text); the source is gated. NOT vendored."
    }
}

# --- write + integrity-verify (only for a real source) ----------------------
if ($classification -eq 'ok') {
    $dir = Split-Path -Parent $OutFile
    if ($dir -and -not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    [System.IO.File]::WriteAllBytes($OutFile, $bytes)

    $hashMem  = Get-Sha256OfBytes $bytes
    $hashDisk = Get-Sha256OfFile $OutFile
    if ($hashMem -ne $hashDisk) {
        $result.status = 'pending'
        $result.classification = 'verify-failed'
        $result.reason = "Integrity gate FAILED: in-memory hash ($hashMem) != on-disk hash ($hashDisk). Not trustworthy."
        Write-Result $result
        return
    }

    $result.status = 'vendored'
    $result.classification = $(if ($isPdf) { 'pdf' } else { 'ok' })
    $result.sha256 = $hashDisk
    $result.reason = $null
    Write-Result $result
    return
}

# --- suspect: pending, not vendored -----------------------------------------
$result.status = 'pending'
$result.classification = $classification
$result.reason = $reason
if ($KeepSuspect) {
    $dir = Split-Path -Parent $OutFile
    if ($dir -and -not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    $inspect = $OutFile + '.suspect'
    [System.IO.File]::WriteAllBytes($inspect, $bytes)
    $result.outFile = $inspect
    $result.sha256 = Get-Sha256OfFile $inspect
}
Write-Result $result
