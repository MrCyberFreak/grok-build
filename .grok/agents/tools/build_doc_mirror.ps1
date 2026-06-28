<#
  build_doc_mirror.ps1
  Deterministically (re)build a global doc-library mirror under
  X:\Grok_Build\.grok\library\<product>\<product>.md

  Unlike refresh_libraries.ps1 (which drives a headless Claude + WebFetch and does
  NOT scale to the large claude / claude-code page sets), this script fetches each
  page's RAW markdown directly from its .md endpoint with curl.exe -- verbatim, no
  summarization -- and reassembles the mirror in the established format:
    header (today's date) + grouped table of contents + one section per page,
    each section prefixed by  <a id="page-<slug>"></a>  and a
    <!-- source: <url> (fetched <today>) -->  marker.
  It then rewrites _meta.json (last_updated, captured_urls, pending_urls_or_sections).

  Both code.claude.com and platform.claude.com serve clean markdown at <slug>.md
  via direct HTTPS GET. code.claude.com pages carry a 3-line "> ## Documentation
  Index" banner before the H1; we strip everything before the first H1, which also
  no-ops cleanly for platform pages (no banner).

  Usage:
    pwsh -File build_doc_mirror.ps1 -Product claude-code
    pwsh -File build_doc_mirror.ps1 -Product claude
    pwsh -File build_doc_mirror.ps1 -Product claude-code -DryRun   # list pages, no fetch
#>
param(
  [Parameter(Mandatory)][ValidateSet('claude-code','claude')]$Product,
  [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
# Native curl warnings to stderr must NOT be promoted to terminating errors.
$PSNativeCommandUseErrorActionPreference = $false

$libRoot = 'X:\Grok_Build\.grok\library'
$today   = (Get-Date).ToString('yyyy-MM-dd')
$utf8    = [System.Text.UTF8Encoding]::new($false)   # UTF-8, no BOM

# ----------------------------------------------------------------------------
# Product configuration. $spec is an ordered group/slug list:
#   lines starting "# " are group headings; other non-empty lines are page slugs.
# ----------------------------------------------------------------------------
if ($Product -eq 'claude-code') {
  $title       = 'Claude Code CLI'
  $base        = 'https://code.claude.com/docs/en/'
  $sourceRoots = @(
    'Index: https://code.claude.com/llms.txt',
    'Pages: https://code.claude.com/docs/en/<slug>.md  (raw markdown form of each doc page)'
  )
  $coverageNote = 'High-value Claude Code pages PLUS the complete Agent SDK reference subtree (programmatic agents, subagents, skills, slash commands, custom tools, hooks, sessions, structured outputs, plugins, MCP). Regenerable cache built deterministically from the .md endpoints; not the complete docs set (see _meta.json pending_urls_or_sections).'
  $spec = @'
# Getting started
overview
quickstart
how-claude-code-works
setup
authentication
features-overview
# Usage & workflows
best-practices
common-workflows
interactive-mode
keybindings
# Reference
cli-reference
commands
tools-reference
glossary
errors
troubleshooting
# Configuration
settings
env-vars
model-config
claude-directory
memory
# Permissions & sandbox
permissions
permission-modes
sandbox-environments
sandboxing
# Extending - hooks
hooks
hooks-guide
# Agents, teams & orchestration (how subagents, agent view, agent teams & dynamic workflows compose)
agents
sub-agents
agent-view
agent-teams
workflows
# Skills & output
skills
output-styles
statusline
# Plugins
plugins
plugins-reference
discover-plugins
# MCP
mcp
mcp-quickstart
managed-mcp
# Sessions & state
sessions
checkpointing
worktrees
# Headless & automation
headless
routines
scheduled-tasks
# IDE & platforms
vs-code
jetbrains
chrome
desktop
claude-code-on-the-web
slack
# CI/CD
github-actions
gitlab-ci-cd
# Agent SDK - build agents programmatically (Claude Code as a library)
agent-sdk/overview
agent-sdk/quickstart
agent-sdk/agent-loop
agent-sdk/claude-code-features
agent-sdk/subagents
agent-sdk/skills
agent-sdk/slash-commands
agent-sdk/custom-tools
agent-sdk/tool-search
agent-sdk/mcp
agent-sdk/plugins
agent-sdk/hooks
agent-sdk/permissions
agent-sdk/sessions
agent-sdk/session-storage
agent-sdk/structured-outputs
agent-sdk/streaming-output
agent-sdk/streaming-vs-single-mode
agent-sdk/user-input
agent-sdk/todo-tracking
agent-sdk/cost-tracking
agent-sdk/file-checkpointing
agent-sdk/modifying-system-prompts
agent-sdk/observability
agent-sdk/hosting
agent-sdk/secure-deployment
agent-sdk/migration-guide
agent-sdk/python
agent-sdk/typescript
agent-sdk/typescript-v2-preview
'@
}
else {
  $title       = 'Claude / Anthropic Developer Platform'
  $base        = 'https://platform.claude.com/docs/en/'
  $sourceRoots = @(
    'Index: https://platform.claude.com/llms.txt',
    'Pages: https://platform.claude.com/docs/en/<slug>.md  (raw markdown form of each doc page)',
    'Note: docs.claude.com and docs.anthropic.com redirect to platform.claude.com/docs. The Claude Agent SDK harness (api/agent-sdk) now lives at code.claude.com/docs/en/agent-sdk/* -- mirrored in the claude-code library.'
  )
  $coverageNote = 'High-value developer-platform pages -- models & exact model IDs, pricing, Messages API, the COMPLETE tool-use suite (incl. build-a-tool-using-agent, tool combinations, programmatic tool calling, tool search), Agent Skills (overview/quickstart/best-practices/enterprise), Managed Agents, MCP, prompt caching, batches, files, token counting, streaming, errors & rate limits, the client SDKs. Regenerable cache built deterministically from the .md endpoints.'
  $spec = @'
# Models & pricing
about-claude/models/overview
about-claude/pricing
# Getting started
get-started
intro
build-with-claude/overview
# Messages API & core building blocks
api/messages
build-with-claude/working-with-messages
build-with-claude/handling-stop-reasons
build-with-claude/context-windows
build-with-claude/streaming
build-with-claude/structured-outputs
build-with-claude/extended-thinking
build-with-claude/adaptive-thinking
build-with-claude/effort
api/versioning
api/errors
# Context & cost management
build-with-claude/prompt-caching
build-with-claude/token-counting
build-with-claude/batch-processing
build-with-claude/context-editing
build-with-claude/compaction
# Inputs & outputs
build-with-claude/files
build-with-claude/vision
build-with-claude/pdf-support
build-with-claude/citations
build-with-claude/embeddings
# Tool use (how agents call tools)
agents-and-tools/tool-use/overview
agents-and-tools/tool-use/how-tool-use-works
agents-and-tools/tool-use/define-tools
agents-and-tools/tool-use/handle-tool-calls
agents-and-tools/tool-use/tool-reference
agents-and-tools/tool-use/parallel-tool-use
agents-and-tools/tool-use/tool-use-with-prompt-caching
agents-and-tools/tool-use/build-a-tool-using-agent
agents-and-tools/tool-use/tool-combinations
agents-and-tools/tool-use/programmatic-tool-calling
agents-and-tools/tool-use/tool-search-tool
agents-and-tools/tool-use/manage-tool-context
agents-and-tools/tool-use/server-tools
agents-and-tools/tool-use/strict-tool-use
agents-and-tools/tool-use/fine-grained-tool-streaming
agents-and-tools/tool-use/troubleshooting-tool-use
agents-and-tools/tool-use/bash-tool
agents-and-tools/tool-use/text-editor-tool
agents-and-tools/tool-use/code-execution-tool
agents-and-tools/tool-use/computer-use-tool
agents-and-tools/tool-use/advisor-tool
agents-and-tools/tool-use/web-search-tool
agents-and-tools/tool-use/web-fetch-tool
agents-and-tools/tool-use/memory-tool
# MCP
agents-and-tools/mcp-connector
agents-and-tools/remote-mcp-servers
# Agent Skills
agents-and-tools/agent-skills/overview
agents-and-tools/agent-skills/quickstart
agents-and-tools/agent-skills/best-practices
agents-and-tools/agent-skills/enterprise
# Managed Agents (server-side agents API)
managed-agents/overview
managed-agents/quickstart
managed-agents/reference
# SDKs & account
cli-sdks-libraries/overview
manage-claude/rate-limits-api
manage-claude/usage-cost-api
'@
}

# ----------------------------------------------------------------------------
# Parse $spec into ordered groups
# ----------------------------------------------------------------------------
$groups = New-Object System.Collections.Generic.List[object]
$cur = $null
foreach ($raw in ($spec -split "`n")) {
  $l = $raw.Trim()
  if (-not $l) { continue }
  if ($l.StartsWith('# ')) {
    $cur = [pscustomobject]@{ Name = $l.Substring(2).Trim(); Slugs = (New-Object System.Collections.Generic.List[string]) }
    $groups.Add($cur)
  } else {
    if ($null -eq $cur) { throw "slug before any group heading: $l" }
    $cur.Slugs.Add($l)
  }
}
$total = ($groups | ForEach-Object { $_.Slugs.Count } | Measure-Object -Sum).Sum
Write-Host "[$Product] $($groups.Count) groups, $total pages -> base $base"

# ----------------------------------------------------------------------------
# Fetch + assemble
# ----------------------------------------------------------------------------
$tmp      = [System.IO.Path]::GetTempFileName()
$tocLines = New-Object System.Collections.Generic.List[string]
$sections = New-Object System.Collections.Generic.List[string]
$okUrls   = New-Object System.Collections.Generic.List[string]
$failed   = New-Object System.Collections.Generic.List[string]

foreach ($g in $groups) {
  $tocLines.Add('')
  $tocLines.Add("**$($g.Name)**")
  $tocLines.Add('')
  foreach ($slug in $g.Slugs) {
    $url    = "$base$slug.md"
    $anchor = 'page-' + ((($slug -replace '[^A-Za-z0-9]+','-').Trim('-')).ToLower())
    if ($DryRun) { $tocLines.Add("- [$slug](#$anchor)"); continue }

    $code = (& curl.exe -s -L --max-time 45 -o $tmp -w '%{http_code}' $url) | Select-Object -Last 1
    $code = "$code".Trim()
    $body = ''
    if (Test-Path $tmp) { $body = [System.IO.File]::ReadAllText($tmp, $utf8) }

    if ($code -ne '200' -or $body.Length -lt 60 -or $body -match 'Asset not found') {
      $failed.Add("$slug (HTTP $code, $($body.Length)b)")
      Write-Host ("  FAIL  {0}  HTTP {1}  {2}b" -f $slug, $code, $body.Length)
      continue
    }

    # Strip everything before the first H1 (drops code.claude.com banner; no-op for platform).
    $lines = $body -split "`r?`n"
    $h1 = -1
    for ($i = 0; $i -lt $lines.Count; $i++) { if ($lines[$i] -match '^#\s') { $h1 = $i; break } }
    if ($h1 -ge 0) { $lines = $lines[$h1..($lines.Count - 1)] }
    $clean = ($lines -join "`n").Trim()

    $pageTitle = (($clean -split "`n")[0] -replace '^#\s+','').Trim()
    if (-not $pageTitle) { $pageTitle = $slug }

    $tocLines.Add("- [$pageTitle](#$anchor)")
    $sections.Add("<a id=""$anchor""></a>`n<!-- source: $url (fetched $today) -->`n`n$clean")
    $okUrls.Add($url)
    Write-Host ("  ok    {0}  ({1}b)  {2}" -f $slug, $body.Length, $pageTitle)
  }
}
if (Test-Path $tmp) { Remove-Item $tmp -Force -ErrorAction SilentlyContinue }

if ($DryRun) {
  Write-Host "`nDryRun -- $total pages would be fetched. TOC preview:`n"
  $tocLines | ForEach-Object { Write-Host $_ }
  return
}

# ----------------------------------------------------------------------------
# Compose the mirror file
# ----------------------------------------------------------------------------
$header = New-Object System.Collections.Generic.List[string]
$header.Add("# $title -- Offline Docs Mirror")
$header.Add('')
$header.Add("last_updated: $today")
$header.Add('')
$header.Add("Coverage: $($okUrls.Count) pages. $coverageNote")
$header.Add('')
$header.Add('Source roots:')
foreach ($s in $sourceRoots) { $header.Add("- $s") }
$header.Add('')
$header.Add('---')
$header.Add('')
$header.Add('## Table of contents')

$doc = ($header -join "`n") + "`n" + ($tocLines -join "`n") + "`n`n---`n`n" + ($sections -join "`n`n---`n`n") + "`n"

$outPath = Join-Path $libRoot "$Product\$Product.md"
[System.IO.File]::WriteAllText($outPath, $doc, $utf8)
$bytes = (Get-Item $outPath).Length
Write-Host ("`nWROTE  {0}  ({1:N0} bytes, {2} pages ok, {3} failed)" -f $outPath, $bytes, $okUrls.Count, $failed.Count)

# ----------------------------------------------------------------------------
# Update _meta.json
# ----------------------------------------------------------------------------
$metaPath = Join-Path $libRoot "$Product\_meta.json"
$meta = Get-Content $metaPath -Raw | ConvertFrom-Json
$meta.last_updated = $today
$meta.captured_urls = $okUrls.ToArray()

$capturedSet = [System.Collections.Generic.HashSet[string]]::new()
foreach ($u in $okUrls) { [void]$capturedSet.Add($u) }
$oldPending = @()
if ($meta.PSObject.Properties.Name -contains 'pending_urls_or_sections') { $oldPending = @($meta.pending_urls_or_sections) }
$meta.pending_urls_or_sections = @($oldPending | Where-Object { -not $capturedSet.Contains((($_ -split '\s')[0])) })

$rebuildNote = "Rebuilt $today by build_doc_mirror.ps1 -- deterministic curl of each <slug>.md endpoint (verbatim, unsummarized); banner stripped to first H1. "
if ($meta.PSObject.Properties.Name -contains 'notes') { $meta.notes = $rebuildNote + [string]$meta.notes } else { $meta | Add-Member -NotePropertyName notes -NotePropertyValue $rebuildNote }

[System.IO.File]::WriteAllText($metaPath, ($meta | ConvertTo-Json -Depth 10), $utf8)
Write-Host "UPDATED $metaPath  (captured=$($okUrls.Count), pending=$($meta.pending_urls_or_sections.Count))"

if ($failed.Count -gt 0) {
  Write-Host "`nFAILED PAGES ($($failed.Count)):"
  $failed | ForEach-Object { Write-Host "  - $_" }
}
