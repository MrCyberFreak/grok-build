---
description: At session end, distill this session's corrections and mistakes into durable, forward-acting rules — proposing feedback memories, CLAUDE.md rules, or checks for the user to approve. Human-gated; nothing is written without a yes.
allowed-tools: Read, Write, Edit, Glob, Grep
argument-hint: "[optional: a specific correction/mistake to focus on]"
---

Turn what this session **taught** into things that fire next time. A correction is
only "learned" once it becomes a **forward-acting rule, a check, or a memory** — not a
logged anecdote (rules compound; corrections don't). Propose; the user approves. If
`$ARGUMENTS` names a specific lesson, focus there.

## 1. Scan this session

Reflect on the conversation already in context — no transcript file to parse. Look for:

- **Corrections** the user gave — preferences, "no, do it this way", course-corrections.
- **Mistakes I made + the fix that worked** — a tool that failed and the workaround, a
  wrong assumption and what was actually true.
- **Confirmed approaches** worth keeping — something that worked and should be the default.

Ignore one-off task content (that's `/oneprompt`'s job) and anything already known.

## 2. Dedup against what's already captured

Read what exists so you never propose a duplicate:

- The project's memory index + the files it points to — the `memory/MEMORY.md` loaded
  into this session (its path is shown in the session's memory system-reminder). If you
  can't determine the project's memory dir, **ask the user** for it.
- The global `X:\Grok_Build\.grok\CLAUDE.md`.

Skip anything already covered. If a lesson *refines* an existing memory, propose an **edit
to that file**, not a new one.

## 3. Route each candidate (escalation ladder — strongest home first)

For each surviving lesson, pick the most enforcing home it qualifies for:

1. **A check (hook / lint)** — if the mistake is *deterministic and checkable* (e.g.
   secret-scan-before-push, UTF-8/cp1252 console safety, drive-root Write fallback). Don't
   write a note — recommend the user run `/update-config` to add the hook/lint. A check the
   model *can't skip* beats a rule it must remember.
2. **A global CLAUDE.md rule** — if it's a *general behavioral rule that should always
   apply, across projects*. Must pass the march-of-nines gate (step 4).
3. **A feedback memory** — if it's *project- or context-specific*. The default for nuanced
   preferences.

## 4. March-of-nines gate (before anything graduates to global CLAUDE.md)

A global rule loads into EVERY session, so a subtly-wrong one misfires everywhere. Promote
to CLAUDE.md only if it passes both:

- **General, not one-repo?** Would it hold across unrelated projects? If it's really about
  one project, it's a feedback memory, not a global rule.
- **Not better as a check?** If it's checkable, prefer the hook/lint (step 1).

When in doubt, keep it as a feedback memory — cheaper to be wrong.

## 5. Draft candidates (0-3 max; 0 is a fine, common answer)

Be selective — a couple of high-value rules beat a pile of notes. Each **feedback memory**
must match the on-disk convention, and **the template below is that canonical shape — use
it directly.** If the target `memory/` dir already has files you may glance at one to
confirm formatting; if it's empty (a fresh project), just use the template and create the
dir — do NOT open another project's `memory/` vault to find an example (that both wastes a
step and breaks the stay-within-the-active-project rule for a detail the template already gives).

```markdown
---
name: <kebab-case-slug>
description: <one-line summary — used for recall and the MEMORY.md index>
metadata: 
  node_type: memory
  type: feedback
  originSessionId: <this session's id if you know it; OMIT this line rather than invent a UUID>
---

<2-3 sentences: the observation / correction / confirmed approach, with the concrete trigger.>

**Why:** <the underlying principle or user intent.>

**How to apply:** <forward-acting guidance — "always/never X in context Z". Link related memories with [[their-slug]].>
```

Every candidate MUST have a concrete **How to apply**. If you can't write one, it's an
anecdote, not a rule — drop it.

## 6. Present for approval (accept / reject / edit each)

Show the candidates compactly, grouped by destination (checks / CLAUDE.md rules / feedback
memories). For each: the proposed content and where it would go. Let the user accept,
reject, or edit each one individually. **Propose, never impose.** If nothing this session
is worth keeping, say so plainly and stop.

## 7. Write only the approved ones

- **Feedback memory** → write the file into the session's `memory/` dir. If the lesson is
  tentative / not yet proven, write it to the `memory/_candidates/` **messy vault** instead
  (create the folder if needed) — it graduates to the clean store later once proven. Append
  a one-line pointer to `memory/MEMORY.md`: `- [<Title>](<file>.md) — <hook>`.
- **CLAUDE.md rule** → show the exact diff, apply on confirmation.
- **Check** → don't implement it here; tell the user to run `/update-config`, summarizing
  what the hook/lint should enforce.

## 8. Wrap up

Print a short recap: what was written and where, what was routed to `/update-config`, what
was dropped. Remind the user to run `/backup-config` to persist new memory/command files to
the global config repo.

## Rules

- **Propose, don't impose.** Never write or edit a file without explicit approval.
- **Few and forward-acting.** Prefer 0-3 durable rules over a pile of notes; every kept item
  says what to do *next time*.
- **Honesty.** Don't invent provenance (session ids); don't label something a "mistake" if it
  wasn't. "Nothing worth capturing" is a valid result.
- **ASCII-safe console output** (the console is cp1252) and **no AI / Claude attribution** in
  any file you write (per the global CLAUDE.md).
