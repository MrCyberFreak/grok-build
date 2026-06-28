---
name: watch-review
description: "Triage the library currency-watch review queue once a digest exists: walk each QUEUED candidate in the latest watch digest (include/revise/reject), integrate approved claims into the expert corpus, label every decision into goldset.jsonl, and re-run goldcheck. Use for 'review the watch digest', 'process this week's library-watch queue', 'grow the gold set from the watch candidates'. NOT for running the watch itself (refresh_practice_corpora), vendoring brand-new sources (vendor-corpus), creating a new expert (scaffold-expert), or the doc-mirror refresh (refresh_libraries)."
allowed-tools: Read, Edit, Bash, Glob, Grep, AskQuestion, Skill
argument-hint: "[run-id e.g. 2026-06-27-all] [--library <slug>]"
---

# watch-review - the human review loop after a currency-watch run

The library currency-watch runs on a cadence and drops a review digest. This skill is
the **human loop after it**: walk the latest digest one QUEUED candidate at a time,
capture each INCLUDE/REVISE/REJECT verdict, deterministically integrate approved
verbatim-faithful claims into the expert corpus, turn **every** decision into a labeled
`goldset.jsonl` example (so calibration stops rotting), then re-run `goldcheck` to prove
the gates still pass.

This skill owns the **review + label loop**, not the watch run and not new-source
vendoring. It never fabricates candidates and never hand-edits the gold set: the
deterministic outcome (`expected_gate`) is computed by the `goldadd` helper.

## Honesty caveat - read before triaging
No **live** digest has ever been produced yet (only dry-runs). This procedure was
verified against the engine (`watch_lib.py`, selftest + goldcheck pass) and the runner
(`refresh_practice_corpora.ps1`), **not** against a live artifact. So be defensive:
**verify the digest and decisions files exist and have the expected shape before you
triage**, and if a field is missing from a decision record, **surface that to the user
rather than guessing** a value.

All paths are under `$GROK_HOME` (`X:\Grok_Build\.grok`, referred to below as
`<cfg>`). The gold-set helper runs from `<cfg>\agents\tools\watch\` with `PYTHONUTF8=1`.

## Inputs (capture from the request)
- **run-id** (optional) - `<YYYY-MM-DD>-<tier>`, tier in {`fast`, `all`} (e.g.
  `2026-06-27-all`). Defaults to the **newest** `digest-*.md`.
- **--library `<slug>`** (optional) - review only that one library's queue.

## Procedure

### 1. Locate the digest + decisions; stop cleanly if there is nothing to review
- Digest (human-readable): `<cfg>\agents\tools\logs\watch\digest-<runId>.md`. If no
  run-id was passed, pick the **newest** `digest-*.md` in that directory (Glob, sort by
  name/date).
- If **no `digest-*.md` exists**, STOP and tell the user to run the watch first
  (`agents\tools\refresh_practice_corpora.ps1`) - do **NOT** fabricate candidates.
- Read the digest for human context only. The **structured data you act on** is the
  per-library decisions file: `<cfg>\library\<x>\.watch\decisions-<runId>.json` - a JSON
  array. With `--library <slug>`, read only that library's file; otherwise read every
  library's decisions file for this run-id (Glob `library\*\.watch\decisions-<runId>.json`).
- Each array element has this shape (parse it, do not parse the markdown):
  ```
  { "target_expert": str,
    "decision": "QUEUE" | "AUTO_INTEGRATE" | "REJECT",
    "decision_trace": str,
    "source": { "url","tier","author","raw_src_path","date","fetched" },
    "panel":  { "verdict","margin","borderline","scores","strongest_dissent" },
    "claims": [ { "text","confidence_flag","quote","quote_present" } ],
    "gate":   { "relevance_pass","contradiction" } }
  ```
  `confidence_flag` is one of `verbatim` | `secondary` | `inference`; `quote_present` is
  a bool. **Review the items with `decision == "QUEUE"`** (you may skim
  `AUTO_INTEGRATE` items so the user can spot-check them).
- **Shape check before triaging.** If a decisions file is missing, is not a JSON array,
  or a QUEUE item is missing a field you need (`source.url`, `source.raw_src_path`,
  `claims`, `panel.verdict`), report exactly what is missing and which file - do not
  invent the value.

### 2. Triage each QUEUED candidate one at a time
For each `QUEUE` item, present to the user, compactly:
- the **source** url + tier (+ author/date if present),
- the **verbatim quote(s)** from `claims[].quote` (and each `confidence_flag` /
  `quote_present`),
- the **panel/council verdict** (`panel.verdict`, `margin`, `borderline`,
  `strongest_dissent`),
- the **route reason** (`decision_trace`) and the gate result (`gate`).

Then ask the verdict with **AskQuestion** (multiple choice):
- **INCLUDE** - integrate the claim as-is.
- **REVISE** - integrate, but the user supplies corrected/trimmed wording (free-text).
- **REJECT** - do not integrate.

Always allow a free-text path so the user can give a one-line **rationale** (you will
store it as the gold example's `reason`). Process candidates one at a time; do not batch
the decisions into a single prompt.

### 3. On INCLUDE / REVISE: integrate the claim into the corpus (with provenance)
- Append the verbatim-faithful claim to the expert corpus `<cfg>\library\<x>\<x>.md`
  (where `<x>` = `target_expert`), preserving its wording (for REVISE, the user's
  corrected wording). Attach provenance inline: the source **url + date**, mirroring how
  that corpus already cites sources (e.g. a `[src: <url> | fetched <date>]`-style
  marker).
- For a REVISE, integrate the user's corrected text, not the raw claim.
- **If the candidate is a brand-new primary source that needs integrity-grade vendoring**
  (raw bytes + SHA256 provenance, not just a quote), do **NOT** reinvent that here -
  delegate to the **vendor-corpus** skill (Skill tool) and let it own the raw-bytes +
  checksum sequence.

### 4. For EVERY decision (include AND revise AND reject): append a labeled gold example
This is the point of the skill - **no decision is skipped**, including rejects. Build one
item JSON object per decision and append it via `goldadd`. Pull `verbatim_quote` from the
candidate's `claims[].quote` and `source_text` from the saved source body at
`source.raw_src_path` (under `<cfg>\library\<x>\.watch\src\<slug>.txt`) so `goldcheck`
can replay offline.

Item JSON fields you supply:
- `human_label` - the user's choice: `INCLUDE` | `REVISE` | `REJECT`.
- `trap_type` - the nature of the candidate (NOT the human label):
  - `none` - a clean, genuine include.
  - `off_topic` / `poison` - a credible-but-wrong reject the gates cannot catch (only
    panel/human catches it).
  - `hallucination` / `pending_cite` / `echo` / `lead_only` - cases the deterministic
    gate itself catches (quote not in source / JS-shell or bot-wall source / verbatim
    repost / Tier-3 social post).
- `target_expert`, `source_url`, `author` - from the decision record's `source`.
- `verbatim_quote` - the exact substring that must exist in `source_text`
  (from `claims[].quote`).
- `source_text` - the INLINE source body read from `source.raw_src_path`.
- `reason` - the user's one-line rationale.

**Do NOT hand-set `expected_gate`.** `goldadd` computes it deterministically; if you pass
one that disagrees with the gates it exits 2 and writes nothing (unless `--force`).
`candidate_id` is auto-assigned (`gold-NNN`, max+1) when omitted.

Write the object to a temp file and call (from `<cfg>\agents\tools\watch\`,
`PYTHONUTF8=1` - `--item-file` is preferred for long `source_text`):

```
python watch_lib.py goldadd --goldset goldset.jsonl --source-tiers source_tiers.json --item-file <item.json>
```

(`--item-json '<json>'`, `--item-stdin`, or the individual `--trap-type/--human-label/...`
flags also work.) If `goldadd` exits non-zero, report its message and the offending item;
do not `--force` past a real gate disagreement without the user's say-so.

### 5. Re-run goldcheck - the gate; refuse to report "done" on failure
After all decisions are appended:

```
python watch_lib.py goldcheck --goldset goldset.jsonl --source-tiers source_tiers.json
```

`goldcheck` replays every gold item through the deterministic gates and **exits 1 on any
mismatch**. If it **FAILS**, the skill **REFUSES to report success** - surface the exact
failing item(s) and the command output, and stop. Report PASS only when goldcheck passes
(exit 0).

### 6. Report + offer to back up
Report: the digest/run-id reviewed, per-candidate verdict (INCLUDE/REVISE/REJECT),
corpus files edited (absolute paths), how many gold examples were appended (with their
`gold-NNN` ids), and the goldcheck PASS/FAIL result.

Then **offer to run `/backup-config`** to persist the corpus + gold-set changes to the
global config repo. Note that `_meta.json` freshness/date bumps are already handled by
the watch's postpass - this skill does **not** redo them.

## Rules
- **Verify before you triage.** Files must exist and match the shape above; a missing
  field is surfaced, never guessed (no live digest has been produced yet).
- **Every decision becomes a labeled example.** Includes, revises, AND rejects - that is
  how calibration stays honest.
- **Never hand-set `expected_gate`.** `goldadd` computes it; a disagreement is a signal,
  not something to `--force` past silently.
- **goldcheck is the gate.** Exit 1 = not done. Do not claim success on a failed replay.
- **Stay in scope.** Running the watch is `refresh_practice_corpora.ps1`; registering the
  schedule is `register_watch_tasks.ps1`; integrity-grade vendoring of brand-new sources
  is `vendor-corpus`; creating a new expert is `scaffold-expert`; the doc-mirror refresh
  is `refresh_libraries`. This skill is only the review + label loop.
- **ASCII-safe output, UTF-8 files (`PYTHONUTF8=1`), no AI/Claude attribution** anywhere;
  the user's git identity only. Do not commit/push - the user runs `/backup-config`.
