---
description: Capture this session's lessons (/distill) then write a handoff doc so the next session resumes cleanly. If the user gives no focus note, you MUST summarize what changed this session yourself for the Focus section.
allowed-tools: Bash, Read, Glob, Grep, Write, Skill
argument-hint: "[optional note about focus / what's unfinished — if omitted, auto-summarize session changes]"
---

Produce a **handoff document** that lets a fresh Grok session resume this work
with full context and zero re-discovery. Be concrete and honest — this is an
audit trail, not a status report. Never claim something is done or working that
you didn't actually verify.

## Focus description (required — user note OR your summary)

The optional `$ARGUMENTS` note becomes the **Focus** section (or frames it).
**If the user provides a note:** weave it in as the primary framing, still
grounded in what actually changed.

**If `$ARGUMENTS` is empty or omitted:** you MUST write Focus yourself from the
session — do not ask the user, do not leave a placeholder, do not write "N/A".
Synthesize 1-2 sentences from:
- `git diff` / files created or edited this session (or filesystem list if no git)
- The conversation arc: what was requested, what landed, what is still open
- Any `/distill` or config changes from steps 1-2

Example (empty args): "Aligned handoff docs to `handoffs/` at project root,
updated scaffold + `/handon` fallback, migrated Jarvis2 handoffs; X-drive
lockdown from prior session still uncommitted."

## 1. Capture this session's lessons first (`/distill`)

Durable rules must be locked in **before** the handoff snapshots state. `/distill`
and the skill scan (step 2) are the end-of-session steps that can *write* artifacts
(feedback memories, CLAUDE.md rules, hooks, or a new skill); the handoff merely
*photographs* the project. If you handoff first, anything they write afterward
won't appear in the handoff and immediately makes it stale. So: lock in the lessons
and skill opportunities, then photograph the room.

Before gathering state, invoke the **`/distill`** skill (via the Skill tool) to turn
this session's corrections and mistakes into proposed durable rules. It is
human-gated and self-skipping — if nothing this session is worth hardening, it
says so and you move straight on. Let the user approve or decline its proposals,
then continue; the handoff below will record whatever it wrote.

Skip this step only if the user has already run `/distill` this session or
explicitly tells you to skip it — say which, and proceed.

## 2. Scan for skill opportunities (skill-scout)

With the lessons captured, do the same for *process*: spot any repeated or manual
workflow from this session that a new or existing skill could streamline. Like
`/distill`, this runs **before** the snapshot so anything it produces is captured
by the handoff rather than left out of it.

**Read** `$GROK_HOME/agents/skill-scout.md`, then **Task** `subagent_type: generalPurpose`
with that body + a summary of this session and current state; ask it to spot any process
worth turning into a skill.

Surface its result as a short addendum:
- If it recommends an **existing** skill → relay the recommendation; the user
  decides whether to use it.
- If it proposes a **new** skill → show the Skill Spec and ask whether to hand it
  to `skill-builder`. Do **not** build anything without approval.
- If it finds **nothing** → say so in one line (this is a normal outcome) and move
  on. Do not manufacture a suggestion.

Keep this to a few lines — it's a routine checkpoint, not the main event. Skip it
only if the user tells you to.

## 3. Gather state (ground the handoff in reality — don't guess)

First detect whether this project is a git repo:

```
git rev-parse --is-inside-work-tree 2>/dev/null
```

- **If it is a git repo**, gather:
  - `git status --short` — uncommitted / untracked changes
  - `git branch --show-current` — current branch
  - `git log --oneline -10` — recent commits
  - `git diff --stat` then `git diff` — working-tree changes not yet committed
- **If it is NOT a git repo**, skip all git commands. Instead establish state
  from the filesystem and the conversation: list the files you created or edited
  this session and note that the project is not version-controlled (so there is
  no commit audit trail — the handoff itself is the record).

Then review the conversation for decisions, dead ends, and intent that isn't
visible in the files.

**Draft the Focus line now** (before writing the file) using the rules above so
it is ready when you fill the template.

## 4. Write the handoff (always into the current project)

Save to `handoffs/handoff-<project>-<YYYY-MM-DD>.md` **relative to the project
root** (the current working directory), where `<project>` is the project root's
directory name, lowercased with non-alphanumeric runs collapsed to `-`
(e.g. `Fargo` → `fargo`, `My App` → `my-app`). Create the `handoffs/` directory
at the project root if it doesn't exist. **Never** write to `docs/handoffs/`
(legacy scaffold path — `/handon` only checks it as a fallback for old projects).
If a file for today already exists, add a `-2`, `-3` … suffix before `.md` —
never overwrite a prior handoff.

Use this structure:

```markdown
# Handoff — <date>

## Focus
<1-2 sentences. User note if given ($ARGUMENTS); otherwise YOUR summary of what changed this session — never blank>

## State
- Version control: <git branch + last commit hash/subject | "not a git repo">
- Working tree / files: <clean | list of uncommitted/untracked or newly created files>

## Done this session
- <concrete, verifiable items — what changed and where (file:line)>

## In progress / not done
- <what was started but is incomplete, and exactly where it stands>

## Key decisions & context
- <decisions made and *why*; constraints; things not obvious from the code>
- <dead ends tried and rejected, so the next session doesn't repeat them>

## Next steps
- <ordered, actionable. The first item should be runnable immediately.>

## Gotchas / open questions
- <failing tests, env quirks, unverified assumptions, decisions awaiting the user>
```

## 5. Seal the session (gated commit + push — ask first)

After the handoff doc is written, **offer** to commit and push this session's work
(code + the rules `/distill` wrote + the handoff). Commit/push is **always explicit
and never automatic** — do nothing here unless the user agrees in this turn.

If they agree:
1. Show `git status --short` + a one-line scope summary so they see what will land.
2. Stage deliberately — avoid a blind `git add -A` when personal or gitignored files
   are around. Commit as the **user**: never pass `--author`, never set a Claude
   identity, and never add a `Co-Authored-By` / "Generated with" trailer or footer.
3. Push. The pre-push secret-scan hook (`PreToolUse` on `git push`) runs
   automatically and **blocks** the push if it finds a credential in the outgoing
   diff. If it blocks, surface the finding and stop — do not bypass it.
4. **Never auto-merge.** On a non-default branch, offer to open a PR instead.

If this session also changed global config (`GROK_HOME`: skills, hooks,
settings, agents), use **`/wrap`** instead — it does this *and* runs `/backup-config`.

## Rules

- **Verify before claiming.** If tests ran, report the actual pass/fail output.
  If a step was skipped, say so plainly.
- Respect any project-specific invariants documented in the repo's CLAUDE.md
  when describing the work.
- Keep it scannable — bullets over prose. Link files as `path:line`.
- The session's lessons and skill opportunities were already captured in steps 1-2
  (`/distill` and skill-scout); make sure any memory / CLAUDE.md / hook / skill
  files they wrote are reflected in the **State** and **Done this session**
  sections so the handoff isn't stale.
- **Focus is never empty.** User note or auto-summary — always one of the two.
- After writing, print the saved file path, the Focus line you used, and a 3-5
  line summary to the chat.
