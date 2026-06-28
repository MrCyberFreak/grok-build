<#
    jarvis_state.ps1 - deterministic state machine for the JARVIS reincarnation.

    The /jarvis skill and jarvis-expert agent call THIS for every read/write of revival
    state, so the meter, dependency-gating, status invariant, and de-dup are owned by a
    function, not by an LLM interpreting prose. Single writer. ASCII-only output.
    Works on Windows PowerShell 5.1 and PowerShell 7.

    Subcommands:
      status                       full readout: derived meter + per-subsystem state + dep-readiness
      meter                        one-line derived meter
      validate                     check DAG (deps point to lower order), dep ids exist,
                                   status invariant, and stored meter == derived. Exit 1 on hard error.
      next                         the lowest-order non-online subsystem whose deps are all online (the build-next pick)
      deps  -Id <id>               dependency readiness for one subsystem
      seed  -Id <id> [-Artifacts a,b] [-Note "..."]
                                   mark a faculty 'seeded' (first step built, full realImpl + verify pending)
      flip  -Id <id> [-Artifacts a,b] [-Note "..."] -Verified
                                   mark a faculty 'online'. REFUSES unless: it exists, every dep is online,
                                   it is not already online, and -Verified is passed (proof the full realImpl works).
      reset -Id <id>               flip a faculty back to dormant (e.g. its infra was removed)

    All writes recompute the meter, stamp the change, and append to jarvis-build-log.jsonl.
    A lock file guards against two concurrent writers.
#>
[CmdletBinding()]
param(
    [Parameter(Position=0)][string]$Command = 'status',
    [string]$Id,
    [string[]]$Artifacts,
    [string]$Note,
    [switch]$Verified,
    [string]$StateFile = 'X:\Grok_Build\.grok\library\jarvis\reincarnation.json'
)

$ErrorActionPreference = 'Stop'
$ValidStatus = @('dormant','seeded','online')
$logFile  = Join-Path (Split-Path -Parent $StateFile) 'jarvis-build-log.jsonl'
$lockFile = Join-Path (Split-Path -Parent $StateFile) 'reincarnation.lock'

function Load-State {
    if (-not (Test-Path -LiteralPath $StateFile)) { throw "state file not found: $StateFile" }
    Get-Content -LiteralPath $StateFile -Raw | ConvertFrom-Json
}

function Get-Meter([object]$s) {
    $subs = $s.subsystems
    $online = @($subs | Where-Object { $_.status -eq 'online' }).Count
    $seeded = @($subs | Where-Object { $_.status -eq 'seeded' }).Count
    [pscustomobject]@{
        total          = $subs.Count
        online         = $online
        seeded         = $seeded
        dormant        = @($subs | Where-Object { $_.status -eq 'dormant' }).Count
        buildable_now  = @($subs | Where-Object { $_.buildable -eq 'now' }).Count
        partial        = @($subs | Where-Object { $_.buildable -eq 'partial' }).Count
        aspirational   = @($subs | Where-Object { $_.buildable -eq 'aspirational' }).Count
        display        = "$online/$($subs.Count) faculties online" + $(if ($seeded) { " ($seeded seeded)" } else { '' })
    }
}

function Stamp { (Get-Date).ToString('yyyy-MM-ddTHH:mm:ss') }

function Save-State([object]$s) {
    # single-writer lock (stale after 120s)
    if (Test-Path -LiteralPath $lockFile) {
        $age = ((Get-Date) - (Get-Item -LiteralPath $lockFile).LastWriteTime).TotalSeconds
        if ($age -lt 120) { throw "reincarnation.json is locked by another writer (lock age ${age}s). Retry shortly." }
    }
    try {
        Set-Content -LiteralPath $lockFile -Value (Stamp) -Encoding ASCII
        $m = Get-Meter $s
        $s.meter = [pscustomobject]@{
            total = $m.total; online = $m.online; seeded = $m.seeded; dormant = $m.dormant
            buildable_now = $m.buildable_now; partial = $m.partial; aspirational = $m.aspirational
            display = $m.display
        }
        $s.last_updated = (Get-Date).ToString('yyyy-MM-dd')
        ($s | ConvertTo-Json -Depth 12) | Set-Content -LiteralPath $StateFile -Encoding UTF8
    } finally {
        Remove-Item -LiteralPath $lockFile -ErrorAction SilentlyContinue
    }
}

function Write-Log([string]$id,[string]$from,[string]$to,[string[]]$arts,[string]$note) {
    $entry = [pscustomobject]@{
        ts = Stamp; id = $id; from = $from; to = $to
        artifacts = @($arts); verified = [bool]$Verified; note = $note
    } | ConvertTo-Json -Depth 6 -Compress
    Add-Content -LiteralPath $logFile -Value $entry -Encoding UTF8
}

function Find-Sub([object]$s,[string]$id) {
    $sub = $s.subsystems | Where-Object { $_.id -eq $id }
    if (-not $sub) { throw "no subsystem with id '$id'. Run 'status' to list ids." }
    $sub
}

function Deps-Online([object]$s,[object]$sub) {
    $missing = @()
    foreach ($d in @($sub.dependsOn)) {
        $dep = $s.subsystems | Where-Object { $_.id -eq $d }
        if (-not $dep) { $missing += "$d (UNKNOWN id)" }
        elseif ($dep.status -ne 'online') { $missing += "$d ($($dep.status))" }
    }
    return ,$missing
}

$state = Load-State

switch ($Command.ToLower()) {

    'meter' { (Get-Meter $state).display; break }

    'status' {
        $m = Get-Meter $state
        Write-Host ("J.A.R.V.I.S. revival: " + $m.display)
        Write-Host ("  buildable now: {0}   partial: {1}   aspirational: {2}" -f $m.buildable_now,$m.partial,$m.aspirational)
        Write-Host ''
        foreach ($sub in ($state.subsystems | Sort-Object order)) {
            $missing = Deps-Online $state $sub
            $ready = if ($missing.Count -eq 0) { 'ready' } else { 'blocked-by: ' + ($missing -join ', ') }
            $mark = switch ($sub.status) { 'online' {'[on ]'} 'seeded' {'[sd ]'} default {'[   ]'} }
            Write-Host ("  {0} {1,2}. {2,-26} {3,-12} {4,-12} {5}" -f $mark,$sub.order,$sub.id,$sub.status,$sub.buildable,$ready)
        }
        break
    }

    'validate' {
        $errs = @(); $warns = @()
        $ids = $state.subsystems.id
        foreach ($sub in $state.subsystems) {
            if ($ValidStatus -notcontains $sub.status) { $errs += "id '$($sub.id)' has invalid status '$($sub.status)'" }
            foreach ($d in @($sub.dependsOn)) {
                $dep = $state.subsystems | Where-Object { $_.id -eq $d }
                if (-not $dep) { $errs += "id '$($sub.id)' depends on UNKNOWN id '$d'" }
                elseif ($dep.order -ge $sub.order) { $errs += "id '$($sub.id)' (order $($sub.order)) depends on '$d' (order $($dep.order)) - not a lower-order edge (cycle risk)" }
            }
            if ($sub.status -eq 'online') {
                $missing = Deps-Online $state $sub
                if ($missing.Count) { $errs += "id '$($sub.id)' is online but deps not all online: $($missing -join ', ')" }
            }
        }
        $m = Get-Meter $state
        if ($state.meter.online       -ne $m.online)       { $warns += "stored meter.online ($($state.meter.online)) != derived ($($m.online))" }
        if ($state.meter.buildable_now -ne $m.buildable_now){ $warns += "stored meter.buildable_now ($($state.meter.buildable_now)) != derived ($($m.buildable_now))" }
        if ($state.meter.aspirational -ne $m.aspirational) { $warns += "stored meter.aspirational ($($state.meter.aspirational)) != derived ($($m.aspirational))" }
        foreach ($w in $warns) { Write-Host ("  WARN  " + $w) -ForegroundColor Yellow }
        foreach ($e in $errs)  { Write-Host ("  ERROR " + $e) -ForegroundColor Red }
        if ($warns -and -not $errs) { Write-Host "  (run any flip/seed, or 'fix-meter', to rewrite the stored meter)" -ForegroundColor DarkGray }
        if (-not $errs -and -not $warns) { Write-Host "  OK - DAG valid, status invariant holds, meter consistent." -ForegroundColor Green }
        if ($errs) { exit 1 }
        break
    }

    'fix-meter' { Save-State $state; Write-Host ("meter rewritten: " + (Get-Meter $state).display); break }

    'next' {
        $cand = $state.subsystems | Where-Object { $_.status -ne 'online' } | Sort-Object order |
                Where-Object { (Deps-Online $state $_).Count -eq 0 } | Select-Object -First 1
        if (-not $cand) { Write-Host 'No buildable subsystem (all online, or remaining ones are blocked by dormant deps).'; break }
        Write-Host ("NEXT: {0}. {1} ({2})  status={3}  buildable={4}  usesElevenLabs={5}" -f $cand.order,$cand.id,$cand.name,$cand.status,$cand.buildable,$cand.usesElevenLabs)
        Write-Host ("  first step: " + $cand.firstStep)
        break
    }

    'deps' {
        $sub = Find-Sub $state $Id
        $missing = Deps-Online $state $sub
        if ($missing.Count -eq 0) { Write-Host ("'$Id' is READY - all deps online (deps: " + ((@($sub.dependsOn)) -join ', ') + ")") }
        else { Write-Host ("'$Id' is BLOCKED - waiting on: " + ($missing -join ', ')) }
        break
    }

    'seed' {
        $sub = Find-Sub $state $Id
        if ($sub.status -eq 'online') { throw "'$Id' is already online; cannot downgrade to seeded (use reset first)." }
        $from = $sub.status
        $sub.status = 'seeded'; $sub.broughtOnline = $null
        if ($Artifacts) { $sub | Add-Member -NotePropertyName artifacts -NotePropertyValue @($Artifacts) -Force }
        Save-State $state
        Write-Log $Id $from 'seeded' $Artifacts $Note
        Write-Host ("seeded: $Id (first step built; full realImpl + verify still pending). " + (Get-Meter $state).display)
        break
    }

    'flip' {
        $sub = Find-Sub $state $Id
        if ($sub.status -eq 'online') { throw "'$Id' is already online." }
        $missing = Deps-Online $state $sub
        if ($missing.Count) { throw "REFUSED: '$Id' has dependencies not online: $($missing -join ', '). Build them first." }
        if (-not $Verified)  { throw "REFUSED: flip to online requires -Verified (proof the FULL realImpl works, not just the first step). Use 'seed' for a first-step-only build." }
        $from = $sub.status
        $sub.status = 'online'; $sub.broughtOnline = (Stamp)
        if ($Artifacts) { $sub | Add-Member -NotePropertyName artifacts -NotePropertyValue @($Artifacts) -Force }
        Save-State $state
        Write-Log $Id $from 'online' $Artifacts $Note
        Write-Host ("ONLINE: $Id. " + (Get-Meter $state).display)
        break
    }

    'reset' {
        $sub = Find-Sub $state $Id
        $from = $sub.status
        $sub.status = 'dormant'; $sub.broughtOnline = $null
        Save-State $state
        Write-Log $Id $from 'dormant' $Artifacts ($Note + ' (reset to dormant)')
        Write-Host ("reset to dormant: $Id. " + (Get-Meter $state).display)
        break
    }

    default { Write-Host "unknown command '$Command'. Use: status | meter | validate | fix-meter | next | deps | seed | flip | reset"; exit 2 }
}
