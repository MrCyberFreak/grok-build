---
name: sprint-plan
description: Facilitate Scrum Sprint Planning - craft a Sprint Goal, select Product Backlog items against the team's capacity, and produce a concrete sprint plan. Use when the user says 'plan a sprint', 'run sprint planning', 'set a sprint goal', 'what should we commit to this sprint', or 'help me fill the sprint'. Walks the three Sprint Planning topics (why / what / how). NOT for prioritizing or estimating the wider backlog (use backlog-refine), writing story text (use user-stories), running a retrospective (use retro), or generic methodology questions (delegate to the agile-expert subagent).
---

# Facilitate Sprint Planning

Run a focused Sprint Planning session and output a sprint plan. For planning facilitation
delegate to the **`sprint-expert`** subagent (and **`scrum-expert`** for exact Scrum-Guide
rules: timeboxes, who decides what, the artifacts/commitments) rather than relying on memory.

## Inputs to gather first
- **Sprint length** (1–4 weeks) and the **timebox** (max 8h for a one-month Sprint, pro-rata).
- **Team capacity** this Sprint (people, days, leave/holidays, support load) and recent
  **velocity** or **throughput** if available — use a *range*, not a single number.
- The **ordered Product Backlog** (top items, ideally INVEST-ready with acceptance criteria).

## The three topics (Scrum Guide 2020)
1. **Why is this Sprint valuable?** Draft a single, outcome-focused **Sprint Goal** with the
   Product Owner's input. One coherent objective — not a list of tickets.
2. **What can be Done?** Select the top backlog items that serve the Sprint Goal and fit
   capacity. Pull from the top of the order; stop when capacity is realistically full
   (leave slack for the unknown). Confirm each selected item is understood and testable.
3. **How will the work get done?** Have the Developers decompose selected items into a plan
   (tasks/sub-items, often a day or less each). Surface dependencies and risks.

## Output
- The **Sprint Goal** (one sentence).
- The **Sprint Backlog**: selected items (with estimates if present) + the plan.
- **Capacity check**: chosen load vs. available capacity, with the slack you left.
- **Risks / dependencies / assumptions** and any items deferred.
Offer to write the plan to a file or the team's tool.

## Guardrails (common antipatterns to avoid)
- No Sprint Goal, or a "goal" that's just the ticket list. Push for one real objective.
- Filling to 100% capacity (sandbagging-or-overcommit). Plan for sustainable pace.
- Treating the forecast as an iron commitment. It's a forecast; scope can be renegotiated
  with the PO without endangering the Sprint Goal.
