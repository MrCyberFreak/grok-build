#!/usr/bin/env python3
"""desc_eval.py — score skill `description:` candidates for trigger accuracy.

Custom, dependency-free description optimizer used by the skill-builder agent.
The *judging* (does description X trigger on prompt Y?) is done by the agent;
this tool just structures the test set and scores the agent's judgments so the
choice between candidates is deterministic and auditable.

INPUT SCHEMA (JSON):
{
  "variants": ["description A", "description B", ...],
  "prompts": [
    {"text": "user prompt ...", "expected": "trigger"},
    {"text": "user prompt ...", "expected": "no-trigger"}
  ],
  "judgments": [            # judgments[i][j] = did variant i trigger on prompt j?
    [true, false, ...],     # one row per variant, one bool per prompt
    [true, true,  ...]
  ]
}

USAGE:
  python desc_eval.py judged.json        # score and pick a winner
  python desc_eval.py --scaffold spec.json   # emit a matrix of nulls to fill in
  python desc_eval.py --help
"""
import json
import sys


def load(path):
    if path == "-":
        return json.load(sys.stdin)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def scaffold(data):
    """Emit input with a judgments matrix of nulls for the agent to fill."""
    variants = data["variants"]
    prompts = data["prompts"]
    data["judgments"] = [[None] * len(prompts) for _ in variants]
    print(json.dumps(data, indent=2))


def score(data):
    variants = data["variants"]
    prompts = data["prompts"]
    judgments = data.get("judgments")
    if not judgments:
        sys.exit("error: no 'judgments' matrix — run with --scaffold first, then fill it in.")

    want = [p["expected"].strip().lower() == "trigger" for p in prompts]
    results = []
    for i, variant in enumerate(variants):
        row = judgments[i]
        if len(row) != len(prompts):
            sys.exit(f"error: judgments[{i}] has {len(row)} entries, expected {len(prompts)}.")
        if any(v is None for v in row):
            sys.exit(f"error: judgments[{i}] still has unfilled (null) entries.")
        correct = sum(1 for got, exp in zip(row, want) if bool(got) == exp)
        misses = [
            prompts[j]["text"]
            for j, (got, exp) in enumerate(zip(row, want))
            if bool(got) != exp
        ]
        results.append({"variant": variant, "correct": correct, "total": len(prompts), "misses": misses})

    # Winner: most correct; tie-break on shorter description.
    results.sort(key=lambda r: (-r["correct"], len(r["variant"])))

    print(f"Scored {len(variants)} variant(s) over {len(prompts)} prompt(s):\n")
    for r in results:
        pct = 100 * r["correct"] / r["total"]
        print(f"  {r['correct']}/{r['total']} ({pct:.0f}%)  {r['variant']!r}")
        for m in r["misses"]:
            print(f"        miss: {m!r}")
    win = results[0]
    print(f"\nWINNER ({win['correct']}/{win['total']}): {win['variant']!r}")
    if len(results) > 1 and results[1]["correct"] == win["correct"]:
        print("(tie on accuracy — chose shorter description)")


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return
    if argv[0] == "--scaffold":
        if len(argv) < 2:
            sys.exit("usage: python desc_eval.py --scaffold spec.json")
        scaffold(load(argv[1]))
        return
    score(load(argv[0]))


if __name__ == "__main__":
    main(sys.argv[1:])
