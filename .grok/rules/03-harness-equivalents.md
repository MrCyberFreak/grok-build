# Claude Code → Grok Build: the other 30%

What Claude has that is harness-specific, and the Grok equivalent (or honest gap).

| Claude Code | Grok Build equivalent | Notes |
|-------------|----------------------|-------|
| **`Workflow` tool** | **Task** tool (parallel subagents) + optional scripts in `.grok/workflows/` | No single Workflow primitive. `council` and `swarm-build` are rewritten to use Task. `llm-council.js` is a **spec**, not executable. |
| **`Agent` tool** | **Task** with `subagent_type: generalPurpose`, `explore`, `plan`, or `code-reviewer` | Custom experts: read `.grok/agents/<name>.md` into the Task prompt. |
| **`Skill` tool** | Slash `/name` or automatic skill match | Same skill files; junctioned or native under `.grok/skills/`. |
| **`Stop` hook `decision: block`** | **Weaker on Grok** — only `PreToolUse` hard-blocks | `build-verify-gate` runs on Stop but cannot block turn end like Claude. Mitigation: treat gate output as mandatory instruction; consider PreToolUse rewrite later. |
| **`settings.json`** | `config.toml` + `.grok/hooks/*.json` | Permissions shape differs (Claude allow-list vs Grok deny C: + always-approve). |
| **Global config dir** | `GROK_HOME` = `X:\Grok_Build\.grok` | |
| **Memory vault** `projects/*/memory/` | `.grok/memory/` (mirrored) + `[memory] enabled` in config | Claude memories copied; new memories write to `.grok/memory/` only. |
| **Notion / GDrive MCP connectors** | Configure stdio MCP in `config.toml` | No claude.ai account connectors; need your own MCP servers + tokens. |
| **Reddit MCP** (`mcpServers.reddit`) | Add `[mcp_servers.reddit]` to `config.toml` | Script exists at Claude `scripts/reddit-mcp-launch.cmd` — can wire when you want. |
| **Plugin seed** (7 marketplaces) | Grok `marketplace` + `.grok/plugins/` | Different format; cherry-pick skills or install xAI plugins. |
| **`/output-style jarvis`** | Persona rule or `rules/jarvis-style.md` | No output-style command. |
| **`keybindings.json` voice** | Grok TUI shortcuts in `config.toml` | No hold-to-talk voice in this Cursor integration. |
| **`statusline.ps1`** | `[ui.notifications.title]` items | Different UI; no custom footer script. |
| **`voice` + `jarvis-voice.ps1`** | Not available in Grok/Cursor agent | ElevenLabs hook can still run on Stop (passive). |
| **Daemon / `jobs/` multiclauding** | Background **Task** + `AwaitShell` | No Claude-style background session daemon. |
| **`claude -p` scheduled tasks** | `grok -p` in Windows Scheduled Tasks | Scripts portable; change binary. |
| **`dangerouslyDisableSandbox`** | `grok --sandbox` profiles / disable sandbox flag | Different sandbox model. |
| **`AskUserQuestion`** | **AskQuestion** tool | |
| **Project `.claude/` sync** | Project `.grok/` + `AGENTS.md` | `scaffold` skill should emit Grok layout. |
| **`effortLevel`, Claude theme** | `[ui]` / model effort flags | Separate fields. |

## Global orchestration skills (on Grok)

| Skill | Location | Claude dependency removed |
|-------|----------|---------------------------|
| **council** | `.grok/skills/council/` | Task phases replace `Workflow`; spec at `.grok/workflows/llm-council.js` |
| **swarm-build** | `.grok/skills/swarm-build/` | Task + `worktree.ps1` replace `Workflow`/`Agent` |