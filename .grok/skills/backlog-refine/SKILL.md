---
name: backlog-refine
description: Refine, estimate, and prioritize a product backlog. Use when the user says 'refine/groom the backlog', 'prioritize these features/items', 'estimate these stories', 'what should we build first', 'rank this list', or 'run planning poker'. Gets items ready (INVEST), estimates them (story points / relative sizing / t-shirt), and orders them with a chosen method (MoSCoW, WSJF, RICE, value-vs-effort). NOT for selecting one Sprint's work (use sprint-plan) or authoring story text/acceptance criteria (use user-stories). For exact formulas/definitions, delegate to the agile-expert subagent.
---

# Refine, estimate & prioritize a backlog

Turn a rough list into an ordered, ready backlog. For exact methods delegate to the
**`agile-backlog-expert`** subagent (refinement + prioritization: MoSCoW/WSJF/RICE/Kano) or
the **`agile-metrics-expert`** subagent (estimation / planning-poker mechanics).

## 1. Get items ready (refinement)
Ensure each candidate is **INVEST**-ready: clear value, vertically sliced, small enough,
testable with acceptance criteria. Split or merge as needed (hand off heavy story-writing
to the `user-stories` skill). Flag anything too vague to estimate → spike it.

## 2. Estimate
Pick the method to fit the need:
- **Story points** (relative; effort + complexity + uncertainty) via **planning poker** —
  private estimates, simultaneous reveal, discuss high/low, re-estimate to consensus.
  Calibrate against **reference stories**; use modified Fibonacci (1,2,3,5,8,13,20,…).
- **T-shirt sizing** (XS–XL) for fast/portfolio-level sizing.
- **Throughput / item-count** forecasting if the team runs `#NoEstimates`/flow-based.
Never convert points to fixed hours, and never compare teams by their numbers.

## 3. Prioritize (choose a method)
- **MoSCoW** — Must / Should / Could / Won't-this-time (Musts define the minimum usable set).
- **WSJF** = Cost of Delay / Job Size (CoD = user-business value + time criticality + risk
  reduction/opportunity enablement). Best when sequencing for economic value.
- **RICE** = (Reach × Impact × Confidence) / Effort.
- **Value vs. Effort** quadrant / **Kano** for feature mix; **Cost of Delay** when timing matters.
Ask which lens fits; apply it consistently across all items.

## Output
A single **ordered backlog**: rank · item · estimate · priority score (and the method) ·
notes. Call out the top "ready" items (good candidates for the next `sprint-plan`), and
anything still blocked or needing a spike.
