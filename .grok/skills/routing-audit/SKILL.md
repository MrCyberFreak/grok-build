---
name: routing-audit
description: Adversarial routing/mis-delegation audit of the agent roster - detect pairs of agent description frontmatter that overlap enough to silently route a request to the wrong expert, missing/asymmetric 'NOT for X (use Y)' boundaries, and coverage holes - emits a ranked collision list with a one-line description fix each. Use after editing agent descriptions or adding agents. NOT capability gap/consolidation (use roster-steward), NOT YAML-validity/index drift (use sync-capabilities).
allowed-tools: Bash, PowerShell, Read, Glob, Grep, Task
argument-hint: [optional: a single agent name to audit only its nearest neighbors]
---

# routing-audit

A **thin, read-only orchestrator** that pressure-tests the agent roster for routing
collisions. It adds no new logic of its own - it reuses two existing capabilities: the
deterministic `hooks/audit-capabilities.ps1` check as a syntactic precondition, then the
`agentic-systems-architect` agent for the semantic pass. The output is a ranked collision
list with one one-line `description:` fix per item.

The problem it catches: after editing an agent's `description:` frontmatter (the literal
text the harness routes on), two sibling agents can overlap enough that a real request
**silently fires the wrong expert**, or a `NOT for X (use Y)` boundary goes missing or
one-sided. Until now this was only caught by ad-hoc, off-label prompting of
`agentic-systems-architect`. This skill makes that pass fixed and repeatable.

**PROPOSES ONLY.** It never edits an agent file, `AGENTS.md`, or any `CLAUDE.md`. Approved
fixes are applied by the user, then reconciled with `/sync-capabilities -Fix`.

## Hard rules (state them, then enforce them)

- **Read-only / propose-only.** Never edit any file. No `Write`, no `Edit` - the skill is
  not granted them. You emit a proposal table and stop.
- **Reuse, don't reinvent.** Do not hand-roll a YAML/frontmatter parser or a fresh
  routing critique prompt-from-scratch each run. Step 1 IS `audit-capabilities.ps1`; Step 3
  IS the `agentic-systems-architect` agent. This skill only sequences and frames them.
- **Ground every collision in quoted text.** Each finding must quote the actual
  `description:` fragments from the two agents - the harness routes on that text, so the
  audit must too. No collision claim without the verbatim words that cause it.
- **ASCII-safe everywhere.** Every line printed to chat stays cp1252-safe: plain hyphens,
  straight quotes, no smart quotes / em-dashes / emoji.
- **No AI attribution.** Never add a Claude/AI byline or "generated with" note to anything.
- **Restart caveat.** Description edits (if the user later applies any) only take effect
  after a session restart - subagents load at session start. Say so when you hand back.

## Inputs

- **none** (default): audit the whole active roster.
- **optional - a single agent name**: scope the pass to that agent and its nearest
  neighbors only (the siblings whose descriptions are most likely to collide with it).

## Procedure

### Step 1 - Syntactic precondition (deterministic, reused)
Run the capability audit report-only. Invoke it via the **Bash tool** calling `powershell`
(Windows PowerShell 5.1 - the truest interpreter on this machine, and the one Claude Code
itself uses to run `.ps1` hooks):

```
powershell -NoProfile -ExecutionPolicy Bypass -File X:/Grok_Build/.grok/hooks/audit-capabilities.ps1
```

Read its **Check 0** output (agent frontmatter validity + description hygiene). If any agent
FAILS Check 0 - malformed YAML, or a `description:` that silently de-registers the agent -
**STOP**: a de-registered agent cannot be routed to at all, so a routing audit over the
remaining set would be misleading. Route that to `/sync-capabilities` first, and resume the
routing audit only once Check 0 is clean. (Check 1/2 drift - AGENTS.md / CLAUDE.md
registration - is informational here and does NOT block the routing pass.)

### Step 2 - Enumerate the active roster
Glob `X:/Grok_Build/.grok/agents/*.md` and read each file's `name:` + `description:`
frontmatter. Include ONLY active global agents - skip:
- the `agents/tools/` helper scripts (not agents),
- any plugins-seed / cache / marketplace copies (`plugins-seed/`, `plugins/`, `library/`).

The `description:` value is the literal string the harness matches a request against; carry
it verbatim into Step 3.

### Step 3 - Delegate the adversarial routing pass (agentic-systems-architect)
Spawn the `agentic-systems-architect` agent via **Task** (read
`$GROK_HOME/agents/agentic-systems-architect.md` first) with a FIXED prompt
over the enumerated `name:` + `description:` pairs. Ask it to, grounded in quoted
description text:
- **rank description PAIRS** by routing-collision risk - how likely a real request lands on
  the wrong sibling;
- **list silent-mis-delegation cases** - where the harness would confidently pick the wrong
  expert with no signal that it erred (confident-wrong, no tell);
- **flag asymmetric or missing `NOT for X (use Y)` boundaries** - A excludes B but B does
  not exclude A, or a known overlap carries no boundary at all;
- **name coverage holes** - a plausible request that no description claims, or that several
  claim only weakly;
- and for each, give **ONE concrete one-line `description:` fix**.

If an agent name was supplied as input, scope the pass to that agent and its nearest
neighbors only.

### Step 4 - Emit the ranked collision table
Present a single table, highest-risk first:

| # | Collision (agent A vs agent B) | Which request misroutes | One-line description fix |

Follow it with a short list of **coverage holes** and any **one-sided NOT-boundaries**.
Quote the offending `description:` fragments so every row is auditable.

### Step 5 - Stop (propose only)
Do not edit anything. Hand back with: if the user approves fixes, **they** apply them to the
agent `description:` frontmatter, then run **`/sync-capabilities -Fix`** to reconcile the
shared index, and **auto-delegation / description changes only take effect after a session
restart** (subagents load at session start).

## When NOT to use this skill
- **Whether an agent should EXIST or be consolidated, or a capability GAP vs the live
  projects** -> `roster-steward`. This skill takes the roster as given and only audits the
  routing TEXT; it never proposes adding, removing, or merging an agent.
- **Malformed agent YAML, or AGENTS.md / CLAUDE.md index drift** -> `/sync-capabilities`
  (the deterministic registration reconciler). Step 1 here only READS its Check 0 as a gate;
  fixing that drift is sync-capabilities' job.

## Out of scope (never do these here)
- Editing any agent file, `AGENTS.md`, or a `CLAUDE.md`.
- Deciding whether an agent should exist or be merged (that is `roster-steward`).
- Fixing malformed YAML or index drift (that is `/sync-capabilities`).
