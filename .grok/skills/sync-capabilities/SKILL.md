---
description: Roster/config wrap-up. First validates every agent's frontmatter (Check 0 - catches a malformed description: that silently de-registers an agent) plus description hygiene, then reconciles the hand-maintained capability surfaces (AGENTS.md registration + the shared CLAUDE.md "Capabilities" block) against what's on disk, and finishes with a restart/smoke-test reminder. Use after adding, removing, or editing a skill, command, or agent, or to check for capability drift. Pass -Fix to sync the CLAUDE.md blocks.
allowed-tools: Bash, PowerShell, Read, Edit, Glob, Grep
argument-hint: "[-Fix] [-ProjectsRoot <path>]"
---

Reconcile the capability surfaces that DON'T update themselves. The filesystem
(`skills/<name>/SKILL.md`, `agents/<name>.md`, and the session menu) are the source of truth and
self-update; this command catches drift in the two hand-maintained derivatives:
`AGENTS.md` (the canonical index) and the shared **"Capabilities — see the global
index"** block copied into `CLAUDE.template.md` and each project's `CLAUDE.md` (for compat).

## Steps

1. **Run the audit** (report-only first), passing any `$ARGUMENTS` through:

   ```
   powershell -NoProfile -ExecutionPolicy Bypass -File X:/Grok_Build/.grok/hooks/audit-capabilities.ps1 $ARGUMENTS
   ```

   It prints three checks - Check 0 (agent frontmatter validity + hygiene), Check 1
   (AGENTS.md registration), Check 2 (CLAUDE.md block drift) - and exits non-zero if
   anything is unresolved. Read its output.

2. **Fix Check 0 FAILs first** - an agent whose frontmatter does not parse is *silently
   de-registered*. The usual cause is a `description:` that starts with a quote or contains
   `: ` (colon-space). Safe fix: re-emit the `description:` value as a valid YAML scalar
   (double-quote the whole value and escape inner `"`, or rephrase to a plain scalar with no
   leading quote and no `: `). Then address WARNs as warranted: a dead handoff pointer
   (`use <name>` for an agent/skill not on disk), a missing proactivity nudge, or a `name:`
   that differs from the filename.

3. **Fix AGENTS.md gaps by hand** (the script never edits AGENTS.md — it's curated
   prose). For each `skill/command/agent "<name>" is on disk but NOT listed` finding:
   - Read the capability's own `description:` frontmatter
     (`skills/<name>/SKILL.md` or `agents/<name>.md`).
   - Add a one-line entry to the right section of `AGENTS.md`:
     §1/§2 for agents, §3 for skills, §6 for CLI tools/scripts. Match the
     terse house style of the existing rows.
   (Note: `commands/` style files are legacy Claude Code; Grok uses `skills/<name>/SKILL.md`.)

4. **Sync the CLAUDE.md block** only if Check 2 reports drift AND the user wants it
   reconciled: re-run step 1 with `-Fix` appended. This rewrites only the shared
   block in the template + project files from the global canonical — nothing else.

5. **Report + finish.** Say what changed (frontmatter fixes, AGENTS.md entries, CLAUDE.md
   files synced), re-run the audit once to confirm a clean `RESULT`, then follow the printed
   **Next (roster wrap-up)** reminder: restart the session so agent edits reload, smoke-test a
   couple of unprompted requests, and run `/backup-config` if the global config changed.

## Notes
- Default is report-only. `-Fix` touches only the CLAUDE.md shared block — never AGENTS.md,
  never the agent files (Check 0 fixes are applied by hand).
- Check 0 needs `python` + `pyyaml` for full YAML validation; without them it falls back to a
  shallow structural check and says so.
- This is the manual counterpart to the registration step baked into `skill-builder`;
  run it any time the index feels stale, after editing agents, or on a schedule.
