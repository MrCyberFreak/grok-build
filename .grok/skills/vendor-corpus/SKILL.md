---
name: vendor-corpus
description: Vendor primary web/PDF sources into an existing library/<x>/ at integrity grade (raw bytes + SHA256 provenance + verify-vs-raw + pending-not-fabricate), then delegate source-cited prose and a hallucination audit. Triggers on "ground <x>-expert on its sources", "vendor these pages into <library> with checksums", "resolve the pending sources in <library>". NOT for creating a brand-new expert (use scaffold-expert) or the weekly currency refresh of doc-library mirrors (refresh_libraries).
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Task
argument-hint: [library slug + sources, or "resolve pending in <library>"]
---

# vendor-corpus - integrity-grade web-corpus vendoring

Ground (or expand) an **EXISTING** expert's `library/<x>/` by vendoring its primary
web/PDF sources to the user's integrity standard: **raw bytes + SHA256 provenance +
verify-vs-raw + pending-not-fabricate + push-protection-safe gitignore**, then delegate
the source-cited prose and a hallucination audit. Reusable standalone **and** as
`scaffold-expert`'s corpus-phase delegate.

This skill owns the **integrity sequence**, not the judgment work: it never fabricates
source content, and it hands the corpus prose to a `general-purpose` agent and the
hallucination check to `agent-eval-strategist`.

## Inputs (capture from the request; ask only for what's missing)
- **library slug `<x>`** - the existing `library/<x>/` to ground (e.g.
  `data-acquisition-legal-risk-expert`). The matching agent is usually `agents/<x>.md`.
- **sources** - the URLs to vendor, each with a target filename stem and a tier
  (primary-statute / court-opinion / regulator-guidance / site-ToS-robots / docs / ...)
  and a license/usage note.
- **OR "resolve pending in `<library>`"** - no source list; the worklist is the
  library's `_meta.json` `pending[]`.
- **fetch date** - today's date, passed to the helper as `-Fetched`. Never invented.

## Procedure

### 1. Resolve the library - it MUST already exist
- Confirm `library/<x>/` exists. If it does **not**, STOP and hand off to
  `scaffold-expert` - that skill owns NEW-expert / NEW-library creation; this one only
  grounds an existing library. Do not create the library skeleton here.
- If the request is **"resolve pending"**, read `library/<x>/_meta.json` and use its
  `pending[]` array as the worklist (each entry has the URL + the reason it stalled).
- Ensure `library/<x>/raw_src/` exists (create it if the library has no raw_src yet).

### 2. Fetch each source as RAW BYTES (never a lossy summary)
For every source, run the helper script (Windows PowerShell 5.1; invoke via the Bash
tool as `powershell -NoProfile -ExecutionPolicy Bypass -File ...`, matching the house
pattern for local helper scripts - the machine's policy blocks unsigned `-File` runs):

```
powershell -NoProfile -ExecutionPolicy Bypass \
  -File "X:\Grok_Build\.grok\skills\vendor-corpus\scripts\vendor_source.ps1" \
  -Url "<url>" \
  -OutFile "X:\Grok_Build\.grok\library\<x>\raw_src\<stem>.<ext>" \
  -Fetched "<YYYY-MM-DD>"
```
- Extension by kind: HTML page -> `.html`, PDF -> `.pdf`, robots.txt -> `.txt`.
- The script sets `$ProgressPreference='SilentlyContinue'`, sends a browser
  `-UserAgent`, captures the verbatim response body, computes SHA256 + byte count, and
  returns a one-line JSON result. It **does not throw** on a bad fetch.
- It never re-summarizes: the bytes on disk are exactly what the server returned. Do
  **not** substitute a WebFetch summary for the raw bytes.

### 3. Integrity gate (the heart - never fabricate, never vendor a non-source)
Read the helper's JSON `status` for each source:
- **`vendored`** - bytes written; the script already re-read the saved file and
  confirmed the on-disk SHA256 equals the in-memory hash. Record it as a real source.
- **`pending`** - a TLS failure, HTTP error, empty body, **JS app shell**, **bot
  challenge / interstitial**, or **login wall**. The bytes were **NOT** written (a
  non-source is never vendored). Record it in `_meta.json` `pending[]` with the helper's
  `reason` and EXCLUDE it from the corpus.
- **NEVER** hand-write, paraphrase, or "reconstruct" a source that did not fetch
  cleanly, and never point a `[src: ...]` marker at bytes that were not actually saved.
  A missing source is `pending`, not invented.

### 4. Upsert `library/<x>/_meta.json` (valid JSON, ASCII-safe)
Mirror the schema in `library/data-acquisition-legal-risk-expert/_meta.json`:
- top level: `slug`, `last_updated` (the fetch date), `origin` (one line: why/when
  built), `kind`, `tracked: true`.
- `sources[]` - one object per vendored source: `file` (`raw_src/<name>`), `url`,
  `fetched` (the passed-in date, never invented), `sha256`, `bytes`, `tier`, `license`,
  `status: "vendored"`.
- `captured[]` - short bullets of what the corpus now actually covers.
- `pending[]` - one object per excluded/stalled source: `item`, `url`, `reason` (from
  the helper), `status: "pending"`. Preserve any pre-existing pending entries you did
  not resolve.
When **resolving pending**, move each newly-vendored item out of `pending[]` into
`sources[]`; leave the still-stalled ones in `pending[]` with an updated reason.

### 5. Delegate the source-cited corpus prose (do NOT author it here)
Launch a **Task** (`subagent_type: generalPurpose`) to write the corpus, deriving **only**
from the vendored raw files:
- It writes `library/<x>/<x>.md` - source-of-truth prose with an inline
  `[src: <raw_src file> | <URL> | fetched <date>]` marker on every claim, mirroring the
  structure of `library/data-acquisition-legal-risk-expert/data-acquisition-legal-risk-expert.md`.
- It writes / updates `library/<x>/raw_src/INDEX.md` - the manifest table
  (File | Source URL | Fetched | Tier | License/usage note | SHA256 (16) | Bytes |
  Status), one row per source, mirroring that library's `raw_src/INDEX.md`.
- It must NOT introduce facts that are not in the vendored bytes, and must mark any
  unsettled / unfetched point UNVERIFIED rather than asserting it.
- It returns a short manifest (files written, captured-vs-pending), not the full prose
  (keep the subagent payload small per the global rule).

Then **VERIFY the formatted text against the RAW vendored bytes** (not a summary):
spot-check that each `[src: ...]` claim is supported by the bytes in the cited
`raw_src/` file. This is the user's integrity rule - a summary layer can fabricate, so
the check is against the raw original, never against another summary.

### 6. `.gitignore` - un-ignore the library, keep raw HTML local
In `X:\Grok_Build\.grok\.gitignore`:
- Ensure `!library/<x>/` is present (un-ignore this curated, tracked corpus) alongside
  the existing `!library/...` allowlist lines. Add it with a one-line comment if absent.
- Ensure the global rule `library/*/raw_src/*.html` is present (it normally already is)
  so raw HTML page-captures stay **LOCAL** - they carry third-party PUBLIC,
  api-key-shaped strings (Google `AIza...`, Stripe `pk_...`) baked into page JS that
  trip GitHub push-protection. Keep the clean originals (PDFs, robots.txt) and the
  formatted corpus + `_meta.json` (with SHA256 provenance) tracked; the raw `.html`
  stays on disk for the integrity check only.

### 7. Wire / refresh the agent's grounding pointer
In `agents/<x>.md` (the expert this corpus grounds), ensure a
`## Grounding corpus (read this FIRST)` section points at
`library/<x>/<x>.md` + `_meta.json` and tells the agent to cite the corpus's
`[src: ...]` markers and to treat `pending[]` items as UNVERIFIED. Mirror the wording
in `agents/data-acquisition-legal-risk-expert.md`. If the section already exists, just
refresh it; do not duplicate it.

### 8. Hallucination audit (mandatory, before reporting)
Spawn `agent-eval-strategist` via **Task** (read `$GROK_HOME/agents/agent-eval-strategist.md`
first) to audit `library/<x>/<x>.md` against the
vendored `raw_src/` files for **hallucinated or miscited sources** - any `[src: ...]`
marker whose cited file does not support the claim, any citation to a `pending` source,
or any fabricated quote. Fix everything it flags before reporting.

### 9. Report
- Vendored sources (with file, tier, SHA256, bytes) vs pending sources (with reason).
- Files written / edited (`_meta.json`, `<x>.md`, `raw_src/INDEX.md`, `.gitignore`,
  `agents/<x>.md`), all absolute paths.
- The corpus manifest from the delegate and the eval-strategist's verdict.
- Remind the user to run `/backup-config` (the global config repo is the backup
  channel) and note this is a **v1 they should review** before trusting it.

## Rules
- **Integrity sequence, not invention.** Raw bytes + SHA256 + verify-vs-raw on every
  source; a source that does not fetch cleanly is `pending`, never reconstructed.
- **EXISTING library only.** A missing `library/<x>/` -> hand to `scaffold-expert`.
- **Delegate the prose + the audit.** Corpus `.md` is the `general-purpose` agent's
  judgment work; the hallucination check is `agent-eval-strategist`'s.
- **Push-protection safe.** `library/*/raw_src/*.html` stays gitignored; raw HTML never
  leaves the local disk.
- **ASCII-safe output, UTF-8 files, no AI/Claude attribution** anywhere; the user's git
  identity only. Do not `git commit`/`push` - the user runs `/backup-config`.
