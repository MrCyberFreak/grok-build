---
name: propagate
description: Propagate a changed value, fact, or decision to every stale reference across the project (or global config) - finding both literal copies AND paraphrases (e.g. "every 2 hours" == "7 runs/day" == "PT2H") and updating them with reviewed diffs. Use right after changing a config value, schedule/cadence, name, threshold, path, version, or a recorded decision, when other docs / CLAUDE.md / memory notes / comments may still cite the old value. NOT for turning corrections into durable rules (use distill) or reconciling the capability index vs disk (use sync-capabilities).
allowed-tools: Read, Edit, Grep, Glob, Bash
---

# propagate - update stale references after a deliberate change

When you change a value / fact / decision in one place, copies and PARAPHRASES of
the old value often linger elsewhere (docs, CLAUDE.md, memory notes, code comments,
configs) and silently go stale. This skill finds and reconciles them with reviewed
diffs.

A literal grep alone is not enough: "stale" is partly SEMANTIC - `PT2H`, "every 2
hours", and "7 runs/day" share no common string. This skill searches literal forms
AND model-generated paraphrases.

## Inputs
- `$ARGUMENTS` may state the change directly, e.g.
  `cadence: PT2H / "every 2 hours" / 7-per-day  ->  PT6H / "3x per day"`.
- Flags: `--global` also sweeps the global config vault (CLAUDE.md, `memory/`,
  AGENTS.md, `skills/`) in `$GROK_HOME`; default scope is the CURRENT
  project only.
- If the change is not given, infer it from the most recent edits / `git diff` and
  STATE your understanding before searching; ask the user if it is ambiguous.

## Procedure
1. **Pin the change.** Write down the OLD value(s) and the NEW value(s) explicitly,
   including every form each takes - the literal token, prose paraphrases, units,
   synonyms, and any derived/computed restatements. Example for a cadence:
   old = {`PT2H`, "every 2 hours", "every ~2h", "7 runs/day", "~7x/day"};
   new = {`PT6H`, "3x/day", "07:20 / 13:20 / 19:20"}.
2. **Set scope.** Current project repo by default; add the global config vault only
   with `--global`. State the scope. NEVER read or edit a sibling project's files.
3. **Search.** Grep each OLD form across scope (Grep tool) - include docs, CLAUDE.md,
   memory, code comments, and configs. Collect hits with file:line.
4. **Triage each hit** into:
   - **stale** - asserts the OLD value as CURRENT -> update to the NEW value.
   - **historical** - a changelog / "reduced from X" / dated note -> LEAVE; it is
     correctly about the past. Do not rewrite history.
   - **unrelated** - a coincidental match -> leave.
5. **Apply** the stale updates with Edit, preserving surrounding wording, units, and
   formatting. Show each change. Keep edits strictly additive where a file is
   append-only (e.g. memory notes, history/changelog files).
6. **Respect boundaries.** Do not touch other-session uncommitted drift; stage or
   commit nothing unless the user asks. ASCII-safe output only (cp1252 console).
7. **Report** a grouped summary: updated (file:line + old -> new),
   left-as-historical (with reason), and ambiguous hits that need a human decision.

## Notes
- This skill is the propagation companion to the global `propagate_record.ps1` +
  `propagate_nudge.ps1` Stop-hook nudge, which reminds you to run it after a
  value-bearing edit to a fact-bearing file.
- Proposes and applies edits only; it never commits or pushes. Back up via the
  normal project flow / `/backup-config` afterward.
