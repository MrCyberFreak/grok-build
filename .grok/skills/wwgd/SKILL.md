---
name: wwgd
description: "What Would Gary Vee Do?" — get Gary Vaynerchuk's documented take on your current situation (personal brand, content, attention, marketing, hustle/mindset), as concrete suggestions you can accept, reject, or ask to see explained visually. Use when the user types /wwgd, asks "what would Gary Vee do", "WWGD", "how would GaryVee approach this", "channel Gary Vee on this", or wants a Gary-style gut-check on a content/audience/brand/entrepreneurial decision. Delegates to the garyvee-expert agent (which reads the sourced garyvee corpus and refreshes from his keynotes / podcast / books / socials), then runs an accept/reject/explain-more loop with visual explanations. NOT for factual platform mechanics or pricing (use tiktok-platform-monetization / brand-deals-sponsorship / digital-products-passive-income / faceless-content-strategy), and NOT for Boris (use /wwbd) or Karpathy (use /wwkd).
allowed-tools: Task, AskQuestion, Read, Grep, Glob, Edit, Write, Bash, WebFetch
---

# /wwgd — What Would Gary Vee Do?

Turn the user's situation into **Gary Vaynerchuk's documented take** — concrete, sourced
suggestions they can **accept**, **reject**, or **ask to see explained (visually)**. Gary is
chairman of VaynerX / CEO of VaynerMedia and a 6x bestselling author; this skill channels his
*documented* philosophy on attention, content, personal brand, and mindset — never a made-up persona.

The companion `garyvee-expert` agent does the grounding (reads `library/garyvee/garyvee.md`,
refreshes from live sources). This skill owns the **conversation with the user**: framing the
situation, presenting suggestions, and the interactive accept/reject/explain loop.

## Procedure

### 1. Capture the situation
- Use whatever the user passed after `/wwgd`. If they passed nothing, infer the situation from the
  current work/conversation (the content plan, the brand decision, the launch on the table).
- Only ask a clarifying question if the situation is genuinely empty or ambiguous — keep it to
  **one** short question. Gary would just look at the work and react.

### 2. Get Gary's take (delegate via Task)
- **Read** `$GROK_HOME/agents/garyvee-expert.md`.
- **Task** `subagent_type: generalPurpose` with prompt: full agent instructions + Mode A + situation/context.
- Expect structured suggestions with principle, source URL, confidence flag, visual seed, caveats.
- Follow-ups: new **Task** with prior output in context.

### 3. Present the suggestions (scannable)
Show them compactly so the user can react fast. For each:

> **N. <suggestion>** — *<named principle>* `[confidence]`

Then one line of *why this fits the situation*. Keep the source URL attached but unobtrusive.
**Lead with honesty about confidence:** mark anything `[inference]` clearly as "extrapolated from
his principles, not something he said." Surface any tension the agent flagged — especially where
his platform-specific advice has **evolved** (which platform is "underpriced" now changes over time).

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
- **Content-calendar / pillar→micro sketch** — e.g. one long-form piece exploded into a week of posts.
- **Give:ask ratio diagram** — jab-jab-jab-right-hook made concrete for their channel.
- **Before / after post** (fenced blocks) — a sales-y post vs a value-first one.
- **Platform-priority table** — where their attention is underpriced right now, by effort/payoff.
Keep prose minimal around the visual. If it needs material the agent didn't supply, ask the
`garyvee-expert` agent via a follow-up **Task** for it rather than inventing it — and pull a real
example/quote from a source, never a fabricated one.

### 6. Apply & wrap up
- For each **accepted** suggestion that's actionable here (e.g. draft the post, sketch the content
  calendar, restructure the offer), offer to apply it now — then do so on confirmation.
- Close with a short recap: what was accepted, what was applied, and the **source URLs** behind the
  accepted advice so the user can read Gary in his own words.

## Rules
- **It's advice, not orders.** Present; the user accepts/rejects. Never auto-apply without a yes.
- **Honesty over persona.** Sourced positions are "Gary said X (link)"; extrapolations are
  `[inference]`. Never fabricate a quote or imply he said something he didn't.
- **Lean visual** whenever the user wants more — diagrams/tables/before-after over walls of prose.
- **Date-stamp platform advice.** His "which platform / format" answer is time-sensitive; flag stale takes.
- If the corpus was stale or thin for this topic, say so and note the agent went live (or couldn't).
- To refresh the underlying corpus, tell the `garyvee-expert` agent to run **Mode B** (refresh the library).
