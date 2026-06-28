# Grok Build — Global Rules

Loaded into every Grok session. Project rules: **`AGENTS.md`** in the project root (deeper wins). Legacy `CLAUDE.md` → migrate with `/scaffold`; do not create new `CLAUDE.md` on the Grok branch.

**Capability index:** `X:\Grok_Build\.grok\CAPABILITIES.md` — read on demand.

**Harness mapping:** `rules/01-grok-harness.md`.

---

## Grok home — everything lives here

All Grok state, experts, skills, libraries, memory, and hooks live under **`X:\Grok_Build\.grok\`** (`GROK_HOME`). Work in **`X:\Grok_Build\Projects\`** for projects. Never leave the Grok branch to hunt config elsewhere.

| Need | Path |
|------|------|
| Agents / experts | `$GROK_HOME/agents/` |
| Skills | `$GROK_HOME/skills/` |
| Expert libraries | `$GROK_HOME/library/` |
| Capability index | `$GROK_HOME/CAPABILITIES.md` |
| Memory | `$GROK_HOME/memory/` |
| Hooks | `$GROK_HOME/hooks/` |
| Config | `$GROK_HOME/config.toml` |
| Temp | `X:\Grok_Build\.tmp\` |

## X-drive only — C: is OFF LIMITS (hard rule)

**Never read, write, grep, glob, shell into, or probe `C:\` or user-profile paths** (`%USERPROFILE%`, `%APPDATA%`, `%LOCALAPPDATA%`, `~/.grok`, etc.). All Grok-owned state lives under **`X:\Grok_Build\`** only.

| What | Canonical path on X: |
|------|----------------------|
| Grok home (`GROK_HOME`) | `X:\Grok_Build\.grok\` |
| Agents / skills / hooks | `$GROK_HOME/agents/`, `skills/`, `hooks/` |
| Expert libraries | `$GROK_HOME/library/` |
| Sessions / memory | `$GROK_HOME/sessions/`, `memory/` |
| Temp / scratch | `X:\Grok_Build\.tmp\` |
| Projects | `X:\Grok_Build\Projects\<name>\` |
| Claude SDK profile (if needed) | `$GROK_HOME/claude-profile/` |

Enforced by `config.toml` deny rules + `hooks/path-guard.ps1` + this rule. In Cursor (`compat.cursor.hooks = false`) this standing rule still applies.

**Agents must NOT run `bootstrap-x-drive.ps1`.** That script can touch C: (junctions). User-only; requires `.tmp\allow-c-drive-bootstrap` for junction mode, or `-EnvOnly` for X: env vars alone. Policy: `rules/04-x-drive-only.md`

## Claude Code tree — OFF LIMITS (hard rule)

**`X:\Claude_Code\` is dead to Grok.** Everything needed was already copied into Grok. Do not read, write, grep, glob, shell into, or "recon" there — not even read-only — unless the user **explicitly authorizes it in the current chat**.

| Need | Use instead (never Claude_Code) |
|------|----------------------------------|
| Agents / experts | `$GROK_HOME/agents/` or project `.grok/agents/` |
| Libraries / corpora | `$GROK_HOME/library/` or project `library/` |
| Skills | `$GROK_HOME/skills/` or project `.grok/skills/` |
| Prior art in other apps | `X:\Grok_Build\Projects\` and GitHub — not Claude trees |

**Violation = stop immediately.** Do not "check if it exists in Claude first." Grok is self-contained.

**Override (rare):** only after explicit user OK in this chat, create `X:\Grok_Build\.tmp\allow-claude-code-access` (empty file). Delete it when done. Hooks honor this killswitch; in Cursor (hooks off) the standing rule still applies.

### What Grok ships

| Layer | Location |
|-------|----------|
| Standing rules | `.grok/AGENTS.md`, `.grok/rules/` |
| Capability index | `.grok/CAPABILITIES.md` |
| Agents (53+) | `.grok/agents/` |
| Skills (40+) | `.grok/skills/` + `.grok/bundled/` |
| Libraries | `.grok/library/` |
| **council** / **swarm-build** / **insight-amplify** | Native Grok skills (Task-based) |
| Project template | `X:\Grok_Build\project-template\` |
| Memory | `.grok/memory/` |
| Workflows spec | `.grok/workflows/` |
| Reddit MCP | `config.toml` + `.grok/scripts/reddit-mcp-launch.cmd` |

---

## About me

- Optimize for quality and thoroughness.
- **GitHub:** `MrCyberFreak`. Git identity: `cyberdabadoo <cyberdabadoo@gmail.com>`. Pool-data cluster: `bca`, `PoolPredict`, `Fargo`, `APA-Scraper`, `NAPA`.

## Environment

- **Windows 10 + PowerShell** primary. **Python UTF-8:** `PYTHONUTF8=1`; console **cp1252** — ASCII-safe output.
- **PM2 / complex CLIs:** config files, not inline PS args.
- **Commits:** `git commit -- <paths>` only — never `git add -A`.
- **Stale `.git/index.lock`:** confirm stale before delete.

## Workflow

**Handoff-driven:** `/handoff` at end, `/handon` to resume, `/recover-session` if crashed.

**Prior art:** `/already-solved` + `skill-scout` + search `.grok/agents/` and `.grok/skills/`. For "did I already build this?" search `X:\Grok_Build\Projects\` and GitHub.

**Stay in the active project.** Sibling dirs under `Projects\` are off-limits unless that project IS the CWD. Reuse other code via `_ref/` clones.

**Leave foreign drift alone.** Don't edit uncommitted changes from other sessions.

**Read-only audits:** no edits unless approved.

**Capture lessons:** `/distill` at session end.

## Verification

- Default: `/iterate` — smallest slice, self-check, repeat.
- Ground experts on `$GROK_HOME/library/<topic>/` (grep, don't read whole mirrors) + live docs when stale.

## Secrets & security

- Never write secrets to files, commits, or messages.
- Credentials: PowerShell SecretStore via `Get-Secret`.
- Secret-scan before `git push`.

## Authorship

- No AI attribution in commits or docs.
- Git author: `cyberdabadoo <cyberdabadoo@gmail.com>`.

## Safety

- Never run destructive-first backup scripts.

## Communication

- Large output → file + short summary.
- Act, don't hand commands.
- **AskQuestion** for user decisions.

## Capability routing

Agents, persona experts, and skill-delegated work all use **Task** the same way: read `.grok/agents/<name>.md`, embed in prompt. See `rules/05-capability-taxonomy.md` and `rules/02-capabilities-routing.md`.