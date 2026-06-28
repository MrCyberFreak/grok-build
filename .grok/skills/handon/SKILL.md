---
description: Resume from the latest handoff doc in the current project and get this session up to speed
allowed-tools: Bash, Read, Glob, Grep, Task
argument-hint: "[optional: a specific handoff file, or a note on what to focus on]"
---

This is the complement to `/handoff`. Load the most recent handoff for **this
project**, re-establish context, and verify it still matches reality before
acting. A handoff is a snapshot from a prior session — treat it as a lead, not
ground truth.

## 1. Find the handoff to load

- If `$ARGUMENTS` names a specific file, use that.
- Otherwise search **canonical** `handoffs/handoff-*.md` at the project root.
  Pick the most recent by date, then by `-N` suffix (e.g. `-3` beats `-2`).
- **Legacy fallback:** if `handoffs/` is empty/missing, also check
  `docs/handoffs/handoff-*.md` (old scaffold path). If found, load it but note
  the project should migrate files to `handoffs/` at root.
- If neither location has a matching file, say so plainly and stop — suggest
  `/handoff` or `/recover-session`. Do not invent context.

Read the chosen file in full.

## 2. Re-verify against reality (don't trust the snapshot blindly)

The handoff may be stale — commits, edits, or fixes may have happened since.
Reconcile it with the current state:

- If this is a git repo: check `git log --oneline -10`, `git status --short`, and
  `git branch --show-current`. Compare against the handoff's "State" section —
  note anything that advanced past it (e.g. work listed as "not done" that is now
  committed).
- If not a git repo: spot-check that the files the handoff references still exist
  and still say what it claims (read the relevant `path:line` anchors).
- Flag any drift between the handoff and reality explicitly — don't silently
  proceed on outdated assumptions.

## 3. Brief the user and propose a plan

Print a short orientation to the chat:

- **Resuming from:** `<handoff file path>` (`<its date>`)
- **Where things stand:** 2-4 bullets reconciling the handoff with current state,
  calling out any drift you found.
- **Open items:** the unfinished work and gotchas from the handoff still relevant.
- **Proposed next step:** the first actionable item — incorporate the user's
  `$ARGUMENTS` note if they steered toward something specific.

Then ask the user to confirm or redirect before making changes. Don't start
editing until you've oriented them.
