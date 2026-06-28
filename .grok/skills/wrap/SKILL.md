---
description: End-of-session wrap-up - seals BOTH the project (via /handoff -> distill, handoff doc, gated commit+push) and the global Claude config (via /backup-config). Use to close out a session that touched config as well as project work.
allowed-tools: Bash, Read, Glob, Grep, Write, Skill
argument-hint: "[optional note about focus / what's unfinished]"
---

Close out the session cleanly by sealing **both** scopes that may have changed this
session: the current **project** AND the global **Claude config**. This is the one
command to run at session end when you touched config (skills, hooks, commands,
agents, settings) on top of project work — so neither scope gets left dirty.

## Order of operations (do not reorder)

1. **Seal the project — run `/handoff`** (pass along $ARGUMENTS via the Skill tool).
   That command already does the full project ritual in the correct order:
   `/distill` (capture this session's durable rules first) → gather git state →
   write the handoff doc → offer the **gated** commit + push. Let it fully complete,
   including the commit/push decision, before continuing.

2. **Seal the global config — only if it changed.** Check whether anything under
   `GROK_HOME` was added or edited this session (new/changed skills, hooks,
   commands, agents, `settings.json`, memory):

   ```
   git -C "$GROK_HOME" status --short
   ```

   (The global config is its own git repo.)
   - If there **are** changes → run **`/backup-config`** to commit + push them.
   - If there are **none** → say "global config clean — nothing to back up" and skip.

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
