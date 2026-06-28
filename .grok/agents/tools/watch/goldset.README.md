# Gold set - the only thing that makes the panel's verdicts *trustworthy*

`goldset.jsonl` is a small, frozen set of human-labeled candidates replayed every
watch run. It does two jobs:

1. **Proves the deterministic gates still work** (run `python watch_lib.py goldcheck
   --goldset goldset.jsonl --source-tiers source_tiers.json`). The planted
   hallucination / pending-cite must be BLOCKED, the echo must be DUP'd, the social
   post must be LEAD_ONLY - 100% or the gate is broken.
2. **Calibrates the panel** once the council runs in the live pipeline: the panel's
   verdict on each item is compared to your `human_label`. If panel-vs-gold
   agreement drops below baseline, the auto-lane HALTS and everything queues.

## How to grow it to 20-40 items (your ~1-2 hr one-time job)

Load it with **hard negatives**, not easy positives. Target mix:

| Slot | trap_type | expected_gate | What it proves |
|---|---|---|---|
| 5-8 clear includes | `none` | `PASS_TO_PANEL` | real, novel, on-topic material reaches the panel |
| 5-8 clear rejects | `off_topic` | `PASS_TO_PANEL` | gate passes; **panel** must reject on relevance |
| 3-5 hallucination traps | `hallucination` | `BLOCKED` | a `verbatim_quote` NOT in `source_text` is blocked |
| 2-3 echo/dup traps | `echo` | `DUP` | a verbatim-body repost (Tier 0/1) is collapsed |
| 1-2 pending-cite traps | `pending_cite` | `BLOCKED` | a JS-shell / bot-wall source is never cited |
| 1-2 poison traps | `poison` | `PASS_TO_PANEL` | credible-but-wrong: only panel/human catches it |
| 1-2 lead-only | `lead_only` | `LEAD_ONLY` | a Tier-3 social post is never a citation |

## Item schema (one JSON object per line)

```json
{
  "candidate_id": "gold-001",
  "trap_type": "none|hallucination|pending_cite|echo|lead_only|off_topic|poison",
  "human_label": "INCLUDE|REVISE|REJECT",
  "expected_gate": "PASS_TO_PANEL|BLOCKED|DUP|LEAD_ONLY|REJECT",
  "target_expert": "claude-code",
  "source_url": "https://...",
  "author": "",
  "verbatim_quote": "exact substring that must exist in source_text",
  "source_text": "INLINE source body so goldcheck runs offline (no fetch)",
  "reason": "why you labeled it this way"
}
```

Notes:
- `expected_gate` is the **deterministic** outcome (what watch_lib's gates do). For a
  poison/off-topic item that is the gate's job to PASS (it can't catch a credible
  falsehood) - `expected_gate` is `PASS_TO_PANEL` even though `human_label` is REJECT.
- `source_text` is inline so the gold set is self-contained and `goldcheck` needs no
  network. For live calibration the pipeline fetches `source_url` for real.
- Tier is read from `source_tiers.json` by domain/author - pick `source_url`/`author`
  to match the tier you intend to test.
- Refresh quarterly; every time you approve/reject a queued item in a real digest,
  consider adding it here as a new labeled example - that is how the loop keeps closing.
