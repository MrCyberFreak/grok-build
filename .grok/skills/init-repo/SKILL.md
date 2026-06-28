---
name: init-repo
description: >
  USE WHEN starting work in a project that lacks a grok-leverage
  AGENTS.md (no `grok-leverage:` marker blocks at git root), or when
  user asks to set up the stack here. Drops AGENTS.md + `.gitignore`
  patterns + optional language-specific logging template. Migrates
  legacy CLAUDE.md when present. Interactive, idempotent via markers.
  NOT for full project layout (use /scaffold).
argument-hint: "[target-dir] [--lang python|typescript|go|rust|none] [--noninteractive]"
---

# /init-repo (Grok)

## What it does

Sets up a fresh (or existing) repository for the **Grok branch** conventions:

1. **AGENTS.md** — Grok-canonical project rules (replaces legacy `CLAUDE.md`).
   Uses `project-template/AGENTS.template.md` as the base when none exists.
2. **Legacy migration** — if only `CLAUDE.md` exists, run `/scaffold` migration
   logic (convert → `AGENTS.md`, backup `CLAUDE.md.migrated.bak`).
3. **.gitignore** — append grok-leverage state patterns (`.last-stack-check`, etc.).
4. **Logging template** (optional, per detected language) — structured-logging starter.

**Does NOT create `CLAUDE.md`.** Grok reads `AGENTS.md` first; `CLAUDE.md` is legacy.

Each step is **confirmed before write**. Re-running detects marker comments and
offers update-in-place.

## Workflow

1. **Resolve target dir.** Default cwd. Verify git repo or ask to proceed.

2. **Detect language** from manifests (`package.json`, `pyproject.toml`, `go.mod`, `Cargo.toml`).

3. **Plan the changes** and show the user:
   ```
   I'll add the following to <target-dir>:
     1. AGENTS.md       — Grok project rules (or migrate from CLAUDE.md)
     2. .gitignore      — append grok-leverage state patterns
     3. logging starter — optional, per language
   Proceed? (y / n / select-subset)
   ```

4. **AGENTS.md**
   - If `CLAUDE.md` only: run `scaffold-project.ps1 -Set config` (migrates automatically).
   - Else if no `AGENTS.md`: customize from `X:/Grok_Build/project-template/AGENTS.template.md`.
   - Wrap body in `<!-- grok-leverage:agents-md START/END -->` markers.
   - Point capabilities section at `$GROK_HOME/CAPABILITIES.md` — do not inline the global roster.

5. **.gitignore** — append:
   ```
   # <!-- grok-leverage:gitignore START -->
   .last-stack-check
   session-nudges-*.txt
   security-nudges-*.txt
   .grok/settings.local.json
   # <!-- grok-leverage:gitignore END -->
   ```

6. **Ensure `.grok/` placeholders** exist (`skills/`, `agents/`, `hooks/`, `rules/`).

7. **Summarize** what was written and what needs human follow-up.

## Hard rules

- **Never create CLAUDE.md** on the Grok branch.
- **Confirm before write** (unless `--noninteractive`).
- **Idempotent** via `grok-leverage:` markers.
- **Refuse random non-git dirs** unless user explicitly allows.

## Pairs with

- `/scaffold` — full template (README, handoffs, git files, `.grok/`)
- `/repo-doctor` — audit AGENTS.md quality and sync drift
- `/sync-capabilities` — reconcile capability index after edits

## What this skill does NOT do

- Configure CI, install toolchains, or run `git init` (offer only).
- Duplicate the global capability list into project `AGENTS.md`.