---
name: wwbd
description: "What Would Boris Do?" — get Boris Cherny's (creator of Claude Code) documented take on your current situation, as concrete suggestions you can accept, reject, or ask to see explained visually. Use when the user types /wwbd, asks "what would Boris do", "WWBD", "how would Boris / the Claude Code team approach this", "channel Boris on this", or wants a Boris-style gut-check on an agentic-coding / harness / engineering-workflow decision, plan, or piece of code. Delegates to the boris-expert agent (which reads the sourced boris corpus and refreshes from his X / the Claude Code best-practices doc), then runs an accept/reject/explain-more loop with visual explanations. NOT for general Claude Code how-to (use claude-code-expert) or for Karpathy (use /wwkd).
allowed-tools: Task, AskQuestion, Read, Grep, Glob, Edit, Write, Bash, WebFetch
---

# /wwbd — What Would Boris Do?

Turn the user's situation into **Boris Cherny's documented take** — concrete, sourced
suggestions they can **accept**, **reject**, or **ask to see explained (visually)**. Boris
created and heads Claude Code at Anthropic; this skill channels his *documented* philosophy,
never a made-up persona.

The companion `boris-expert` agent does the grounding (reads `library/boris/boris.md`,
refreshes from live sources). This skill owns the **conversation with the user**: framing the
situation, presenting suggestions, and the interactive accept/reject/explain loop.

## Procedure

### 1. Capture the situation
- Use whatever the user passed after `/wwbd`. If they passed nothing, infer the situation from
  the current work/conversation (the file open, the decision being discussed, the plan on the table).
- Only ask a clarifying question if the situation is genuinely empty or ambiguous — keep it to
  **one** short question. Don't interrogate; Boris would just look at the work and react.

### 2. Get Boris's take (delegate via Task — same as any agent)
- **Read** `$GROK_HOME/agents/boris-expert.md`.
- **Task** `subagent_type: generalPurpose` with prompt: full agent instructions + Mode A + user's
  situation and enough context (code/plan/decision) to map principles onto it.
- Expect structured suggestions: action, named principle, source URL, confidence flag
  (`[verbatim]` / `[secondary]` / `[inference]`), "Show it" visual seed, tensions/caveats.
- Follow-up angles: new **Task** with prior output in context (same expert file, don't improvise persona).

### 3. Present the suggestions (scannable)
Show them compactly so the user can react fast. For each:

> **N. <suggestion>** — *<named principle>* `[confidence]`

Then one line of *why this fits the situation*. Keep the source URL attached but unobtrusive.
**Lead with honesty about confidence:** mark anything `[inference]` clearly as "extrapolated from
his principles, not something he said." Surface any tension the agent flagged.

### 4. Accept / reject / explain — the loop
Offer the user control over each suggestion. Use **AskQuestion** with options like:
- **Accept** (this one / all) — adopt it; if it's actionable here, offer to apply it.
- **Reject** (this one / all) — drop it.
- **Explain more** — they want it unpacked, **leaning visual** (see §5).
- **Mix / decide per item** — let them pick which to accept and which to expand.

Loop until the user has accepted or dismissed each suggestion. "Explain more" → explain → re-offer
accept/reject for that item.

### 5. Explain visually (the default for "tell me more")
When the user asks for more on a suggestion, **show, don't just tell.** Reach first for a visual,
using the agent's "Show it" seed:
- **Before / after** code or config diff (fenced blocks) — e.g. a bloated CLAUDE.md vs a lean one.
- **ASCII decision tree / flow** — e.g. "diff fits in one sentence? --> just do it / else --> plan first".
- **Comparison table** — e.g. glob+grep vs RAG across simplicity / freshness / failure modes.
- **A small diagram** — context window filling up; writer/reviewer parallel worktrees; the verify loop.
Keep prose minimal around the visual. If the visual needs material the agent didn't supply, ask the
`boris-expert` agent via a follow-up **Task** for it rather than inventing it — and pull a real example/quote
from a source, never a fabricated one.

### 6. Apply & wrap up
- For each **accepted** suggestion that's actionable in this project (e.g. trim CLAUDE.md, add a verify
  step, restructure a plan), offer to apply it now — then do so on confirmation.
- Close with a short recap: what was accepted, what was applied, and the **source URLs** behind the
  accepted advice so the user can read Boris in his own words.

## Rules
- **It's advice, not orders.** Present; the user accepts/rejects. Never auto-apply without a yes.
- **Honesty over persona.** Sourced positions are "Boris said X (link)"; extrapolations are
  `[inference]`. Never fabricate a quote or imply he said something he didn't.
- **Lean visual** whenever the user wants more — diagrams/tables/before-after over walls of prose.
- If the corpus was stale or thin for this topic, say so and note the agent went live (or couldn't).
- To refresh the underlying corpus, tell the `boris-expert` agent to run **Mode B** (refresh the library).
