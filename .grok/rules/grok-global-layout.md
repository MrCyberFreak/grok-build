# Grok Global Layout

## Home directory

Everything Grok persists lives under **`X:\Grok_Build\.grok\`** (`GROK_HOME`):

| Path | Purpose |
|------|---------|
| `config.toml` | Global settings, permissions |
| `AGENTS.md` / `rules/` | Standing instructions |
| `agents/` | Expert agent definitions |
| `skills/` | Slash-command skills |
| `library/` | Offline expert corpora |
| `hooks/` | Lifecycle hooks + path guard |
| `memory/` | Durable session memories |
| `sessions/` | Conversation persistence |
| `bundled/` | Factory-default agents/skills |
| `workflows/` | Orchestration specs (council, insight-amplify) |
| `scripts/` | MCP launchers, utilities |

Temp / scratch: `X:\Grok_Build\.tmp\`.

Project-local state (e.g. Jarvis2 HUD prefs): `Projects/<name>/.grok/state/`.

## C: drive policy

**Off limits to Grok agents** — no reads, writes, or probes. Canonical data is on X: under `Grok_Build\` only. Do not use `%APPDATA%`, `Path.home()`, or `C:\Users\...` in project code.

## Library usage

Expert agents ground on `$GROK_HOME/library/<topic>/`. Grep corpora; check `_meta.json` `last_updated` before trusting stale mirrors. Never read whole mirror files into context.

## Projects

Application work under `X:\Grok_Build\Projects\<name>\`. Project-local libraries (e.g. `Projects/Jarvis2/library/`) override or extend global corpora for that project.