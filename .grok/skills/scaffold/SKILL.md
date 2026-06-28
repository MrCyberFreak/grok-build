---
name: scaffold
description: Scaffold the full standard Grok project template (AGENTS.md, .editorconfig, .env.example, .grok/ placeholders, README, handoffs/, .gitignore, .gitattributes) into the current project folder, and offer to git-init if it isn't a repo yet. Migrates legacy Claude Code CLAUDE.md to AGENTS.md when present. Safe to re-run - never overwrites existing files. Use right after opening Grok in a fresh project folder.
argument-hint: "[-Force] [-NoMigrateLegacy]"
---

# scaffold (Grok global)

Lay down the standard project template into the current working directory.

## Grok vs legacy Claude Code

| Legacy (Claude Code) | Grok branch |
|----------------------|-------------|
| `CLAUDE.md` | **`AGENTS.md`** (canonical) |
| `.claude/` | **`.grok/`** (project-local skills/agents/hooks/rules) |
| `$CLAUDE_CONFIG_DIR` | **`$GROK_HOME`** (`X:\Grok_Build\.grok`) |

Grok also reads `CLAUDE.md` for compatibility when present, but **new projects get `AGENTS.md` only**. `/scaffold` migrates an existing `CLAUDE.md` automatically.

## Procedure

1. Run the scaffold engine (pass `$ARGUMENTS` through):

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File X:/Grok_Build/project-template/scaffold-project.ps1 -Set all $ARGUMENTS
   ```

   Flags:
   - `-Force` — overwrite existing template files
   - `-NoMigrateLegacy` — skip `CLAUDE.md` → `AGENTS.md` conversion

2. Read its created / migrated / skipped summary and report it back.

3. The script auto-fills `<Project Name>` and `<YYYY-MM-DD>` in freshly-created `AGENTS.md` / `README.md`.

4. **Legacy migration (default on):**
   - If `CLAUDE.md` exists and `AGENTS.md` does not → convert content to Grok-native `AGENTS.md`, rename `CLAUDE.md` to `CLAUDE.md.migrated.bak`
   - If `.claude/` exists → ensure `.grok/` placeholder dirs exist; tell user they can remove `.claude/` when ready

5. Check whether `.git` exists.
   - If NOT a repo, ask whether to `git init`. Only run if they confirm.
   - If already a repo, do nothing further.

6. Do NOT invent project details. Leave remaining `<...>` placeholders for the user. Point out that `AGENTS.md` still needs purpose / status / commands filled in.

## Template location

`X:\Grok_Build\project-template\` — Grok layout (`.grok/` not `.claude/`).