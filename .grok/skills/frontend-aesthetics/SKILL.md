---
name: frontend-aesthetics
description: Pick a distinctive, intentional visual direction BEFORE writing any UI code, so the result does not read as a templated AI default. Use when building a new front-end UI, landing page, dashboard, or component from scratch, or when reshaping an existing UI that looks generic ("make this look good / less AI / more distinctive / give it a real design"). Runs a quick aesthetic-direction pass (thesis -> compact token system -> critique) then hands off to implementation. NOT for Anthropic's claude.ai/design product (use claude-design-expert); NOT for writing the framework code itself (use react-expert / frontend-framework-expert); for grounded styling rules and accessibility, defer to the frontend-design-expert agent + library/frontend-design/.
allowed-tools: Read, Glob, Grep
---

# frontend-aesthetics

A short, enforced design-direction pass to run **before** writing UI code. The goal: make
deliberate aesthetic choices instead of falling back to the defaults that make AI-built
UIs look templated. Written in-house; the technique is inspired by Anthropic's public
"Frontend Aesthetics" guidance (see References) - this skill paraphrases the method in our
own words and does not reproduce the proprietary skill text.

## When this fires
Building a new UI/page/component from scratch, or a request like "make this look good /
less generic / more distinctive / give it a real identity." Skip it for a tiny tweak to an
already-established design.

## The method

### 1. Lead with a thesis
Before any code, name the single most characteristic element of the subject's world and let
it drive the design. The hero is a thesis, not a hero image. One sentence: "This should
feel like ___, and the one move that signals that is ___." If you cannot name the move, you
do not have a direction yet.

### 2. Avoid the templated tells
These read instantly as "AI default" - do not reach for them unless the thesis genuinely
demands it:
- Inter + a purple/violet gradient + evenly rounded cards on a white page.
- Warm cream background with serif headings and a terracotta accent.
- Near-black background with an acid/neon-green accent.
- Broadsheet layout leaning on hairline rules to look "editorial."
Picking the opposite of a tell is not a direction either - make a positive choice.

### 3. Brainstorm a compact token system (first pass)
Sketch the smallest system that expresses the thesis - do not open a code editor yet:
- Color: a base + one accent with intent (what each role means), ideally derived from a
  single hue (see the OKLCH recipe in `library/frontend-design/design-quality-rules.md`).
- Type: a display/heading choice + a body choice + scale and weight rules.
- Layout: spacing rhythm, density, grid, and where the whitespace goes.
- Signature: the one distinctive move (a motif, a motion, a type treatment, a layout break).

### 4. Critique against the brief (second pass)
Before writing code, challenge each choice: is it specific to THIS brief, or could it be
pasted onto any project? Replace anything generic. Confirm the signature move survives.

### 5. Treat copy as design material
Words exist to make the UI easier to understand. Active voice, plain language, concrete
labels. Write the real microcopy, not lorem ipsum - it changes the layout.

### 6. Then build - grounded
Now implement, grounding the actual classes/tokens/components and accessibility in the
**frontend-design-expert** agent and `library/frontend-design/` (Tailwind v4, shadcn/ui,
Radix, WCAG 2.2). Need a ready-made starting aesthetic? Pull one from
`library/frontend-design/design-systems/CATALOG.md`.

## Output
- **Direction:** the thesis + the one signature move (1-2 sentences).
- **Tokens:** the compact color / type / layout / signature system.
- **Then:** proceed to implementation grounded in the frontend-design library.

## References
- Anthropic "Frontend Aesthetics" cookbook / frontend-design skill (the public technique
  this paraphrases): https://github.com/anthropics/claude-code/tree/main/plugins/frontend-design .
  That skill's text is proprietary (Anthropic Commercial Terms) and is NOT copied here. If
  you want the literal official version, it can be installed as a plugin:
  `claude plugin add anthropic/frontend-design` (a network plugin install - weigh it against
  the local plugin-lockdown posture first).
