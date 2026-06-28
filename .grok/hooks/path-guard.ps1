# PreToolUse path guard:
# - Block ALL tool access to C:\ (reads and writes)
# - Block access outside X:\Grok_Build\ except explicit project trees under X:\Grok_Build\
$ErrorActionPreference = 'Continue'

$payload = [Console]::In.ReadToEnd()
if ([string]::IsNullOrWhiteSpace($payload)) { exit 0 }

try {
    $data = $payload | ConvertFrom-Json
} catch {
    exit 0
}

$tool = $data.tool_name
if (-not $tool) { $tool = $data.toolName }

$input = $data.tool_input
if (-not $input) { $input = $data.toolInput }

$ClaudeCodeKillswitch = 'X:\Grok_Build\.tmp\allow-claude-code-access'
$BootstrapKillswitch = 'X:\Grok_Build\.tmp\allow-c-drive-bootstrap'

function Test-ClaudeCodeAllowed() {
    return Test-Path -LiteralPath $ClaudeCodeKillswitch
}

function Test-ClaudeCodePath([string]$Path) {
    if ([string]::IsNullOrWhiteSpace($Path)) { return $false }
    $normalized = $Path -replace '/', '\'
    return $normalized -match '(?i)^X:\\Claude_Code(\\|$)'
}

function Test-GrokAllowed([string]$Path) {
    if ([string]::IsNullOrWhiteSpace($Path)) { return $true }
    $normalized = $Path -replace '/', '\'
    return $normalized -match '(?i)^X:\\Grok_Build(\\|$)'
}

function Test-CDrivePath([string]$Path) {
    if ([string]::IsNullOrWhiteSpace($Path)) { return $false }
    $normalized = $Path -replace '/', '\'
    return $normalized -match '(?i)^C:\\'
}

function Test-CDriveInText([string]$Text) {
    if ([string]::IsNullOrWhiteSpace($Text)) { return $false }
    return $Text -match '(?i)(C:\\|%USERPROFILE%|%APPDATA%|%LOCALAPPDATA%|~\s*[/\\]|~\s*\.claude|~\s*\.grok|~\s*\.cursor|\$env:USERPROFILE|\$env:APPDATA|\$env:LOCALAPPDATA|\$HOME[/\\])'
}

function Test-ForeignDriveInText([string]$Text) {
    if ([string]::IsNullOrWhiteSpace($Text)) { return $false }
    if ($Text -match '(?i)X:\\Grok_Build') { return $false }
    return $Text -match '(?i)X:\\'
}

$blocked = $false
$reason = ''
$denyMsg = 'Grok branch only: use paths under X:\Grok_Build\ (GROK_HOME, Projects, .tmp).'
$claudeDenyMsg = 'Claude Code tree is OFF LIMITS. Grok is self-contained — use $GROK_HOME or the active project. Override only with explicit user OK + .tmp\allow-claude-code-access.'
$cDriveDenyMsg = 'C: drive is OFF LIMITS. All Grok state lives under X:\Grok_Build\ (.grok, Projects, .tmp). Never write/read/probe C: or user profile paths.'

switch -Regex ($tool) {
    '^(Edit|StrReplace|Write|search_replace|write|Delete|delete|Read|Grep|Glob|list_dir)$' {
        $path = $input.path
        if (-not $path) { $path = $input.file_path }
        if (-not $path) { $path = $input.target_directory }

        if (Test-CDrivePath $path) {
            $blocked = $true
            $reason = "$cDriveDenyMsg (blocked path: $path)"
        } elseif ((Test-ClaudeCodePath $path) -and -not (Test-ClaudeCodeAllowed)) {
            $blocked = $true
            $reason = "$claudeDenyMsg (blocked path: $path)"
        } elseif (-not (Test-GrokAllowed $path)) {
            $blocked = $true
            $reason = "$denyMsg (blocked path: $path)"
        }

        $pattern = $input.pattern
        if (-not $blocked -and $pattern -and (Test-CDriveInText $pattern)) {
            $blocked = $true
            $reason = "$cDriveDenyMsg (search pattern)"
        }
        if (-not $blocked -and $pattern -and (Test-ClaudeCodePath $pattern) -and -not (Test-ClaudeCodeAllowed)) {
            $blocked = $true
            $reason = "$claudeDenyMsg (search pattern)"
        }
        if (-not $blocked -and $pattern -and (Test-ForeignDriveInText $pattern)) {
            $blocked = $true
            $reason = "$denyMsg (search pattern)"
        }

        $glob = $input.glob_pattern
        if (-not $blocked -and $glob -and (Test-CDrivePath $glob)) {
            $blocked = $true
            $reason = "$cDriveDenyMsg (glob: $glob)"
        }
        if (-not $blocked -and $glob -and (Test-ForeignDriveInText $glob)) {
            $blocked = $true
            $reason = "$denyMsg (glob pattern)"
        }
    }
    '^(Shell|Bash|PowerShell)$' {
        $cmd = $input.command
        if (-not $cmd) { $cmd = $input.cmd }
        if ([string]::IsNullOrWhiteSpace($cmd)) { break }

        if ($cmd -match '(?i)bootstrap-x-drive\.ps1' -and $cmd -notmatch '(?i)-EnvOnly' -and -not (Test-Path -LiteralPath $BootstrapKillswitch)) {
            $blocked = $true
            $reason = 'bootstrap-x-drive.ps1 touches C: — blocked. User must create .tmp\allow-c-drive-bootstrap first, or use -EnvOnly.'
        } elseif (Test-CDriveInText $cmd) {
            $blocked = $true
            $reason = "$cDriveDenyMsg (shell command)"
        } elseif ($cmd -match '(?i)Claude_Code' -and -not (Test-ClaudeCodeAllowed)) {
            $blocked = $true
            $reason = "$claudeDenyMsg (shell command)"
        } elseif (Test-ForeignDriveInText $cmd) {
            $blocked = $true
            $reason = "$denyMsg (shell command)"
        }
    }
}

if ($blocked) {
    $out = @{ decision = 'deny'; reason = $reason } | ConvertTo-Json -Compress
    Write-Output $out
    exit 2
}

exit 0