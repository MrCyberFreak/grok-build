---
name: run
description: Launch the project's dev server, app, or main entrypoint so the user can interact with it. Use when the user says run it, start the server, launch the app. NOT for one-off smoke verification after a change (use verify).
argument-hint: "[optional port or target]"
---

# run (Grok global)

Start the project's main runnable.

## Procedure

1. Read `AGENTS.md` / `README.md` for the canonical run command.
2. Check if a dev server is already running (terminals folder or port probe).
3. Start in background if long-running (`is_background: true` in Shell).
4. Report URL/port and how to stop it.

## Hard rules

- Prefer config files (`ecosystem.config.js`, `package.json` scripts) over fragile inline PowerShell args.
- Do not block the session on a foreground server unless the user asked to watch logs.