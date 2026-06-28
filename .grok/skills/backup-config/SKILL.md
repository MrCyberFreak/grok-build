---
name: backup-config
description: Back up / commit / push the **global Grok harness** (in the grok-build repo root) - new/changed skills, hooks, .grok/ config, agents, memory, or settings. Use when the user says 'back up my (global) config', 'commit the global config', 'save my new skills/hooks', or at session end to persist harness artifacts. **Never** for project work (use per-project handoff or safe-commit). The global repo is the one at X:\Grok_Build (grok-build on GitHub).
allowed-tools: Bash, Read
---

Back up the **global Grok harness** (in the grok-build Git repo at the workspace root)
safely: summarize what drifted **under .grok/**, **review and selectively stage only harness
paths**, scan the staged diff for secrets, then commit and push **only to the global grok-build
repo**. 

**Project work must never land here** — use the project's own repo via /handoff or safe-commit.
This skill is global-harness only.

## The hard rule (state it first, enforce it throughout)

**Only the global harness repo.** Before any git command, resolve the repo root and
assert it is the workspace root that contains `.grok/` (the grok-build remote).
If you are inside a `Projects/<name>/` worktree, **STOP** and tell the user to use
the project flow instead.

**The global repo routinely carries UNRELATED uncommitted changes from other
sessions.** NEVER blind-`git add -A` by default. Default to a **reviewed, selective
stage** limited to `.grok/` paths: show the user exactly which paths will be added
and let them confirm.
`git add -A` is an explicit opt-in the user must ask for, never the silent default.

**Never push if anything secret-shaped is staged.** Per the global security rule,
scan the staged diff first; on any hit, STOP and report — do not commit or push.

## Procedure

### 1. Confirm we are in the global harness repo + summarize drift
Resolve the current repo root:

```
git rev-parse --show-toplevel
```

If this toplevel is inside a `Projects/<name>` (or matches a project worktree), **STOP**
and route the user to project-specific flows (`/handoff`, `/safe-commit`).

The global root must be `X:\Grok_Build` (contains `.grok/`). Set:

```
$GROK_ROOT = "X:\Grok_Build"
```

Then:

```
git -C $GROK_ROOT status --short -- .grok/
git -C $GROK_ROOT diff --stat -- .grok/
```

Read the output. Group **only** changes under .grok/ :

- **.grok/skills/** — new or edited skills
- **.grok/hooks/** — hooks
- **.grok/agents/** — agents
- **.grok/config.toml**, **.grok/AGENTS.md**, **.grok/rules/**, **.grok/memory/**
- **.grok/** other (library updates, etc.)

Ignore anything outside .grok/ (that's project drift or other — never stage it here).

Call out anything outside .grok/ explicitly and refuse to include it.

### 2. Stage selectively (reviewed, not blind)
Propose **only .grok/ paths**. Example (use $GROK_ROOT = "X:\Grok_Build"):

```
git -C $GROK_ROOT add -- .grok/skills/ .grok/hooks/ .grok/agents/ .grok/config.toml .grok/AGENTS.md .grok/rules/ .grok/memory/
```

**Never** use `git add -A` or paths outside `.grok/`. Show:

```
git -C $GROK_ROOT diff --cached --stat -- .grok/
```

### 3. Scan the staged diff for secrets (gate before commit)
```
git -C $GROK_ROOT diff --cached -- .grok/
```

Scan for secrets as before (keys, tokens, etc.). If any hit, STOP.

Also:
```
git -C $GROK_ROOT diff --cached --name-only -- .grok/
```

### 4. Commit
```
git -C $GROK_ROOT commit -m "<message>" -- .grok/...
```

Commit as the user, no AI attribution.

### 5. Push and report
```
git -C $GROK_ROOT push
git -C $GROK_ROOT rev-parse --short HEAD
```

Report what was pushed to the **grok-build** remote only.

## When NOT to use this skill
- **Project work** — use the project's repo via `/handoff`, `/safe-commit`, etc.
- **Anything outside .grok/** at the workspace root — refuse it.
- **Resolving submodules or gitlink issues** — out of scope.
- **Editing** — this skill only backs up existing changes (use other flows to edit).
