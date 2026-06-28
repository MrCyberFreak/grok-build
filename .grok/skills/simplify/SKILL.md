---
name: simplify
description: Quality-only cleanup on recent changes - remove dead code, reduce duplication, clarify names, tighten control flow - without changing behavior or expanding scope. Use when the user says simplify, clean up the diff, or after a working fix when the code is messy. NOT for feature work or refactors that change behavior.
argument-hint: "[optional file or scope]"
---

# simplify (Grok global)

Improve code quality on the **current change set** without altering behavior.

## Allowed

- Remove unused imports/variables
- Inline trivial wrappers
- Rename for clarity (local scope only)
- Extract repeated literals to named constants
- Simplify conditionals with identical behavior
- Delete commented-out dead code introduced in this change

## Not allowed

- New features or API changes
- Cross-file refactors unrelated to the task
- "While I'm here" cleanups outside the diff scope
- Behavior changes disguised as cleanup

## Procedure

1. Identify the diff scope (`git diff` or files touched this session).
2. Apply minimal quality fixes.
3. Re-run the same verify command the user or `AGENTS.md` specifies.
4. Summarize what simplified and confirm behavior unchanged.