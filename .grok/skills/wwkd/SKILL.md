---
name: wwkd
description: "What Would Karpathy Do?" — get Andrej Karpathy's documented take on your current situation, as concrete suggestions you can accept, reject, or ask to see explained visually. Use when the user types /wwkd, asks "what would Karpathy do", "WWKD", "channel Karpathy on this", or wants a Karpathy-style gut-check on an ML / LLM / agent / model-training / software-design / learning decision, plan, or piece of code (Software 2.0/3.0, vibe coding, build-from-scratch, the training recipe, overfit-one-batch, march-of-nines, keep-AI-on-a-leash, learn-by-building). Delegates to the karpathy-expert agent (which reads the sourced karpathy corpus and refreshes from his blog/X/talks), then runs an accept/reject/explain-more loop with visual explanations. NOT for Boris / Claude Code taste (use /wwbd).
allowed-tools: Task, AskQuestion, Read, Grep, Glob, Edit, Write, Bash, WebFetch
---

# /wwkd — What Would Karpathy Do?

Turn the user's situation into **Andrej Karpathy's documented take** — concrete, sourced
suggestions they can **accept**, **reject**, or **ask to see explained (visually)**. Karpathy:
OpenAI founding member, ex-Tesla AI director, creator of micrograd/nanoGPT/nanochat and "Neural
Networks: Zero to Hero", founder of Eureka Labs. This skill channels his *documented* philosophy,
never a made-up persona.

The companion `karpathy-expert` agent does the grounding (reads `library/karpathy/karpathy.md`,
refreshes from live sources). This skill owns the **conversation with the user**: framing the
situation, presenting suggestions, and the interactive accept/reject/explain loop.

## Procedure

### 1. Capture the situation
- Use whatever the user passed after `/wwkd`. If they passed nothing, infer the situation from the
  current work/conversation (the model/training decision, the agent/LLM design, the code, the
  learning plan).
- Only ask a clarifying question if the situation is genuinely empty or ambiguous — keep it to
  **one** short question. Karpathy would just look at the data/code and react.

### 2. Get Karpathy's take (delegate via Task)
- **Read** `$GROK_HOME/agents/karpathy-expert.md`.
- **Task** `subagent_type: generalPurpose` with prompt: full agent instructions + Mode A + situation/context.
- Expect structured suggestions with principle, source URL, confidence flag, visual seed, caveats.
- Follow-ups: new **Task** with prior output in context.

### 3. Present the suggestions (scannable)
Show them compactly so the user can react fast. For each:

> **N. <suggestion>** — *<named principle>* `[confidence]`

Then one line of *why this fits the situation*. Keep the source URL attached but unobtrusive.
**Lead with honesty about confidence:** mark anything `[inference]` clearly as "extrapolated from
his principles, not something he said." Surface any tension the agent flagged (e.g. "vibe code it"
vs "build it from scratch to understand it").

### 4. Accept / reject / explain — the loop
Offer the user control over each suggestion. Use **AskQuestion** with options like:
- **Accept** (this one / all) — adopt it; if it's actionable here, offer to apply it.
- **Reject** (this one / all) — drop it.
- **Explain more** — they want it unpacked, **leaning visual** (see §5).
- **Mix / decide per item** — let them pick which to accept and which to expand.

Loop until each suggestion is accepted or dismissed. "Explain more" → explain → re-offer accept/reject.

### 5. Explain visually (the default for "tell me more")
When the user asks for more on a suggestion, **show, don't just tell.** Reach first for a visual,
using the agent's "Show it" seed:
- **Minimal from-scratch code sketch** (fenced block) — the nanoGPT/micrograd move: the smallest thing
  that makes the idea concrete.
- **ASCII pipeline / decision diagram** — e.g. the recipe: `data --> skeleton+dumb baseline --> overfit one batch --> regularize --> tune`.
- **Comparison table** — e.g. Software 1.0 vs 2.0 vs 3.0; autonomy-slider settings; eval-before-optimize.
- **A curve / loop sketch** — overfit→regularize; the generate→verify loop; the "march of nines".
Keep prose minimal around the visual. If the visual needs material the agent didn't supply, ask the
`karpathy-expert` agent via a follow-up **Task** — and pull a real example/quote from a source, never fabricate.
(Remember the corpus note: x.com is fetch-blocked, so tweet wordings are snippet-sourced — don't over-quote.)

### 6. Apply & wrap up
- For each **accepted** suggestion that's actionable here (e.g. add an eval before optimizing, overfit one
  batch first, write a from-scratch baseline, put a human-in-the-loop checkpoint), offer to apply/scaffold
  it now — then do so on confirmation.
- Close with a short recap: what was accepted, what was applied, and the **source URLs** so the user can
  read Karpathy in his own words.

## Rules
- **It's advice, not orders.** Present; the user accepts/rejects. Never auto-apply without a yes.
- **Honesty over persona.** Sourced positions are "Karpathy said X (link)"; extrapolations are
  `[inference]`. Never fabricate a quote or imply he said something he didn't.
- **Lean visual** whenever the user wants more — diagrams/tables/code sketches over walls of prose.
- If the corpus was stale or thin for this topic, say so and note the agent went live (or couldn't).
- To refresh the underlying corpus, tell the `karpathy-expert` agent to run **Mode B** (refresh the library).
