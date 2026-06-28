# grok-build

Single consolidated Git repository for **Grok Build harness configuration, agents, skills, hooks, rules, memory, and global settings**.

## Purpose

- Full history of changes to the Grok Build setup over time.
- One repo only — no proliferation of separate config repos.
- Primary focus: the global harness under `.grok/`.
- Project-specific work lives under `Projects/` (gitignored by default here; initialize git inside individual projects or selectively add if desired).

## What is tracked

- `.grok/config.toml`
- `.grok/agents/`
- `.grok/skills/`
- `.grok/hooks/`
- `.grok/rules/`
- `.grok/AGENTS.md`, `CAPABILITIES.md`
- `.grok/memory/` (important entries)
- `.grok/project-template/`
- Other core harness files and scripts

Large transient data (sessions, usage data, caches) and most `Projects/` contents are ignored.

## Usage

See the `/backup-config` skill for safe, reviewed backups of global config changes.

Manual:

```bash
# Review changes
git status --short
git diff --stat

# Selectively stage harness changes (never blind `git add -A`)
git add .grok/config.toml .grok/agents/ .grok/skills/ .grok/hooks/ ...

# Scan for secrets (critical)
git diff --cached

# Commit (user identity only)
git commit -m "Global: ..."

# Push (after secret scan)
git push
```

## Git identity

- Author: `cyberdabadoo <cyberdabadoo@gmail.com>`
- No AI attribution in commits.

## X-drive only

All state lives under `X:\Grok_Build`. Never track C: paths.

## Related

- Original Claude equivalent: https://github.com/MrCyberFreak/claude-code-config (historical)
- Global rules: `.grok/AGENTS.md`
- Backup skill: `/backup-config`

Changes here capture the evolution of the Grok Build harness.