# Grok harness primitives

| Concept | Grok location |
|---------|---------------|
| Global rules | `GROK_HOME/AGENTS.md` (`X:\Grok_Build\.grok\AGENTS.md`) |
| Project rules | Project-root `AGENTS.md` or `CLAUDE.md` |
| Capability index | `GROK_HOME/CAPABILITIES.md` |
| Home env var | `GROK_HOME` = `X:\Grok_Build\.grok` |
| Subagents | **Task** tool — read `.grok/agents/<name>.md` first |
| Built-in explore/plan | Task `subagent_type: explore` or `plan` |
| Slash commands | `.grok/skills/<name>/SKILL.md` |
| Hooks | `.grok/hooks/grok-hooks.json` |
| Memory | `.grok/memory/` (`[memory] enabled` in config.toml) |
| Parallel orchestration | **Task** subagents (council, swarm-build, insight-amplify) |
| User choices | **AskQuestion** tool |
| Headless | `grok -p` |
| Sandbox | `[sandbox]` / `--sandbox` in config.toml |
| Library corpora | `$GROK_HOME/library/<topic>/` |

## What lives in GROK_HOME

| Resource | Path |
|----------|------|
| Agents (53+) | `.grok/agents/` |
| Skills (40+) | `.grok/skills/` + `.grok/bundled/skills/` |
| Hooks | `.grok/hooks/` |
| Libraries | `.grok/library/` |
| Workflows | `.grok/workflows/` |

When in doubt, delegate to `grok-build-expert`.