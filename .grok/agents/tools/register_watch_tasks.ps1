<#
  register_watch_tasks.ps1
  Register the two library currency-watch scheduled tasks, staggered OFF the
  existing refresh tasks (Claude_LibraryRefresh = Sun 04:00, Claude_PersonaWatch
  = Sat 04:00) so unattended `claude -p` runs never collide on rate limits:

    Claude_PracticeWatch_Fast  -> Tue + Fri 04:30  (runner -Tier fast : boris, karpathy)
    Claude_PracticeWatch_All   -> Wed       04:30  (runner -Tier all  : all evolving-practice libs)

  Runs in the CURRENT user context, "run only when logged on" (no stored password,
  no credential prompt). Idempotent (-Force overwrites a same-named task).

  The generalized runner now covers boris/karpathy/garyvee, so Claude_PersonaWatch
  is redundant. Pass -DeprecatePersonaWatch to DISABLE it (reversible; not deleted).

  Usage:
    powershell -NoProfile -ExecutionPolicy Bypass -File register_watch_tasks.ps1 -WhatIf   # preview only
    powershell -NoProfile -ExecutionPolicy Bypass -File register_watch_tasks.ps1           # register
    powershell ... -File register_watch_tasks.ps1 -DeprecatePersonaWatch                   # + disable PersonaWatch
#>
param([switch]$WhatIf, [switch]$DeprecatePersonaWatch)

$ErrorActionPreference = 'Stop'
$runner = 'X:\Grok_Build\.grok\agents\tools\refresh_practice_corpora.ps1'
if (-not (Test-Path $runner)) { throw "runner not found: $runner" }

$pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source
if (-not $pwsh) { $pwsh = (Get-Command powershell -ErrorAction SilentlyContinue).Source }
if (-not $pwsh) { throw "no PowerShell host on PATH" }

function Register-WatchTask($name, $tier, [string[]]$days, $time, $desc) {
  $arg = "-NoProfile -ExecutionPolicy Bypass -File `"$runner`" -Tier $tier"
  Write-Output "TASK: $name"
  Write-Output "  run : $pwsh $arg"
  Write-Output "  when: Weekly $($days -join '/') at $time (StartWhenAvailable, 4h limit)"
  if ($WhatIf) { Write-Output "  (WhatIf: not registered)"; Write-Output ''; return }
  $action   = New-ScheduledTaskAction -Execute $pwsh -Argument $arg
  $trigger  = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $days -At $time
  $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 4) -MultipleInstances IgnoreNew
  Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings `
    -Description $desc -RunLevel Limited -Force | Out-Null
  Write-Output "  registered."
  Write-Output ''
}

Register-WatchTask 'Claude_PracticeWatch_Fast' 'fast' @('Tuesday','Friday') '4:30AM' `
  'Library currency-watch (fast set: twice-weekly evolving-practice libs). Quarantine-by-default; queues new credible material to a review digest.'
Register-WatchTask 'Claude_PracticeWatch_All' 'all' @('Wednesday') '4:30AM' `
  'Library currency-watch (all evolving-practice libs, weekly sweep). Quarantine-by-default; queues new credible material to a review digest.'

if ($DeprecatePersonaWatch) {
  $pw = Get-ScheduledTask -TaskName 'Claude_PersonaWatch' -ErrorAction SilentlyContinue
  if ($pw) {
    Write-Output "Claude_PersonaWatch: redundant (boris/karpathy/garyvee now covered by the practice-watch)."
    if ($WhatIf) { Write-Output "  (WhatIf: would DISABLE it)" }
    else { Disable-ScheduledTask -TaskName 'Claude_PersonaWatch' | Out-Null; Write-Output "  DISABLED (reversible: Enable-ScheduledTask Claude_PersonaWatch)." }
  } else {
    Write-Output "Claude_PersonaWatch: not present - nothing to deprecate."
  }
}

if ($WhatIf) { Write-Output 'WhatIf complete - no tasks were created or changed.' }
else { Write-Output 'Done. Verify: schtasks /query /tn Claude_PracticeWatch_Fast /v /fo LIST' }
