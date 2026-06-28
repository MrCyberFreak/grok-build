<#
    prior-art-reminder.ps1
    UserPromptSubmit hook. When the user's prompt looks like a request to BUILD
    something new, inject a standing reminder to check for prior art / existing
    capabilities first (already-solved / skill-scout / installed skills) before
    writing code. Low-noise: stays silent unless the prompt shows build intent.

    Pairs with the "Check for prior art before building" rule in the global
    CLAUDE.md. The directive is advisory (model may forget); this hook makes the
    reminder land at the moment of a build request. ASCII-only output (cp1252).
#>
$ErrorActionPreference = 'Stop'

# --- read the hook payload from stdin --------------------------------------
try {
    $raw = [Console]::In.ReadToEnd()
    if (-not $raw) { exit 0 }
    $data = $raw | ConvertFrom-Json
    $prompt = [string]$data.prompt
    if (-not $prompt) { exit 0 }
} catch { exit 0 }

# --- build-intent detector (case-insensitive) ------------------------------
# Fire when a build verb sits near an artifact noun, or on a few stock phrases.
# verb stems so build/building/builds, create/creating, write/writing, etc. all match
$verb = '(build|creat|implement|develop|writ|mak|scaffold|design|set up)\w*'
$noun = '(script|tool|skill|agent|feature|function|app|application|component|library|module|package|cli|command|hook|plugin|service|system|integration|bot|pipeline|wrapper|utility|dashboard|endpoint|api)'
$pattern = "(?i)\b$verb.{0,40}\b$noun\b|\bfrom scratch\b|\blet'?s build\w*\b|\bnew\s+(skill|tool|agent|feature|script|app|command|plugin|library|service)\b"

if ($prompt -notmatch $pattern) { exit 0 }

# --- inject the reminder ----------------------------------------------------
$msg = 'PRIOR-ART CHECK (standing rule from global CLAUDE.md): this prompt looks like a request to build something new. Before writing code, first check for an existing solution - use the already-solved skill for external prior art and skill-scout for an existing skill, and search the installed skills/agents/marketplaces. Report what already exists and prefer reusing/adapting it over reinventing.'

$out = @{
    hookSpecificOutput = @{
        hookEventName     = 'UserPromptSubmit'
        additionalContext = $msg
    }
}
$out | ConvertTo-Json -Compress -Depth 5
exit 0
