<#
  announce-and-run.ps1

  Thin wrapper for the user's OWN scheduled tasks. When a task's console
  window appears, this makes the window clearly identify itself (window
  title + a banner) instead of looking like a blank / mystery terminal,
  then runs the real target script unchanged.

  It does NOT modify the target script - it only sets the title, prints a
  banner, and then invokes the target by path.

  Used by scheduled-task actions like:
    powershell.exe -NoProfile -ExecutionPolicy Bypass `
      -File "<this script>" `
      -Label  "FargoDailyPull" `
      -Info   "Pulls Fargo pool-rating data; runs every 2 hours." `
      -Target "X:\...\run-pull.ps1"
#>
param(
  [Parameter(Mandatory)][string]$Label,
  [Parameter(Mandatory)][string]$Target,
  [string]$Info = ""
)

try { $Host.UI.RawUI.WindowTitle = "$Label  --  your own scheduled task (safe to ignore)" } catch {}

$bar = "  +" + ("-" * 70)
Write-Host ""
Write-Host $bar                                                                  -ForegroundColor Cyan
Write-Host "  |  THIS IS ONE OF YOUR OWN SCHEDULED TASKS - nothing is wrong."    -ForegroundColor Cyan
Write-Host ("  |  Task : {0}" -f $Label)                                         -ForegroundColor White
if ($Info) { Write-Host ("  |  What : {0}" -f $Info)                             -ForegroundColor Gray }
Write-Host ("  |  Runs : {0}" -f (Get-Date))                                     -ForegroundColor Gray
Write-Host ("  |  File : {0}" -f $Target)                                        -ForegroundColor DarkGray
Write-Host $bar                                                                  -ForegroundColor Cyan
Write-Host ""

# Hold the banner on screen briefly so a fast-finishing task is still readable.
Start-Sleep -Milliseconds 1500

if (-not (Test-Path -LiteralPath $Target)) {
  Write-Host "  ERROR: target script not found: $Target" -ForegroundColor Red
  Start-Sleep -Seconds 4
  exit 1
}

& $Target @args
exit $LASTEXITCODE
