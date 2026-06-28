# Council — design notes

The `/council` skill is a natural-language trigger ("convene the council",
"pressure-test this idea") that launches the global **`llm-council`** workflow
(`.grok/workflows/llm-council.js` — Grok runs council via **Task** subagents per `SKILL.md`).
Inspired by [Andrej Karpathy's `llm-council`](https://github.com/karpathy/llm-council)
— no external app, no OpenRouter account, no paid API.

## Three-stage flow (both modes)

1. **First opinions** — each council member answers **independently**.
2. **Peer review** — each member ranks/critiques the others with **identities hidden**
   (anonymized A/B/C…); tallied Borda-style.
3. **Chairman** — Opus 4.8 synthesizes one verdict.

## Two modes

| | `models` (Karpathy-style) | `personas` (idea pressure-test) |
|---|---|---|
| Diversity axis | 3 Claude models, same question | distinct expert lenses, each its own angle |
| Members | Opus 4.8, Sonnet 4.6, Haiku 4.5 | Skeptic · Operator · Risk & Counsel · Technologist · Champion · Devil's Advocate + 1-2 auto-scouted specialists |
| Best for | cross-checking one judgment/factual answer | "is this idea any good / should we do this" |
| Default | yes (back-compat) | passed by the skill for idea reviews |

**Why personas mode exists:** correlated same-vendor models add little signal
(["Nine Judges, Two Effective Votes"](https://arxiv.org/html/2605.29800)); *reasoning/persona
diversity* is what helps, and a **hard-assigned Devil's Advocate** is the only role
shown to reliably break sycophantic agreement
([Only the Devil's Advocate Works](https://openreview.net/forum?id=mxBmj5LYU2)). Grounded in
[multi-agent debate](https://arxiv.org/abs/2305.14325) and the
[panel-of-judges](https://arxiv.org/abs/2404.18796) findings.

> **Honest caveat:** Workflow subagents run on Claude-family models only, so this is *not*
> a true cross-vendor council. What's faithful is the **structure** + (in personas mode)
> genuine lens diversity. For real GPT/Gemini/Grok diversity, use Karpathy's OpenRouter app.

## Run

```
> convene the council on: should we ship feature X now or wait for the redesign?
> pressure-test this idea: <idea>            # personas mode
```

Or invoke the workflow directly: `Run /llm-council with args { question: "...", mode: "personas" }`.

## Output

`final_answer` (the Chairman's verdict) · `council` (members + confidence) ·
`specialists` (auto-scouted seats) · `anonymized_map` · `borda_tally` · `reviews`.

## Customize

Edit `$GROK_HOME/workflows/llm-council.js`: the `PERSONAS` roster, the `MODELS`
list, `CHAIRMAN_MODEL` (`opus` | `sonnet` | `haiku` | `fable`), and the `peerReview` /
`autoSpecialists` defaults.
