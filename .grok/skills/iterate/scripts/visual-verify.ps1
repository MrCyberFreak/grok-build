<#
    visual-verify.ps1
    Reusable Windows visual / static self-verification helper for the `iterate`
    skill (and any build-verify loop). Generalizes the proven per-project
    "headless Edge/Chrome --screenshot then Read the PNG" pattern into one global
    tool so any project gets it for free.

    Two modes:

    RENDER (default): render a local HTML file or an http(s) URL with headless
      Edge/Chrome and write a PNG, so the caller can Read the image back and
      critique it visually. Handles file:// conversion, #hash routes, a
      virtual-time budget for JS to run, and a UNIQUE --user-data-dir per run so
      concurrent verifies do not collide on a profile lock (a documented gotcha
      on this box).

    CHECK (-CheckHtml): static smoke-check a generated HTML file WITHOUT a
      browser: extract inline <script> blocks and run `node --check` on each
      (catches the silent client-side JS break that otherwise reaches the user),
      plus optional -Expect content-marker greps.

    Prints a single result line. Non-zero exit on failure so a caller/hook can
    branch. ASCII-only output (cp1252 console safe).

    Examples:
      visual-verify.ps1 -Url "X:\proj\prototype\index.html#/players" -Out shot.png
      visual-verify.ps1 -Url "http://localhost:5173/#/overview" -Size 1440,900
      visual-verify.ps1 -Url "X:\proj\out.html" -CheckHtml -Expect "Compose","Reports"
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Url,
    [string]$Out = "",
    [string]$Size = "1500,1050",
    [int]$Wait = 4000,
    [ValidateSet('auto', 'edge', 'chrome')][string]$Engine = 'auto',
    [switch]$CheckHtml,
    [string[]]$Expect = @(),
    [int]$Timeout = 30000
)

# Native browser/node banners write to stderr; under Windows PowerShell 5.1 with
# EAP=Stop that is promoted to a terminating error. So use Continue and rely on the
# explicit exit-code / Test-Path checks below. ($PSNativeCommandUseErrorActionPreference
# is PS 7.3+ only - we cannot depend on it here.)
$ErrorActionPreference = 'Continue'

function Write-Line([string]$m) { [Console]::Out.WriteLine($m) }

# --- resolve the target: local path (+ optional #route) vs http(s)/file URL ---
$localFile = $null
$target = $Url
if ($Url -match '^(?i)(https?|file)://') {
    $target = $Url
    if ($Url -match '^(?i)file:///(.+)$') {
        $localFile = ($Matches[1] -replace '/', '\') -replace '%20', ' '
    }
}
else {
    $hash = ''
    $p = $Url
    $hi = $Url.IndexOf('#')
    if ($hi -ge 0) { $p = $Url.Substring(0, $hi); $hash = $Url.Substring($hi) }
    $resolved = Resolve-Path -LiteralPath $p -ErrorAction SilentlyContinue
    if (-not $resolved) {
        Write-Line "VERIFY FAIL: file not found: $p"
        exit 2
    }
    $localFile = $resolved.Path
    $uri = 'file:///' + (($localFile -replace '\\', '/') -replace ' ', '%20')
    $target = $uri + $hash
}

# ============================ CHECK mode ====================================
if ($CheckHtml) {
    if (-not $localFile) {
        Write-Line "VERIFY FAIL: -CheckHtml needs a local HTML file, not a remote URL."
        exit 2
    }
    try {
        $html = Get-Content -LiteralPath $localFile -Raw -Encoding utf8
    }
    catch {
        Write-Line "VERIFY FAIL: cannot read $localFile"
        exit 2
    }

    # Normalize -Expect: external shells passing "a","b" through `powershell -File`
    # collapse it to one string, so split each element on comma/semicolon too.
    $markers = @()
    foreach ($e in $Expect) { if ($e) { $markers += ($e -split '[;,]') } }
    $markers = @($markers | ForEach-Object { $_.Trim() } | Where-Object { $_ })

    $fail = $false
    $tmpDir = Join-Path $env:TEMP ("cvv-check-" + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $tmpDir -Force | Out-Null

    # inline <script> blocks that have no src= attribute
    $rx = [regex]'(?is)<script(?![^>]*\bsrc\s*=)[^>]*>(.*?)</script>'
    $blocks = $rx.Matches($html)
    $checked = 0
    foreach ($m in $blocks) {
        $js = $m.Groups[1].Value
        if (-not $js.Trim()) { continue }
        $checked++
        $f = Join-Path $tmpDir ("inline-$checked.js")
        [System.IO.File]::WriteAllText($f, $js, (New-Object System.Text.UTF8Encoding($false)))
        # Run node via cmd /c so its stderr is captured as plain text, not wrapped
        # in a PowerShell NativeCommandError record (PS 5.1 noise).
        $raw = cmd /c "node --check `"$f`" 2>&1"
        if ($LASTEXITCODE -ne 0) {
            $msg = (@($raw | Where-Object { $_ -and $_.Trim() } | Select-Object -First 3) -join ' | ')
            Write-Line "JS SYNTAX FAIL (inline block $checked): $msg"
            $fail = $true
        }
    }

    foreach ($e in $markers) {
        if ($html -notmatch [regex]::Escape($e)) {
            Write-Line "MISSING MARKER: '$e'"
            $fail = $true
        }
    }

    try { Remove-Item $tmpDir -Recurse -Force -ErrorAction SilentlyContinue } catch { }

    if ($fail) { Write-Line "CHECK FAILED (file=$localFile)"; exit 3 }
    Write-Line "CHECK OK: $checked inline script block(s) parse, $($markers.Count) marker(s) present (file=$localFile)"
    exit 0
}

# ============================ RENDER mode ===================================
function Find-Engine([string]$which) {
    $edge = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    $chrome = @(
        "C:\Program Files\Google\Chrome\Application\chrome.exe",
        "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
    )
    if ($which -eq 'edge') { if (Test-Path $edge) { return @{ exe = $edge; name = 'edge' } } else { return $null } }
    if ($which -eq 'chrome') { foreach ($c in $chrome) { if (Test-Path $c) { return @{ exe = $c; name = 'chrome' } } }; return $null }
    # auto: prefer Edge (proven on this box), then Chrome
    if (Test-Path $edge) { return @{ exe = $edge; name = 'edge' } }
    foreach ($c in $chrome) { if (Test-Path $c) { return @{ exe = $c; name = 'chrome' } } }
    return $null
}

$eng = Find-Engine $Engine
if (-not $eng) {
    Write-Line "VERIFY FAIL: no headless browser found (Edge/Chrome) for engine '$Engine'."
    exit 4
}

if (-not $Out) {
    $outDir = Join-Path $env:TEMP 'claude-visual-verify'
    New-Item -ItemType Directory -Path $outDir -Force | Out-Null
    $stamp = (Get-Date -Format 'yyyyMMdd-HHmmss')
    $Out = Join-Path $outDir ("shot-$stamp-$(Get-Random).png")
}
else {
    $parent = Split-Path -Parent $Out
    if ($parent -and -not (Test-Path $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
}
# delete a stale same-name output (fresh-file rule: avoid a path-guard misfire on a busy path)
if (Test-Path $Out) { try { Remove-Item $Out -Force -ErrorAction SilentlyContinue } catch { } }

$profileDir = Join-Path $env:TEMP ("cvv-prof-" + [guid]::NewGuid().ToString('N'))
$cliArgs = @(
    '--headless=new',
    '--disable-gpu',
    '--hide-scrollbars',
    '--no-first-run',
    '--no-default-browser-check',
    "--user-data-dir=$profileDir",
    "--window-size=$Size",
    "--virtual-time-budget=$Wait",
    "--screenshot=$Out",
    $target
)

try {
    $proc = Start-Process -FilePath $eng.exe -ArgumentList $cliArgs -PassThru -WindowStyle Hidden -ErrorAction Stop
    if (-not $proc.WaitForExit($Timeout)) {
        try { $proc.Kill() } catch { }
        Write-Line "VERIFY FAIL: render timed out after ${Timeout}ms (engine=$($eng.name))."
        exit 5
    }
}
catch {
    Write-Line "VERIFY FAIL: could not launch $($eng.name): $($_.Exception.Message)"
    exit 5
}
finally {
    try { Remove-Item $profileDir -Recurse -Force -ErrorAction SilentlyContinue } catch { }
}

if ((Test-Path $Out) -and ((Get-Item $Out).Length -gt 0)) {
    $bytes = (Get-Item $Out).Length
    Write-Line "RENDER OK -> $Out (engine=$($eng.name), ${bytes} bytes)"
    Write-Line "NEXT: Read the PNG above and critique the rendered UI against the brief."
    exit 0
}
else {
    Write-Line "VERIFY FAIL: no screenshot produced at $Out (engine=$($eng.name))."
    exit 6
}
