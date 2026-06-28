---
name: scaffold-expert
description: Create a new expert agent and its grounding library from a short brief, or split an existing expert into per-X children. Use for "add/create a new expert", "new persona advisor", "scaffold an expert + its corpus/library", "split <x>-expert into per-framework experts". Scaffolds library/<x>/, authors the <x>-expert agent from the persona-advisor or two-mode docs-librarian template with NOT-boundaries, optionally seeds the /ww<x> skill (persona = agent + skill pair per rules/05-capability-taxonomy.md), delegates corpus-authoring, then wires .gitignore + CAPABILITIES.md and validates. NOT for building a standalone skill from a spec (skill-builder), reconciling an existing roster (sync-capabilities), or refreshing a persona corpus (the expert's own Mode B).
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Task
argument-hint: [expert name + topic, or "split <x>-expert"]
---

# scaffold-expert — stand up a new expert end-to-end

Turn a short brief into a **working expert**: the canonical `library/<x>/` skeleton, the
`<x>-expert` agent from the right template, an optional `/ww<x>` skill, then the corpus
build (delegated) and the wire+validate tail. This skill **assembles and sequences** the
~7-step recipe; it does **not** write corpus prose (that's the fan-out's judgment work) or
decide *whether* the expert is worth creating (that's `roster-steward` / the human).

The leaves are already owned — `skill-builder` builds the `/ww<x>` skill from a spec,
`sync-capabilities` runs the wire/validate tail. This skill owns the **middle**: the
library scaffold, the agent from a template, and the sequencing that ties it together.

## Inputs (capture from the brief; ask only for what's missing)
- **name** — kebab-case stem, e.g. `stripe` → agent `stripe-expert`, library `library/stripe/`.
- **type** — `persona-advisor` | `docs-librarian` | `umbrella-router` (picks the template).
- **topic/scope** — one-liner: what it owns and the NOT-boundary (what it does *not* own).
- **canonical sources** — the URLs/feeds/books the corpus is grounded in.
- **/ww<x> skill?** — whether to also seed the persona `/ww<x>` skill (persona-advisor only).
- *(optional)* register in the persona currency-watch (`refresh_persona_corpora.ps1`).

If the brief is a **split** ("split agile-expert into per-framework experts"), the name is
each child stem; read the parent agent + library first to inherit scope and sources, and
record the split in the parent's `_meta.json`.

## Procedure

### 1. Preflight — confirm the name is free, pick the template
- Check for collisions: **no** `agents/<x>-expert.md`, **no** `library/<x>/` directory,
  **no** existing `<x>-expert` mention in `AGENTS.md`. If any exist, stop and ask before
  overwriting — never clobber an existing expert or corpus.
- Pick the template by `type`:
  - `persona-advisor` → `agents/boris-expert.md` (Mode A advise / Mode B refresh,
    `[verbatim]`/`[secondary]`/`[inference]` flags, person-corpus).
  - `docs-librarian` → `agents/agile-expert.md` (Mode A answer / Mode B build, source-URL +
    version grounding) — use the non-routing shape for a single-topic expert.
  - `umbrella-router` → `agents/agile-expert.md` *with* its routing table (an umbrella that
    defers framework depth to dedicated child experts).

### 2. Scaffold `library/<x>/`
Create the canonical skeleton (write UTF-8, ASCII-safe):
- `library/<x>/<x>.md` — empty stub with a one-line title comment; the fan-out fills it.
- `library/<x>/_meta.json` — sidecar matching the schema of `library/scrum/_meta.json`
  (docs) or `library/boris/_meta.json` (persona): name/kind, `last_updated`, the
  `source_roots`/`sources` array (with tier, status, fetched, license), and a `pending`
  list seeded with "corpus not yet authored".
- `library/<x>/raw_src/INDEX.md` — manifest stub (file → source URL → version → tier →
  license table, empty) following `library/scrum/raw_src/INDEX.md`.

### 3. Instantiate `agents/<x>-expert.md` from the template
Copy the chosen template and **rewrite it for the new expert** — don't leave Boris/Agile
content behind:
- **Frontmatter `description:`** — trigger-optimized (run §8); embed the NOT-boundary(ies)
  so the harness routes correctly. `tools:` per the template (persona/docs both use
  `WebSearch, WebFetch, Read, Write, Glob, Grep, Bash`).
- **Body** — fill the two modes (A = advise/answer, B = build/refresh), the **library
  paths** (`library/<x>/<x>.md`, `_meta.json`, `raw_src/`), the **canonical sources**, and
  the hard rules (cite-the-URL, sourced-vs-inferred for persona, route-the-depth for
  umbrella). Keep the house voice: concrete, honest about confidence, no fluff.

### 4. (Optional) Seed the `/ww<x>` skill
If requested (persona-advisor only), copy `skills/wwbd/SKILL.md` to
`skills/ww<x>/SKILL.md` and point it at the new `<x>-expert` agent: rename, rewrite the
`description:` (the accept/reject/explain-visual loop, delegating to `<x>-expert`), and
swap every Boris reference for the new person. Leave the standalone-skill description
*optimization* to `skill-builder` if a richer pass is wanted — this is a working seed.

### 5. Hand corpus authoring to a fan-out (do NOT write prose here)
**If the corpus needs integrity-grade vendored primary sources (raw bytes + SHA256
provenance + verify-vs-raw), delegate the corpus phase to `/vendor-corpus`** instead of
hand-rolling the fetch/hash/gitignore here - that skill owns the integrity protocol in one
place (it expects the `library/<x>/` skeleton this skill just scaffolded to already exist).
Otherwise (a persona/docs corpus that lives-fetches without a vendored-source bar):
launch a `general-purpose` agent (or a small fan-out, one slice per source) to **build the
corpus to the boris/karpathy depth bar**:
- It reads `library/<x>/raw_src/` (if any) and **live-fetches** the canonical sources.
- It **writes the files directly to disk** — `library/<x>/<x>.md` (source-cited, with
  confidence flags for persona), updates `_meta.json` (captured counts / `pending`), and
  fills `raw_src/INDEX.md`. (Keep the payload small per the global rule — return a manifest,
  not the full corpus inline.)
- It returns a **short manifest** (files written, captured-vs-pending), not the prose.
This skill never authors corpus content itself — that judgment work belongs to the fan-out.

### 6. Wire the new expert into the roster
- **.gitignore** — add `!library/<x>/` so the new (curated, tracked) corpus is un-ignored
  alongside the existing `!library/...` lines. Do **not** touch other lines.
- **AGENTS.md** — register the agent under §1 (live-docs experts) or §2 with a one-line
  curated entry; if a `/ww<x>` skill was seeded, add it to §3 (Persona advisors). Match the
  terse house style; use the final description.
- Run `hooks/audit-capabilities.ps1 -Fix` to sync the shared **CLAUDE.md Capabilities
  block** from the global canonical into the template + project CLAUDE.md files.

### 7. Validate
- The audit's **Check 0** (frontmatter validity + description hygiene) must pass — a bad
  `description:` silently **de-registers** the agent. Resolve anything it flags.
- Confirm the audit ends with `RESULT: capability surfaces are consistent.`
- **Mandatory grounding audit.** Spawn `agent-eval-strategist` via **Task** (read
  `$GROK_HOME/agents/agent-eval-strategist.md` first) to
  audit the fan-out's corpus for hallucinated / miscited sources and to confirm the new
  `description:` discriminates from neighbouring experts (no silent overlap). Fix anything
  it flags before reporting.
- If **persona-type** and the user opted in, append the new corpus to the `$corpora` list
  in `agents/tools/refresh_persona_corpora.ps1` (so the weekly currency-watch covers it).

### 8. Optimize the agent description (desc_eval)
Before finalizing the agent (and any `/ww<x>` skill) description:
- Draft **3 candidate `description:` lines** (include the brief's original).
- Judge each candidate × the brief's should-trigger / should-NOT-trigger prompts **on the
  description text alone** (the way the harness selects). Feed variants + prompts +
  judgments to `agents/tools/desc_eval.py`; keep the highest-accuracy candidate (ties → the
  shorter / more specific one). Write the winner into the agent file. Report the matrix.

### 9. Report
- Paths created (`agents/<x>-expert.md`, `library/<x>/...`, optional `skills/ww<x>/`).
- Template used; the final descriptions + their eval scores.
- Wiring done (.gitignore, AGENTS.md, CLAUDE.md block) and the audit result.
- The fan-out's corpus manifest (captured vs pending).
- **Restart reminder:** the new agent/skill is not invocable until a session restart
  (subagents load at session start); then smoke-test an UNPROMPTED request to confirm
  auto-delegation fires. If the global config changed, run `/backup-config`.

## Rules
- **Assemble, don't author.** This skill scaffolds and sequences; corpus prose is the
  fan-out's job, the `/ww<x>` skill spec-optimization is `skill-builder`'s, and the
  whether-to-build call is `roster-steward`'s / the human's.
- **Never clobber.** Stop and ask before overwriting any existing agent, library, or skill.
- **Ground the templates fully.** No leftover Boris/Agile text in the new agent — rewrite
  every mode, path, source, and boundary.
- **ASCII-safe, UTF-8 files, no AI/Claude attribution** anywhere (frontmatter, body, files).
- **Validate Check 0** — a malformed description de-registers the agent silently.
