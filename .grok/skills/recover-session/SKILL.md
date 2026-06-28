---
name: recover-session
description: Recover a crashed or interrupted Claude Code session that left NO handoff: reconstruct where you were from the prior session's transcript and git state, then offer to write the missing handoff so /handon can resume. Use for 'the session crashed/died/was interrupted, pick up where we left off / what was I doing' with no handoff, when /handon finds no handoff, or 'reconstruct what I was doing from the transcript'. NOT /handon (an EXISTING handoff), NOT /handoff (writes one at clean end), NOT cleaning drift or stale locks.
allowed-tools: Bash, Read, Glob, Grep, Skill
---

Recover a **crashed or interrupted** Claude Code session that has **no handoff
doc**. `/handon` deliberately stops in exactly this case (it resumes only when a
`handoffs/` file already exists). This skill reconstructs "where you were" from
the prior session's **transcript** plus **git forensics**, then **offers** to
write the missing handoff so the normal `/handon` flow can take over.

## Hard rules (state them first, hold to them)

- **Strictly read-only / report-only.** This skill never deletes a lock, never
  edits/reverts/stages/cleans foreign drift, and never writes the handoff itself.
  Everything it finds is reported; any *action* is the user's call.
- **Never write the handoff here.** When the user agrees, hand off to **`/handoff`**
  (gated, the user's identity, no AI attribution) - do not write the file yourself.
- **ASCII-only output** (the console is cp1252; curly quotes / em-dashes / emoji
  throw `UnicodeEncodeError`). The helper script already strips non-ASCII.
- **Leave other sessions' work alone.** Uncommitted / untracked / staged changes you
  did not create are off-limits - report, never touch (per the global rule).

## 1. Locate the prior session transcript

Transcripts live at `$GROK_HOME/projects/<encoded-cwd>/*.jsonl`
(`$GROK_HOME` = `X:\Grok_Build\Global`). The directory name is the
current working directory with **each** `:` `\` `/` `_` replaced by `-`,
char-by-char (NOT run-collapsed):

```
X:\Grok_Build\Projects\PoolPredict  ->  X--Claude-Code-Projectes-PoolPredict
```

(`X:` + `\Claude` becomes `X--Claude` - one dash from the `:`, one from the `\`.)

**Do not trust the reconstruction blindly** - also list the projects dir and pick
the one that matches the cwd:

```
$cwd = (Get-Location).Path
Get-ChildItem "$env:GROK_HOME\projects" -Directory | Select-Object Name
```

Then pick the transcript to parse:

- List the `*.jsonl` files in that dir by last-write time (newest first).
- **The current (recovery) session is ALSO writing a transcript** in the same dir.
  So do **not** assume the newest file is the crashed one - it is probably *this*
  session. Prefer the most-recent **other** transcript: if the newest file is the
  one being appended to right now (it is the active session), take the
  **2nd-most-recent**, or the largest other file.

```
Get-ChildItem "$env:GROK_HOME\projects\<encoded>\*.jsonl" |
  Sort-Object LastWriteTime -Descending |
  Select-Object Name, LastWriteTime, Length
```

State which file you chose and why, so the user can correct you if you grabbed the
wrong one.

## 2. Parse its tail (helper script)

Run the bundled read-only tail-parser on the chosen transcript:

```
powershell -NoProfile -ExecutionPolicy Bypass -File `
  "$env:GROK_HOME\skills\recover-session\scripts\parse_transcript.ps1" `
  -Path "<chosen transcript path>" -Last 40
```

It surfaces, ASCII-safe:

- **LAST USER REQUEST** - the last real typed prompt (not a tool result / meta tag).
- **RECENT ACTIVITY** - the trailing assistant text + `tool_use` + `tool_result`
  events in order.
- **IN-FLIGHT TOOL CALLS** - any `tool_use` near the end with no matching
  `tool_result` (the work that was cut off mid-flight).

Bump `-Last` (e.g. `-Last 80`) if the tail is all tool noise and the real request
isn't visible. Read the output as *leads*, not gospel - the run crashed, so it may
be incomplete.

## 3. Git forensics (only if in a git repo)

Confirm first: `git rev-parse --is-inside-work-tree`. If it is a repo, gather and
reconcile transcript *intent* against committed *reality*:

```
git branch --show-current
git status --short
git log --oneline -10
git stash list
git worktree list
```

Note where the transcript's last intent landed: was the in-flight edit committed,
left uncommitted, stashed, or done in a worktree? Call out drift between "what the
session was trying to do" and "what actually made it to disk / git".

## 4. Flag leftover artifacts (REPORT ONLY - never act)

Surface, but do **not** touch:

- **A confirmed-stale `.git/index.lock`** - only if there is **no live `git.exe`**
  **AND** the lock's mtime is older than ~30s. Report it and *suggest the user*
  remove it (e.g. via `[System.IO.File]::Delete`). **Do not delete it yourself** -
  a live git may own it.
- **`.backup-*` / sibling worktree dirs** left by an interrupted swarm/backup - list
  them so the user can clean up later. Do not remove them.
- **Uncommitted FOREIGN drift** - files that are not part of the recovered work
  (another/concurrent session's changes). Report their existence and stop there;
  never edit, revert, stage, or clean them (the leave-other-sessions-alone rule).

## 5. Output a /handon-style brief, then offer the handoff

Print a short orientation to the chat, mirroring `/handon`:

- **Resuming from:** `<transcript file>` (its timestamp) - and why you picked it.
- **Where things stand:** 2-4 bullets reconciling the transcript's last intent with
  git reality (step 3), flagging any drift.
- **In-flight work:** the unfinished tool call(s) / last action from step 2 - exactly
  what was cut off.
- **Leftover artifacts:** anything from step 4 (stale lock / backups / foreign drift),
  each marked *report-only, your call*.
- **Proposed next concrete step:** the first actionable item to resume the work.

Then **offer** to write the missing handoff by invoking **`/handoff`** (via the Skill
tool) so the next `/handon` resumes cleanly. **Do not write or edit anything** - not
the handoff, not a lock, not drift - without the user's explicit go-ahead in this turn.

## When NOT to use this skill

- **A handoff already exists** -> use `/handon` (it resumes from the latest handoff).
- **Writing a handoff at a clean session end** -> use `/handoff`.
- **Deleting a stale lock / cleaning drift / removing backup dirs** -> out of scope;
  this skill only *reports* those (report-only), it never performs the cleanup.
