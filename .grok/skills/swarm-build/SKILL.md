---
name: swarm-build
description: Orchestrate a multi-stream parallel BUILD with subagents in isolated git worktrees — scope read-only, partition by disjoint file ownership, implement each stream in its own worktree, then gated merge-back, verify, secret-scan and push, cleanup. Use when the user asks to "swarm" parallel build tasks, "parallel agents in git worktrees", or partition a build by file ownership. NOT for read-only analysis swarms (insight-amplify). Grok global skill — uses Task subagents + worktree.ps1.
argument-hint: "[optional: list of tasks/streams; optional repo path]"
---

# swarm-build (Grok global)

Phased, safety-gated parallel build: each stream in its **own git worktree**, merge back under human gates.

**Helper:** `X:\Grok_Build\.grok\skills\swarm-build\scripts\worktree.ps1`

Invoke via Shell:
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "X:/Grok_Build/.grok/skills/swarm-build/scripts/worktree.ps1" -Action create -Repo "<abs-repo>" -Stream "<name>" -Base main
```

## Hard rules

- **Disjoint file ownership** — overlap → STOP at scope phase.
- **Never auto-resolve merge conflicts.**
- **Never merge onto non-default branch** without offering a PR.
- **Push only after clean secret-scan + explicit go-ahead.**
- **Git identity:** `cyberdabadoo <cyberdabadoo@gmail.com>` — no AI attribution.
- **Keep pre-swarm backup until verify passes.**
- **ASCII-safe** console output.
- **Worktree cleanup:** use `worktree.ps1 -Action remove` (.NET delete fallback).

## Grok harness mapping

| Claude | Grok |
|--------|------|
| `Workflow` / `Agent` fan-out | **Task** tool — parallel subagents |
| Isolated worktree per stream | `worktree.ps1` + optional Task `best-of-n-runner` for isolated experiments |
| `Explore` scope pass | Task `subagent_type: explore` |

## Procedure

### Phase 0 — Pre-flight (GATED)
Backup repo to sibling dir → git-init if needed → ensure private remote (`gh repo create --private`, gated). Report, then continue.

### Phase 1 — Scope (READ-ONLY)
Parallel Task `explore` subagents → conflict map, implementation DAG, **disjoint file-ownership partition**. Writes nothing. Overlap → STOP.

**Mandatory:** consult `agentic-systems-architect` (Task + read `.grok/agents/agentic-systems-architect.md`) on partition soundness. Show partition + DAG; get go-ahead.

### Phase 2 — Worktrees + parallel implementation
Per stream: `worktree.ps1 -Action create`, then one **Task** per worktree with owned-file set ONLY. Parallel Task batch. Each commits on its stream branch.

### Phase 3 — Merge-back (GATED)
Merge in DAG order on default branch. Conflict → STOP and report.

### Phase 4 — Rebuild / verify (GATED)
Run project test gate; report **actual** output. Fail → keep backup, STOP.

### Phase 5 — Secret-scan + push (GATED)
Scan staged diff; push only on clean scan + explicit approval.

### Phase 6 — Cleanup
`worktree.ps1 -Action remove` per stream. Retire backup after Phase 4 green.

## When NOT to use
- Read-only swarms → `insight-amplify`
- Single-stream change → edit directly
- Parallel research without merge → Task `explore` directly

## Global scope
This skill lives at `GROK_HOME/skills/swarm-build/`. Use from any repo under `X:\`.