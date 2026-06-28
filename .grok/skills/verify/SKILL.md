---
name: verify
description: Run the app, tests, or smoke checks to confirm a change actually works - not just that it compiles. Use when the user says verify, confirm it works, smoke test, or after a fix when runtime proof is needed. NOT for static code review (use code-review or check-work).
argument-hint: "[what to verify - test command, URL, script]"
---

# verify (Grok global)

Prove the change works at runtime.

## Procedure

1. Read project `AGENTS.md` / `README.md` for the canonical test/run command.
2. If none, infer the smallest smoke path (one test file, one CLI invocation, one HTTP hit).
3. Run it yourself via Shell.
4. Report: command run, exit code, relevant output, pass/fail.
5. For UI: headless screenshot if available; otherwise describe what you checked.

## Hard rules

- Do not claim verified without running something.
- On failure, show the error and propose a fix - do not stop at "tests failed".
- ASCII-safe console output.