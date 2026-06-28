---
name: safe-commit
description: Safely make ONE incremental project commit of exactly the files named, mid-session: clear a stale .git/index.lock, stage by explicit path, verify + secret-scan the staged diff, then commit as the user - no AI attribution, no push. For 'commit this', 'commit these files: a.py b.py', 'checkpoint this change to the repo'. NOT the end-of-session handoff (use /handoff), NOT the global config repo (use /backup-config).
allowed-tools: Bash, Read
---

Make **one** safe, rules-compliant commit of **exactly the files the user names** to the
current **project** repo. This is the mid-session checkpoint ritual the global CLAUDE.md
spells out - stale-lock guard, explicit-path staging, parallel-session sweep guard, secret
scan, user identity, sandbox-disabled write - packaged so it stops being re-derived as a
fragile inline one-liner every time. It does **not** push, merge, or open a PR.

## Hard rules (state them first, hold to them)

- **Project repos only. REFUSE the global config repo.** If the repo root is
  `$GROK_HOME` (`X:\Grok_Build\Global`), STOP and route to **`/backup-config`** -
  that flow reviews + pushes the config. This skill never touches the config repo.
- **Never blind-delete `.git/index.lock`.** Remove it ONLY when there is no live `git.exe`
  AND its mtime is older than ~30s. Otherwise wait and re-check - a live git owns it.
- **Never `git add -A`. Stage by explicit path only.** "My files" = paths created/edited in
  THIS session. Leave foreign / other-session drift untouched - do not stage, revert, or
  clean it.
- **Abort if an unintended file is staged.** A parallel session can sweep its own files into
  the shared index; verify the staged set is EXACTLY what was asked before committing.
- **The secret scan gates the commit.** On any hit, STOP and report - do not commit.
- **Commit as the USER, never Claude.** No `--author`, no `GIT_AUTHOR_*`/`GIT_COMMITTER_*`,
  no `Co-Authored-By`, no "Generated with" / robot footer. ASCII-only message.
- **Sandbox off for the writes.** The lock delete and the commit must run with
  `dangerouslyDisableSandbox: true` or they silently miss the real drive (a sandboxed
  delete/commit reports success but the real drive never changes).
- **No push, no merge, no PR.** Out of scope - the user handles those separately.

## Inputs
- **Paths to stage** (optional): the files to commit. Default: the files created/edited in
  THIS session. If you cannot determine that confidently, ask rather than guess.
- **Commit message** (optional): if the user gives one, use it; otherwise generate a concise
  ASCII message from the staged set.

## Procedure

### 1. Confirm a project git repo (and refuse the config repo)
Resolve the repo root from the working directory:
```
git rev-parse --is-inside-work-tree
git rev-parse --show-toplevel
```
If it is not a work tree, STOP and say so. If the toplevel equals `$GROK_HOME`
(`X:\Grok_Build\Global`), STOP and route to **`/backup-config`**. Use the resolved root as
`<repo>` (an absolute path) for every command below - the Bash tool's cwd resets between
calls, so never rely on cwd; pass paths explicitly.

### 2. Stale-lock guard (never blind-delete)
Check for a stale `.git/index.lock` with the bundled guard (report-only first):
```
powershell -NoProfile -ExecutionPolicy Bypass -File "X:\Grok_Build\.grok\skills\safe-commit\scripts\lock-guard.ps1" -RepoPath "<repo>"
```
Read the `STATUS:` line. `NONE` -> proceed. `BUSY` (live git or lock < ~30s) -> do NOT
delete; wait a few seconds and re-check, or report and stop. `STALE-SAFE` -> remove it by
re-running with `-Delete`, and **set `dangerouslyDisableSandbox: true` on that Bash call**
(a sandboxed delete reports success but leaves the lock on the real drive):
```
powershell -NoProfile -ExecutionPolicy Bypass -File "X:\Grok_Build\.grok\skills\safe-commit\scripts\lock-guard.ps1" -RepoPath "<repo>" -Delete
```
Expect `STATUS: REMOVED`. If it comes back `BUSY (delete reported success but ... still
present)`, the call was still sandboxed - re-run with the sandbox disabled.

### 3. Stage by explicit path only (never -A)
Stage exactly the named (or this-session) files, by path:
```
git -C "<repo>" add -- <path1> <path2> ...
```
Never `git add -A` / `git add .`. Do not stage anything you did not create or edit this
session.

### 4. Show + verify the staged set (sweep guard)
```
git -C "<repo>" diff --cached --name-only
git -C "<repo>" diff --cached --stat
```
Confirm the list is EXACTLY the intended files. If any file you did not intend appears
(another session's drift swept into the shared index), unstage it and re-verify - do not
commit a surprise file:
```
git -C "<repo>" restore --staged -- <unintended-path>
```

### 5. Secret-scan the staged diff (gate before commit)
Run the bundled scanner over the staged diff:
```
powershell -NoProfile -ExecutionPolicy Bypass -File "X:\Grok_Build\.grok\skills\safe-commit\scripts\scan-staged-diff.ps1" -RepoPath "<repo>"
```
Exit `0` = clean. Exit `2` = possible secret(s) -> **STOP, do not commit**; report the
finding so the user can unstage/rotate it (or, if a genuine false positive, add an
`allowlist secret` marker on that line and re-run). Exit `3` = scanner error -> STOP and
investigate (it fails CLOSED on purpose). Also eyeball the diff yourself
(`git -C "<repo>" diff --cached`) for credential files (`*.key`, `*.pem`, `.env`,
`*.credentials.json`) and `sk_`-style keys the patterns might miss - belt and braces.

### 6. Commit as the user (sandbox off, no push)
Only if step 5 is clean. Commit exactly the named paths, as the user, with the sandbox
disabled so the write lands on the real drive:
```
git -C "<repo>" commit -m "<concise ASCII message>" -- <path1> <path2> ...
```
Set `dangerouslyDisableSandbox: true` on this Bash call. Do NOT pass `--author`, do NOT set
any `GIT_AUTHOR_*`/`GIT_COMMITTER_*`, and do NOT add a `Co-Authored-By` / "Generated with"
trailer or footer. **Do not push, merge, or open a PR.** Then report the result:
```
git -C "<repo>" rev-parse --short HEAD
git -C "<repo>" log -1 --stat
```
Report: the staged files, the commit message, and the new short hash. State explicitly that
nothing was pushed.

## When NOT to use this skill
- **Writing the end-of-session handoff** -> use **`/handoff`** (this skill only commits, it
  never writes the handoff doc).
- **Backing up / committing the global config repo** (`$GROK_HOME`) -> use
  **`/backup-config`**.
- **Pushing, merging, or opening a PR** -> out of scope; the user does those separately.
