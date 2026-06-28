---
name: backup-config
description: Back up / commit / push the global config (GROK_HOME) - new or changed skills, hooks, commands, agents, memory, or settings. Use when the user says 'back up my (global) config', 'commit the global config', 'save my new skills/hooks', or at session end to persist config artifacts. NOT for backing up a normal project repo, or for syncing the capabilities block.
allowed-tools: Bash, Read
---

Back up the **global config repo** (`$GROK_HOME` = `X:\Grok_Build\Global`)
safely: summarize what drifted, **review and selectively stage**, scan the staged
diff for secrets, then commit and push. This is config-repo only — project backups
have their own per-project "Backup" command and are out of scope.

## The hard rule (state it first, enforce it throughout)

**The global repo routinely carries UNRELATED uncommitted changes from other
sessions.** NEVER blind-`git add -A` by default. Default to a **reviewed, selective
stage**: show the user exactly which paths will be added and let them confirm.
`git add -A` is an explicit opt-in the user must ask for, never the silent default.

**Never push if anything secret-shaped is staged.** Per the global security rule,
scan the staged diff first; on any hit, STOP and report — do not commit or push.

## Procedure

### 1. Summarize the drift
Work in the config repo. From `$GROK_HOME` (resolve it; fall back to
`X:\Grok_Build\Global`):

```
git -C "$GROK_HOME" status --short
git -C "$GROK_HOME" diff --stat
```

Read the output. Group the changed/untracked paths by area so the user sees the
shape of the backup at a glance:

- **skills/** — new or edited `skills/<name>/SKILL.md` and helpers
- **hooks/** — `hooks/*.ps1`
- **commands/** — `commands/*.md`
- **agents/** — `agents/*.md`, `agents/tools/*`
- **memory/** — `memory/*.md` and the memory index
- **settings / docs** — `settings.json`, `CLAUDE.md`, `CLAUDE.template.md`, `AGENTS.md`
- **other / unrelated** — anything that looks like it belongs to a different task

Call out the **other / unrelated** group explicitly — those are the changes you must
not sweep in without asking.

### 2. Stage selectively (reviewed, not blind)
Propose the exact set of paths to stage — the groups from step 1 that belong to this
backup. Stage them by path, e.g.:

```
git -C "$GROK_HOME" add skills/ hooks/ commands/ agents/ memory/ AGENTS.md
```

Only run `git -C "$GROK_HOME" add -A` if the user **explicitly** opts in to
backing up everything. Then show what is staged:

```
git -C "$GROK_HOME" diff --cached --stat
```

### 3. Scan the staged diff for secrets (gate before commit)
Read the full staged diff and check it for credential-shaped content **before**
committing:

```
git -C "$GROK_HOME" diff --cached
```

Look for: API keys / tokens (e.g. `sk-`, `ghp_`, `xoxb-`, AWS `AKIA…`, bearer
tokens, long base64/hex secrets), private-key blocks (`BEGIN … PRIVATE KEY`), and
staged credential files (`*.key`, `*.pem`, `.env`, `*.credentials.json`). Also check
the list of staged files for those filename patterns:

```
git -C "$GROK_HOME" diff --cached --name-only
```

**If anything looks like a real secret, STOP.** Do not commit or push. Report the
file and line, and let the user remediate (unstage, move the secret to SecretStore,
add to `.gitignore`). Distinguish real secrets from obvious placeholders
(`.env.example`, `<your-token-here>`, test fixtures) — flag, don't false-alarm, but
when in doubt stop and ask.

### 4. Commit
If the scan is clean, propose a descriptive commit message grouped by area, e.g.
`Global config: add backup-config skill; register in AGENTS.md`. If the user passed a
message (`$ARGUMENTS`), use it; otherwise generate one from the grouped summary.
Commit on the user's approval:

```
git -C "$GROK_HOME" commit -m "<message>"
```

### 5. Push and report
```
git -C "$GROK_HOME" push
git -C "$GROK_HOME" rev-parse --short HEAD
```

Report: the staged groups, the commit message, the push result (branch + remote),
and the pushed commit hash. If the push failed (e.g. needs a pull/rebase first),
report the error verbatim and stop — don't force anything.

## When NOT to use this skill
- **Backing up a normal project repo** — use that project's own "Backup" command /
  flow; it runs from the project root, not `$GROK_HOME`.
- **Resolving submodule / nested-`.git` / gitlink issues** — out of scope here.
- **Editing config content** (writing skills, fixing settings) — this skill only
  backs up what already exists on disk.
