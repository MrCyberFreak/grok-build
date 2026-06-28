---
name: kanban-flow
description: Set up or analyze a Kanban board and its flow. Use when the user says 'set up a kanban board', 'design our workflow/columns', 'what WIP limits should we use', 'analyze our flow / cycle time / throughput', 'why is work piling up / stuck', 'read this cumulative flow diagram', or 'forecast when this will be done from flow data'. Covers the Definition of Workflow, columns, WIP limits, classes of service, and the flow metrics (WIP, cycle time, throughput, work item age, CFD, SLE). NOT for Scrum sprint mechanics (use sprint-plan) or backlog ranking (use backlog-refine). For exact definitions (the two Kanban canons differ), delegate to the agile-expert subagent.
---

# Set up / analyze Kanban flow

Help a team visualize and optimize flow. The two Kanban canons (the ProKanban **Kanban
Guide** and the Kanban University **Kanban Method**) differ in places — for exact
definitions, delegate to the **`kanban-expert`** subagent and attribute which guide a term
comes from.

## Setting up a board
1. **Define the Workflow (DoW)** — the unit of work, the **started** and **finished**
   points (which define WIP), and the states between them. Model the *actual* workflow
   ("start with what you do now"), not an idealized one.
2. **Columns** — one per workflow state, left→right toward done; consider explicit
   queue/buffer and "done" sub-columns. Add swimlanes for work types or classes of service.
3. **WIP limits** — set a limit per state/column (and/or per person/lane). Limits create a
   **pull** system ("stop starting, start finishing"); start conservative and tune.
4. **Explicit policies** — pull/"done" criteria per column, replenishment cadence, and a
   **Service Level Expectation (SLE)** (e.g. "85% of items finish within 10 days").
5. **Classes of service** (Kanban University) — Standard, Expedite, Fixed Date, Intangible
   — for differentiated handling by cost of delay.

## Analyzing flow (the four flow metrics)
- **WIP** — items started but not finished (too high → multitasking, long waits).
- **Cycle time** — start → finish elapsed (track the distribution + percentiles, not just average).
- **Throughput** — items finished per period (use for forecasting).
- **Work item age** — how long an in-progress item has been going (find aging/stuck work now).
Read the **Cumulative Flow Diagram** (band widths = WIP per state; diverging bands = a
bottleneck) and the **cycle-time scatterplot** (percentile lines → SLE). For "when will it
be done", forecast from throughput (Monte Carlo) rather than guessing.

## Output
The board design (workflow, columns, WIP limits, policies, classes of service) and/or a
flow diagnosis: which metric is off, the likely bottleneck, and 1–3 concrete experiments
(e.g. lower a WIP limit, split a state, swarm aging items). Optimize **flow/throughput**,
not resource utilization.
