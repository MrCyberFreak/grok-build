<#
  mem-triage.ps1 - READ-ONLY Windows memory / page-file diagnostic.

  Used by the windows-oom-pagefile-triage skill. It MUTATES NOTHING: it only
  reads CIM classes and the process list, then prints the numbers plus two
  signals the skill uses to classify environment-vs-real-bug. It never changes
  a system setting (the page-file fix is a SEPARATE, consent-gated, elevated
  invocation documented in SKILL.md).

  Works on Windows PowerShell 5.1 and PowerShell 7. ASCII-only output.

  Usage:
    powershell -NoProfile -ExecutionPolicy Bypass -File mem-triage.ps1 [-TopN 8]
#>
[CmdletBinding()]
param(
    [int]$TopN = 8
)

$ErrorActionPreference = 'Stop'

function GB([double]$kb) { return [math]::Round(($kb / 1048576), 2) }   # KB -> GB

try {
    $os = Get-CimInstance Win32_OperatingSystem
    $cs = Get-CimInstance Win32_ComputerSystem
    $pf = @(Get-CimInstance Win32_PageFileUsage)
} catch {
    Write-Output ('ERROR: could not read memory CIM classes: ' + $_.Exception.Message)
    exit 2
}

$ramTotalKb    = [double]$os.TotalVisibleMemorySize
$ramFreeKb     = [double]$os.FreePhysicalMemory
$commitLimitKb = [double]$os.TotalVirtualMemorySize    # commit limit = RAM + page file
$commitFreeKb  = [double]$os.FreeVirtualMemory         # free commit
$commitUsedKb  = $commitLimitKb - $commitFreeKb
$commitPct     = if ($commitLimitKb -gt 0) { [math]::Round(($commitUsedKb / $commitLimitKb) * 100, 1) } else { 0 }

$autoPf    = [bool]$cs.AutomaticManagedPagefile
$pfPresent = ($pf.Count -gt 0)

Write-Output '== Windows memory / page-file triage (read-only) =='
Write-Output ''
Write-Output ('Physical RAM     : ' + (GB $ramTotalKb) + ' GB total, ' + (GB $ramFreeKb) + ' GB free')
Write-Output ('Commit limit     : ' + (GB $commitLimitKb) + ' GB  (RAM + page file)')
Write-Output ('Commit charge    : ' + (GB $commitUsedKb) + ' GB used, ' + (GB $commitFreeKb) + ' GB headroom  (' + $commitPct + '% of limit)')
Write-Output ('AutomaticManagedPagefile : ' + $autoPf)
if ($pfPresent) {
    foreach ($p in $pf) {
        Write-Output ('Page file        : ' + $p.Name + '  allocated ' + $p.AllocatedBaseSize + ' MB, current ' + $p.CurrentUsage + ' MB, peak ' + $p.PeakUsage + ' MB')
    }
} else {
    Write-Output 'Page file        : NONE (no Win32_PageFileUsage entry - page file appears DISABLED)'
}

Write-Output ''
Write-Output ('-- Top ' + $TopN + ' processes by private (commit) bytes --')
$procs = Get-Process | Sort-Object PrivateMemorySize64 -Descending | Select-Object -First $TopN
foreach ($pr in $procs) {
    $ws = [math]::Round(($pr.WorkingSet64 / 1MB), 0)
    $cm = [math]::Round(($pr.PrivateMemorySize64 / 1MB), 0)
    $line = '{0,-28} pid {1,-7} commit {2,7} MB  ws {3,7} MB' -f $pr.ProcessName, $pr.Id, $cm, $ws
    Write-Output $line
}

Write-Output ''
Write-Output '-- SIGNALS (the skill makes the final call) --'
# Ground truth = is a page file ACTUALLY present (Win32_PageFileUsage non-empty).
# AutomaticManagedPagefile can read True while NO page file exists yet (e.g. just
# enabled, reboot pending) - so the auto flag alone is NOT the environment signal.
$noPageFile       = (-not $pfPresent)
$limitEqualsRam   = ($commitLimitKb -le ($ramTotalKb * 1.05))   # commit limit ~= RAM => no page-file headroom
$commitNearLimit  = ($commitPct -ge 90)
$envRisk          = ($noPageFile -or $limitEqualsRam -or $commitNearLimit)
Write-Output ('pagefile_present     : ' + $pfPresent)
Write-Output ('automatic_managed    : ' + $autoPf + '   (can read True even when NO page file is present yet - reboot pending)')
Write-Output ('no_pagefile_headroom : ' + ($noPageFile -or $limitEqualsRam) + '   (no page file present, OR commit limit ~= RAM)')
Write-Output ('commit_near_limit    : ' + $commitNearLimit + '   (commit charge >= 90% of the commit limit)')
if ($envRisk) {
    Write-Output 'verdict_hint         : ENVIRONMENT-RISK - low/zero commit headroom (no page file and/or commit near limit); an allocation can fail here regardless of app code.'
} else {
    Write-Output 'verdict_hint         : NOT-ENVIRONMENT-by-these-signals - a page file is present and commit headroom looks healthy; look at the app (leak / genuinely insufficient RAM / code bug).'
}
