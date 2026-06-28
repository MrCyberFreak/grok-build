---
description: Go online and research whether someone has ALREADY SOLVED a given engineering problem before you build it. Searches package registries (npm, PyPI, crates.io, pkg.go.dev, Maven, NuGet, RubyGems, Packagist), GitHub, Stack Overflow, official docs/stdlib, standards/RFCs and recent blog posts for existing libraries, tools, snippets, algorithms or patterns; opens and vets the top candidates (maturity, adoption, maintenance, license, fit); and returns a build-vs-reuse verdict. Use when the user asks "has someone already solved this", "is there an existing library/package/tool for X", "don't reinvent the wheel", "what's the standard way to do X", or wants prior-art before implementing. NOT for general topic research (use deep-research) and NOT for searching the local codebase.
allowed-tools: WebSearch, WebFetch, Read, Glob, Grep, Task
argument-hint: "[optional: the problem/feature to check — defaults to the current task]"
---

Go online and find out whether the problem at hand is **already solved by existing,
reusable work** — a library, package, tool, repo, canonical snippet, named algorithm,
or established pattern — so the user can decide to **reuse instead of reinvent**. Do
real web research, vet the candidates, and end with a clear build-vs-reuse verdict.
Then STOP. Do not start implementing anything.

## 0. Scope the problem

1. **Get the problem statement.** If `$ARGUMENTS` is given, that's the problem. If it's
   empty, infer it from the current conversation — the thing the user is about to build
   or just asked how to do. Restate it in **one line** so we're aligned.
2. **Pin the constraints** that decide fit: language / ecosystem / runtime, platform
   (browser, Node, mobile, embedded, offline), license tolerance (can it be GPL? must it
   be permissive?), and any hard perf/size requirements. If the ecosystem is genuinely
   unknown and changes the whole search, ask one quick question; otherwise proceed with
   the most likely assumption and state it.
3. **Extract 3–6 search angles** — the canonical name of the problem, the algorithm or
   pattern term ("the X problem"), the ecosystem package term, and a couple of synonyms.
   The wrong vocabulary is the #1 reason prior art gets missed, so brainstorm names first.

## 1. Search broadly — fan out across source families

Run several `WebSearch` queries that hit **complementary** sources, not the same one
reworded. Cover, as relevant to the ecosystem:

- **Package registries** — is there a maintained package? (npm / PyPI / crates.io /
  pkg.go.dev / Maven Central / NuGet / RubyGems / Packagist / Homebrew).
- **GitHub** — `"<problem>" github`, `awesome <topic>`, reference implementations.
- **Q&A** — Stack Overflow / forums for the canonical answer to this exact problem.
- **Official docs & stdlib / platform APIs** — maybe it's already built in and needs no
  dependency at all. Always check this; it's the cheapest possible "solution."
- **Standards / RFCs / known algorithms** — maybe it's a named, solved problem with a
  textbook approach.
- **Recent blog posts / articles** — current best practice and "how people actually do
  this in <year>."

Vary the phrasing across queries; include the year when best-practice recency matters.
For a thorough sweep, optionally dispatch a few **Task** subagents (`subagent_type:
generalPurpose`) in parallel — one per source family — each returning its top finds with links.

## 2. Open and verify the top candidates

**Don't trust search snippets — `WebFetch` the real page.** For each serious candidate
(repo README, package page, the canonical SO answer, the relevant doc), capture:

- **What it does** and whether it actually covers the problem (or only part of it).
- **Adoption signal** — stars / downloads / "used by" — popularity ≈ battle-testing.
- **Maintenance** — last release and last commit; flag anything stale or archived.
- **License** — and whether it's compatible with the stated tolerance.
- **Fit & caveats** — gaps, heavy transitive deps, platform limits, API ergonomics.

Discard candidates that are abandoned, license-incompatible, or don't really fit, and say
why rather than silently dropping them.

## 3. Judge build-vs-reuse

Classify the situation:

- **Solved** — a mature, well-maintained, reusable solution exists and fits. Reuse it.
- **Partially solved** — something close exists but needs adaptation, glue, or forking.
- **Genuinely novel** — nothing credible fits; building it is the right call.

Weigh reuse cost (dependency weight, license, lock-in, learning curve, maintenance risk)
against build cost. Recommending **"build it"** is a perfectly valid, honest outcome when
nothing fits — don't force a reuse.

## Output

A tight, skimmable report — no padding:

- **Verdict** (one line): *Solved / Partially solved / Novel* + the headline recommendation.
- **Top options** (ranked, ≤5): name + link · one-line what-it-is · key stats
  (stars/downloads · last release · license) · fit & caveats.
- **Recommendation** (2–4 sentences): reuse X / adapt Y / build it, and *why*. If reuse,
  give the exact install/import line and a link to the doc to start from.
- **Searched on** `<today's date>` — flag that this is time-sensitive and adoption/
  maintenance facts can go stale.

Cite **every** factual claim with a link. If you genuinely found nothing credible, say so
plainly — never invent a library or inflate stats to manufacture an answer.
