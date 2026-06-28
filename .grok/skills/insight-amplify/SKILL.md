---
name: insight-amplify
description: Deep, swarm-built insights report that derives its OWN judgments from raw usage data (per-session facets + metrics + transcripts) instead of parroting a built-in report - and evaluates relationships across agents, skills, experts, and libraries. Loads live Grok config and subtracts what you already built so only the genuinely-new survives, adversarially verifies every finding, writes a styled HTML report that auto-opens, then offers a grounded Boris/Karpathy persona read. Use when the user says "amplify my insights", "run insight-amplify", "what's actually new for me", "analyze my Grok usage", or wants a state-aware usage report. PROPOSES only, never a score. NOT for turning THIS session's corrections into rules (use distill). Grok global skill - orchestrates via Task subagents.
argument-hint: "[optional --since YYYY-MM-DD to bound the window]"
---

# insight-amplify (Grok global)

Produce the report a power user actually needs: **reads the same raw data and forms its own judgments**, **maps the capability ecosystem**, **subtracts what you already built**, and **adversarially verifies** every finding before it ships.

**Reference spec:** `X:\Grok_Build\.grok\workflows\insight-swarm.js` (ported from Claude; use as phase/roster spec).

## Hard rules

- **Laymans per block, default Laymans.** Every text box ships Full + Laymans wording; per-block toggle; toolbar "All: Laymans/Full".
- **Graphics are consistent - no toggle.** Stats/charts/ecosystem counts shown once.
- **Response UI on top only.** Accept/Reject/Comment per block; Compose + Export decisions. Never drop report content for UI.
- **Derive, don't parrot.** Source of truth is `facets/` + `session-meta/` + transcripts, not any pre-chewed suggestion list.
- **Verify against LIVE config.** Read actual `config.toml`, `.grok/hooks/`, skill/agent files, `AGENTS.md`. Drop anything already implemented.
- **PROPOSE, never install.** Approved checks route through `/update-config`.
- **No score, ever.**
- **ASCII-safe everywhere.**

## Paths

```
SK=X:/Grok_Build/.grok/skills/insight-amplify/scripts
UD=X:/Grok_Build/.grok/usage-data
WORK=$UD/.amplify
CFG=X:/Grok_Build/.grok
LIB=X:/Grok_Build/.grok/library
```

## The loop

### Step 0 - optional: capture built-in insights JSON
If a built-in insights report/JSON is in context, save to `$WORK/insights.json`. Otherwise skip.

### Step 1 - DETERMINISTIC GROUNDWORK
```powershell
$env:PYTHONUTF8=1
New-Item -ItemType Directory -Path $WORK -Force | Out-Null
python $SK/gather_state.py --pretty | Set-Content $WORK/inventory.json -Encoding utf8
python $SK/aggregate_usage.py --pretty | Set-Content $WORK/usage.json -Encoding utf8
python $SK/analyze_relationships.py --inventory $WORK/inventory.json --usage $WORK/usage.json --pretty | Set-Content $WORK/relationships.json -Encoding utf8
```
Sanity-check counts before continuing.

### Step 2 - LEDGER STATE
```powershell
python $SK/ledger.py recurrence-check --category destructive-ops --category overreach --category encoding --category truncation --category other | Set-Content $WORK/recurrence.json -Encoding utf8
```

### Step 3 - SWARM (Task subagents)

Orchestrate with **Task** (Grok equivalent of Claude `Workflow`). Read `.grok/workflows/insight-swarm.js` for phases:

| Phase | Task seats |
|-------|------------|
| **Analyze** (parallel) | work-usage, friction, ecosystem, roster-steward, skill-scout, wins, horizon |
| **Subtract** | subtract+recommend (rank genuinely-new items vs inventory) |
| **Verify** (parallel) | agent-eval-strategist grounding audit, overlap/refutation pass |
| **Synthesize** | merge into findings schema |
| **Voice** | per-block laymans twins in `findings.laymans` |

Each Task subagent gets: inventory, usage, relationships paths + ground rules from the workflow spec. For roster-steward / skill-scout / agent-eval-strategist, read `.grok/agents/<name>.md` first.

Write the returned findings object to `$WORK/findings.json`.

### Step 3b - MANDATORY epistemics audit
Spawn `agent-eval-strategist` via Task to audit `findings.json` for hallucinated sources, false redundancy, and ungrounded claims. Apply corrections before render.

### Step 4 - APPEND NEW FRICTION TO LEDGER
For each `findings.new_ledger_entries`, run `ledger.py append` (safe to re-run; refuses duplicate ids).

### Step 5 - RENDER + AUTO-OPEN
```powershell
$DATE = Get-Date -Format 'yyyy-MM-dd'
$OUT = "$UD/amplified-insights-$DATE.html"
python $SK/render_report.py --findings $WORK/findings.json --usage $WORK/usage.json --relationships $WORK/relationships.json --out $OUT --date $DATE
Start-Process $OUT
```

### Step 6 - PRESENT FINDINGS
Short chat summary: headline thesis, top 3 recommendations, ecosystem health line, verify-loop status, report path.

### Step 7 - OFFER PERSONA READ
**AskQuestion**: Boris / Karpathy / Both / Skip. If chosen, spawn via **Task** + write `$UD/amplified-insights-$DATE-persona-takes.md`.

### Step 8 - CLOSE
Remind: proposals only; `/update-config` for hooks, `AGENTS.md` for rules, memory vault for memories.

## Grok notes

- Global skill at `GROK_HOME/skills/insight-amplify/`. Works in any project on `X:\`.
- Library corpora are read-only at `X:\Grok_Build\.grok\library\` (agents still reference them).
- ~8+ subagents = heavy spend; use when you want a real state-aware report.
- Without `usage-data/facets/` data yet, rollup may be sparse; transcript scan still works from `.grok/sessions/`.