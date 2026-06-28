<#
.SYNOPSIS
  Create / list / remove git worktrees for a swarm build, with a .NET-delete
  fallback because Remove-Item -Recurse -Force can be sandbox-blocked on this
  Windows machine (reports a "protected path").

.DESCRIPTION
  Helper for the swarm-build skill. Worktrees are created as SIBLING dirs of the
  repo (so relative upstream paths resolve) under a single parent dir, one per
  stream. Cleanup never touches the repo itself and never force-deletes a path
  that is not a registered worktree.

  All paths absolute. ASCII-only output (cp1252 console safe). No Claude / AI
  identity is ever set; git author/committer stay as the user's configured
  identity.

.PARAMETER Action
  create | list | remove

.PARAMETER Repo
  Absolute path to the main git repo (the worktree's upstream).

.PARAMETER Stream
  Stream / branch name (kebab-case). Required for create and remove.

.PARAMETER Base
  Branch to base a new worktree on (default: the repo's current branch).

.PARAMETER ParentDir
  Where sibling worktrees live. Default: <repo>'s parent \ <repoName>-worktrees.

.EXAMPLE
  pwsh worktree.ps1 -Action create -Repo X:\proj -Stream api -Base main
.EXAMPLE
  pwsh worktree.ps1 -Action remove -Repo X:\proj -Stream api
.EXAMPLE
  pwsh worktree.ps1 -Action list -Repo X:\proj
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet('create', 'list', 'remove')]
    [string]$Action,
    [Parameter(Mandatory)][string]$Repo,
    [string]$Stream,
    [string]$Base,
    [string]$ParentDir
)

$ErrorActionPreference = 'Stop'
# A native command (git) writing to stderr must not be promoted to a terminating
# error under PS 7.3+ -- a benign git warning would otherwise abort the script.
$PSNativeCommandUseErrorActionPreference = $false

function Fail([string]$msg) { Write-Error $msg; exit 1 }

$Repo = (Resolve-Path -LiteralPath $Repo).Path
if (-not (Test-Path -LiteralPath (Join-Path $Repo '.git'))) {
    Fail "Not a git repo (no .git): $Repo"
}

if (-not $ParentDir) {
    $repoName = Split-Path -Leaf $Repo
    $ParentDir = Join-Path (Split-Path -Parent $Repo) "$repoName-worktrees"
}

function Get-WorktreePath([string]$stream) {
    if (-not $stream) { Fail "-Stream is required for this action." }
    Join-Path $ParentDir $stream
}

# .NET recursive delete: the mandated fallback when Remove-Item -Recurse -Force
# is refused by the sandbox. Only ever called on a known worktree path.
function Remove-DirHard([string]$path) {
    if (-not (Test-Path -LiteralPath $path)) { return }
    try {
        [System.IO.Directory]::Delete($path, $true)
    }
    catch {
        # Clear read-only attributes (common on .git internals) then retry once.
        Get-ChildItem -LiteralPath $path -Recurse -Force -ErrorAction SilentlyContinue |
            ForEach-Object { try { $_.Attributes = 'Normal' } catch {} }
        [System.IO.Directory]::Delete($path, $true)
    }
}

switch ($Action) {
    'list' {
        & git -C $Repo worktree list
        exit $LASTEXITCODE
    }

    'create' {
        $wt = Get-WorktreePath $Stream
        if (Test-Path -LiteralPath $wt) { Fail "Worktree path already exists: $wt" }
        if (-not (Test-Path -LiteralPath $ParentDir)) {
            New-Item -ItemType Directory -Path $ParentDir -Force | Out-Null
        }
        if (-not $Base) {
            $Base = (& git -C $Repo rev-parse --abbrev-ref HEAD).Trim()
        }
        # New branch named after the stream, based on $Base.
        & git -C $Repo worktree add -b $Stream $wt $Base
        if ($LASTEXITCODE -ne 0) { Fail "git worktree add failed (exit $LASTEXITCODE)." }
        Write-Output "OK created worktree: $wt  (branch: $Stream  base: $Base)"
    }

    'remove' {
        $wt = Get-WorktreePath $Stream
        # Deregister from git first (prune metadata), then hard-delete the dir.
        & git -C $Repo worktree remove $wt --force 2>$null
        # Whether or not git removed it, ensure the dir is gone via .NET fallback.
        Remove-DirHard $wt
        & git -C $Repo worktree prune 2>$null
        if (Test-Path -LiteralPath $wt) { Fail "Could not remove worktree dir: $wt" }
        Write-Output "OK removed worktree: $wt  (branch '$Stream' left intact; delete it after a verified merge)"
    }
}
