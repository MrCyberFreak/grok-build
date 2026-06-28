---
name: update-config
description: Apply an approved config change to the Grok global harness - config.toml permissions, .grok/hooks/, AGENTS.md rules, or new skills/agents. Use when distill, insight-amplify, or the user approves a hook/lint/rule and wants it installed. NOT for project-repo changes, NOT for blind git add -A on the global tree.
argument-hint: "[what to install - hook, rule, skill, permission]"
---

# update-config (Grok global)

Install an **approved** harness change into `GROK_HOME` (`X:\Grok_Build\.grok`).

## Hard rules

- **Only install what the user approved** in this session (or an explicit prior approval they reference).
- **Never write to `X:\Grok_Build\`** - Grok global only.
- **Never write secrets** into config files.
- **Show the diff** before and after; explain what the change enforces.

## Routing by home

| Home | Where to write |
|------|----------------|
| `hook` | `.grok/hooks/grok-hooks.json` or a new `.grok/hooks/<name>.json` + wire in config if needed |
| `rule` | `.grok/AGENTS.md`, `.grok/rules/*.md`, or project `AGENTS.md` |
| `memory` | `.grok/memory/<topic>.md` |
| `skill` | `.grok/skills/<name>/SKILL.md` |
| `agent` | `.grok/agents/<name>.md` under `$GROK_HOME` |
| `permission` | `.grok/config.toml` `[permission]` section |
| `mcp` | `.grok/config.toml` `[mcp_servers.*]` |

## Procedure

1. Restate the approved change in one sentence.
2. Read the target file(s) and plan the minimal edit.
3. Apply the edit (prefer hook/lint over prose rule when enforceable).
4. If hooks changed, verify JSON is valid.
5. Offer `/backup-config` or a selective git commit of only the paths you touched.

## Grok mapping (Claude equivalents)

| Claude | Grok |
|--------|------|
| `settings.json` hooks | `.grok/hooks/*.json` |
| `CLAUDE.md` rules | `AGENTS.md` + `.grok/rules/` |
| `enabledPlugins` | Grok `marketplace` / `.grok/plugins/` |
| `permissions.allow/deny` | `config.toml` `[permission]` |