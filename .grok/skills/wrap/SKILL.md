---
description: End-of-session wrap-up - seals BOTH the project (via /handoff) **and** the global Grok harness (via /backup-config, but only if global .grok/ changed). Project work always goes to the project's own GitHub repo; global harness changes only to grok-build. Use when a session touched both.
allowed-tools: Bash, Read, Glob, Grep, Write, Skill
argument-hint: "[optional note about focus / what's unfinished]"
---

Close out the session cleanly by sealing **both** scopes:
- Current **project** (its own GitHub repo)
- Global **Grok harness** (only if .grok/ changed — goes exclusively to the grok-build repo)

Use when the session touched both the project **and** global harness.

## Order of operations (do not reorder)

1. **Seal the project — run `/handoff`** (pass along $ARGUMENTS via the Skill tool).
   That command already does the full project ritual in the correct order:
   `/distill` (capture this session's durable rules first) → gather git state →
   write the handoff doc → offer the **gated** commit + push. Let it fully complete,
   including the commit/push decision, before continuing.

2. **Seal the global harness — only if .grok/ changed.** Check only under the
   global root for changes inside `.grok/` (skills, hooks, agents, config.toml, etc.):

   ```
   $GROK_ROOT = "X:\Grok_Build"
   git -C $GROK_ROOT status --short -- .grok/
   ```

   - If changes under `.grok/` → run **`/backup-config`** (it will only touch the
     global grok-build repo).
   - Otherwise → "global harness clean — nothing to back up".

3. **Report** a 3–5 line summary: the handoff path, what was committed/pushed in each
   scope (or that the user declined), and anything still open.

## Rules

- **Everything stays gated.** Both `/handoff`'s commit and `/backup-config` act only
  with the user's explicit go-ahead in the turn — never commit, push, or merge
  automatically.
- The author/committer is always the **user** — no `--author`, no Claude identity,
  and no `Co-Authored-By` / "Generated with" trailer or footer anywhere.
- **Never auto-merge** in either scope. On a non-default branch, offer a PR instead.
- The pre-push secret-scan hook (`PreToolUse` on `git push`) guards every push; if it
  blocks, surface the finding and stop — do not bypass it.
