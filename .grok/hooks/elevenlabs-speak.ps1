<#
    elevenlabs-speak.ps1 - reusable ElevenLabs Text-to-Speech engine (the-voice).

    Synthesizes spoken audio from text via the ElevenLabs REST API and plays it on
    Windows. Usable two ways:
      1. Manually:   .\elevenlabs-speak.ps1 -Text "Welcome home, sir."
      2. From the Stop hook (jarvis-voice.ps1), which writes the reply to a temp
         file and spawns this script detached:  -TextFile <path> -Cleanup

    The API key NEVER lives in this file or in config - it is read at runtime from
    PowerShell SecretStore by the name in jarvis-voice.config.json (secret_name).
    Voice / model / settings come from that same config; CLI params override.

    ASCII-only output. Works on Windows PowerShell 5.1 and PowerShell 7.

    Grounded on ElevenLabs live docs (via elevenlabs-expert, 2026-06-27):
      endpoint POST /v1/text-to-speech/{voice_id}; header xi-api-key;
      low-latency model eleven_flash_v2_5; default voice George JBFqnCBsd6RMkjVDRZzb;
      output_format mp3_44100_128; -OutFile to avoid binary-string corruption.
#>
[CmdletBinding()]
param(
    [string]$Text,
    [string]$TextFile,
    [string]$VoiceId,
    [string]$ModelId,
    [switch]$Cleanup
)

$ErrorActionPreference = 'Stop'

$cfgPath = Join-Path $PSScriptRoot 'jarvis-voice.config.json'
$logDir  = 'X:\Grok_Build\.grok\usage-data\jarvis-voice'
$logFile = Join-Path $logDir 'speak.log'

function Write-Log([string]$m) {
    try {
        if (-not (Test-Path -LiteralPath $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
        $stamp = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
        Add-Content -LiteralPath $logFile -Value "[$stamp] $m" -Encoding ASCII
    } catch { }
}

function Remove-Temp {
    if ($script:mp3 -and (Test-Path -LiteralPath $script:mp3)) { Remove-Item -LiteralPath $script:mp3 -ErrorAction SilentlyContinue }
    if ($Cleanup -and $TextFile -and (Test-Path -LiteralPath $TextFile)) { Remove-Item -LiteralPath $TextFile -ErrorAction SilentlyContinue }
}

# --- config ---------------------------------------------------------------
$cfg = $null
if (Test-Path -LiteralPath $cfgPath) {
    try { $cfg = Get-Content -LiteralPath $cfgPath -Raw | ConvertFrom-Json } catch { $cfg = $null }
}
$secretName = if ($cfg -and $cfg.secret_name) { $cfg.secret_name } else { 'ElevenLabsApiKey' }
if (-not $VoiceId) { $VoiceId = if ($cfg -and $cfg.voice_id) { $cfg.voice_id } else { 'JBFqnCBsd6RMkjVDRZzb' } }
if (-not $ModelId) { $ModelId = if ($cfg -and $cfg.model_id) { $cfg.model_id } else { 'eleven_flash_v2_5' } }
$outFormat  = if ($cfg -and $cfg.output_format) { $cfg.output_format } else { 'mp3_44100_128' }
if ($cfg -and $cfg.voice_settings) {
    $vs = $cfg.voice_settings
} else {
    $vs = [pscustomobject]@{ stability = 0.70; similarity_boost = 0.75; style = 0.0; use_speaker_boost = $true; speed = 0.95 }
}

# --- text -----------------------------------------------------------------
if ($TextFile -and (Test-Path -LiteralPath $TextFile)) {
    try { $Text = Get-Content -LiteralPath $TextFile -Raw -Encoding UTF8 } catch { }
}
if (-not $Text -or -not $Text.Trim()) { Write-Log 'no text - nothing to speak'; Remove-Temp; return }

# --- API key from SecretStore --------------------------------------------
function Get-ElevenKey([string]$name) {
    if (-not (Get-Module -ListAvailable -Name Microsoft.PowerShell.SecretManagement)) {
        # OneDrive/Documents PSModulePath quirk: module may live off-path. Prepend likely roots.
        $docs = @(
            [Environment]::GetFolderPath('MyDocuments'),
            (Join-Path $env:USERPROFILE 'Documents'),
            (Join-Path $env:USERPROFILE 'OneDrive\Documents')
        ) | Where-Object { $_ } | Select-Object -Unique
        foreach ($d in $docs) {
            foreach ($sub in @('PowerShell\Modules','WindowsPowerShell\Modules')) {
                $p = Join-Path $d $sub
                if (Test-Path -LiteralPath $p) { $env:PSModulePath = "$p;$($env:PSModulePath)" }
            }
        }
    }
    Import-Module Microsoft.PowerShell.SecretManagement -ErrorAction Stop
    Get-Secret -Name $name -AsPlainText -ErrorAction Stop
}

try { $apiKey = Get-ElevenKey $secretName }
catch { Write-Log ("could not load secret '$secretName' from SecretStore: " + $_.Exception.Message); Remove-Temp; return }
if (-not $apiKey) { Write-Log "secret '$secretName' is empty"; Remove-Temp; return }

# --- synthesize -----------------------------------------------------------
$script:mp3 = Join-Path $env:TEMP ('jarvis-voice-' + ([guid]::NewGuid().ToString('N')) + '.mp3')
$uri = "https://api.elevenlabs.io/v1/text-to-speech/$VoiceId" + "?output_format=$outFormat"

$bodyObj = [pscustomobject]@{
    text           = $Text
    model_id       = $ModelId
    voice_settings = $vs
}
$bodyJson  = $bodyObj | ConvertTo-Json -Depth 6
$bodyBytes = [System.Text.Encoding]::UTF8.GetBytes($bodyJson)   # force UTF-8 (cp1252 console would mangle non-ASCII)

try {
    Invoke-RestMethod -Uri $uri -Method Post `
        -Headers @{ 'xi-api-key' = $apiKey } `
        -ContentType 'application/json' `
        -Body $bodyBytes `
        -OutFile $script:mp3
} catch {
    $detail = $_.Exception.Message
    try {
        if ($_.Exception.Response) {
            $sr = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
            $detail += ' | ' + $sr.ReadToEnd()
        }
    } catch { }
    Write-Log ("TTS request failed: " + $detail)
    Remove-Temp
    return
}

if (-not (Test-Path -LiteralPath $script:mp3) -or (Get-Item -LiteralPath $script:mp3).Length -lt 200) {
    Write-Log 'TTS returned no / tiny audio'
    Remove-Temp
    return
}

# --- play (blocking, headless) -------------------------------------------
$played = $false
try {
    $wmp = New-Object -ComObject WMPlayer.OCX
    $wmp.settings.volume = 100
    $wmp.settings.autoStart = $true
    $wmp.URL = $script:mp3
    $null = $wmp.controls.play()
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    # wait for playback to actually start (1=Stopped 3=Playing 6=Buffering 9=Transitioning 10=Ready)
    while ($wmp.playState -ne 3 -and $sw.Elapsed.TotalSeconds -lt 12) { Start-Sleep -Milliseconds 100 }
    # then wait for it to finish
    while ($wmp.playState -eq 3 -and $sw.Elapsed.TotalSeconds -lt 600) { Start-Sleep -Milliseconds 150 }
    $wmp.controls.stop()
    [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($wmp)
    $played = $true
} catch {
    Write-Log ('WMPlayer playback failed, falling back: ' + $_.Exception.Message)
}
if (-not $played) {
    try { Start-Process -FilePath $script:mp3 | Out-Null; Start-Sleep -Seconds 5 } catch { Write-Log ('fallback play failed: ' + $_.Exception.Message) }
}

Write-Log ('spoke ' + $Text.Length + ' chars (voice ' + $VoiceId + ', model ' + $ModelId + ')')
Start-Sleep -Milliseconds 250
Remove-Temp
