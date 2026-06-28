# Stop hook: auto-open a freshly generated /insights report in the default browser.
#
# Fires on every assistant Stop. To avoid opening anything except a brand-new
# report (and to avoid re-opening the same one), it acts only when the newest
# report-*.html was modified within FRESH_SECONDS and is not the one recorded in
# the marker file. Always exits 0 so it never disrupts the session.

$ErrorActionPreference = 'SilentlyContinue'

$dir          = 'X:\Grok_Build\.grok\usage-data'
$marker       = Join-Path $dir '.last-opened-report'
$FreshSeconds = 300

try {
    $newest = Get-ChildItem -Path $dir -Filter 'report-*.html' -File |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $newest) { exit 0 }

    # Only auto-open a report that was just generated.
    $ageSeconds = ((Get-Date) - $newest.LastWriteTime).TotalSeconds
    if ($ageSeconds -gt $FreshSeconds) { exit 0 }

    # Don't re-open one we've already opened. Cast to string so an empty/missing
    # marker yields '' instead of $null (whose .Trim() would throw and, being
    # swallowed below, permanently wedge auto-open).
    $last = ''
    if (Test-Path $marker) { $last = "$(Get-Content $marker -Raw)".Trim() }
    if ($last -eq $newest.FullName) { exit 0 }

    # Claim the marker BEFORE launching, so a concurrent Stop in another session
    # can't also open the same report (TOCTOU -> duplicate browser tab).
    Set-Content -Path $marker -Value $newest.FullName -Encoding utf8
    Start-Process $newest.FullName
}
catch { }

exit 0
