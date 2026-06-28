# Capability routing (when to delegate)

**Routing rule:** agents, persona experts, and skill-delegated work all use the **same path**:

1. Match domain (description auto-route, `/skill` trigger, or explicit ask)
2. **Read** `.grok/agents/<name>.md` (built-in `explore`/`plan`/`code-reviewer` excepted)
3. **Task** with `subagent_type: generalPurpose` (or `code-reviewer` / `explore` / `plan`) and the full agent body + context in the prompt

**Personas** (`/wwbd`, `/jarvis`, …): the **skill** owns the user loop; it **Task**s to the paired `*-expert` agent — never answer as the persona without that delegation.

See `rules/05-capability-taxonomy.md` for the full model.

Full inventory + library paths: read `X:\Grok_Build\.grok\CAPABILITIES.md` on demand.

## Expert agents (docs-backed — fetch current docs)

- `grok-build-expert` — Grok Build CLI (this harness): config.toml, AGENTS.md, skills, subagents, hooks, MCP, permissions
- `grok-expert` — xAI Grok models & API
- `claude-code-expert` — Claude Code CLI (read-only reference; user edits Claude config separately)
- `claude-expert` — Claude/Anthropic API & models
- `git-expert`, `github-expert`, `huggingface-expert`
- `frontend-design-expert`, `react-expert`, `frontend-framework-expert`, `web-deploy-expert`
- `agile-expert` + `scrum-expert`, `sprint-expert`, `kanban-expert`, `agile-scaling-expert`, `agile-metrics-expert`, `agile-backlog-expert`
- `notion-expert`, `mcp-expert`, `obsidian-expert`, `elevenlabs-expert`, `reddit-expert`
- `boris-expert`, `karpathy-expert`, `garyvee-expert`, `jarvis-expert`
- Creator monetization: `tiktok-platform-monetization`, `faceless-content-strategy`, `brand-deals-sponsorship`, etc.

## Critics & execution (read-only unless noted)

- `agentic-systems-architect`, `agent-eval-strategist`, `predictive-model-critic`, `opportunity-discovery-strategist`
- `pool-rating-systems-expert`, `rating-systems-expert`
- `windows-delivery-engineer`, `python-data-engineer`, `scrape-resilience-engineer`, `entity-resolution-engineer`
- `code-explainer`, `skill-scout`, `skill-builder`, `roster-steward`

## Built-in subagent types

- `explore` — read-only codebase search (Task `subagent_type: explore`)
- `plan` — implementation planning without edits (Task `subagent_type: plan`)
- `generalPurpose` — full-capability delegate (Task `subagent_type: generalPurpose`)
- `code-reviewer` — diff review (Task `subagent_type: code-reviewer`)

## Skills — invoke via `/name`

**Session:** `/handoff`, `/handon`, `/recover-session`, `/distill`, `/wrap`, `/oneprompt`

**Research:** `/already-solved`, `/vendor-corpus`

**Build:** `/iterate`, `/swarm-build`, `/frontend-aesthetics`, `/safe-commit`

**Thinking:** `/grill-me`, `/council`, `/wwbd`, `/wwkd`, `/wwgd`, `/jarvis`

**Agile:** `/user-stories`, `/sprint-plan`, `/retro`, `/backlog-refine`, `/kanban-flow`

**Harness (adapt for Grok):** `/scaffold`, `/scaffold-expert`, `/propagate`, `/routing-audit`, `/insight-amplify`, `/sync-capabilities`

**Quality:** `/code-review` (Grok bundled), `/untrusted-repo-static-audit`, `/windows-oom-pagefile-triage`