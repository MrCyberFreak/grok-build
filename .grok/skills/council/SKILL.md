---
name: council
description: Convene a multi-agent "LLM council" to pressure-test an idea, plan, or high-stakes decision from several independent expert angles (skeptic, operator, risk/legal, technologist, champion, devil's advocate) plus auto-scouted domain specialists, then return one synthesized go/no-go verdict. Use when the user says "convene the council", "ask the council", "pressure-test this idea", "stress-test this plan", "red-team this", or wants several independent perspectives before committing. NOT for one-question-at-a-time interrogation (use grill-me). Grok global skill — orchestrates via Task subagents, not Claude Workflow.
argument-hint: "[idea or question to test]"
---

# Council (Grok global)

Pressure-test an idea / plan / decision with an independent expert panel, then synthesize **one** go/no-go verdict.

**Reference implementation:** `X:\Grok_Build\.grok\workflows\llm-council.js` (ported from Claude; use as roster/phase spec).

## How to run it

1. **Get the question** verbatim. If too vague, ask ONE clarifying question, then proceed.

2. **Pick the mode:**
   - `personas` *(default)* — skeptic, operator, risk & counsel, technologist, champion, devil's advocate + 1–2 domain specialists (spawn via Task after reading matching `.grok/agents/<name>.md`).
   - `models` — same question to parallel subagents; use when user wants a model cross-check, not multi-domain idea review.

3. **Orchestrate with Task** (Grok equivalent of Claude `Workflow`):
   - **Phase 1 — First opinions:** spawn one Task per council seat (parallel). Each subagent answers independently; no peeking at others.
   - **Phase 2 — Peer review (optional, default on):** spawn reviewers; identities anonymized (Response A, B, …). Each critiques/ranks others.
   - **Phase 3 — Chairman:** spawn one Task (`generalPurpose` or strongest model) with all anonymized opinions + reviews; produce `final_answer` verdict.

   For AI/agent/data-system ideas, include `agentic-systems-architect` and/or `agent-eval-strategist` as explicit seats.

4. **Report back:** give the Chairman's `final_answer`. Offer per-seat detail if the user wants depth.

## Lean options

- `peerReview: false` — skip Phase 2
- `autoSpecialists: false` — fixed panel only

## Grok notes

- This is a **global** skill (`GROK_HOME/skills/council/`). Works in any project on `X:\`.
- ~6–8 subagents + chairman = heavy spend; use for real decisions.
- Edit roster defaults in `.grok/workflows/llm-council.js` or inline in the Task prompts.