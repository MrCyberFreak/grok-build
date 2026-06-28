# -*- coding: utf-8 -*-
"""Throwaway offline test of the deterministic postpass (no network/model)."""
import json, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
T = os.path.join(HERE, ".tmp_test")
LIB = os.path.join(T, "lib")
if os.path.isdir(T):
    shutil.rmtree(T)
os.makedirs(LIB)

def w(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)

# minimal _meta.json for the fake library
w(os.path.join(LIB, "_meta.json"), json.dumps({
    "last_updated": "2026-06-20", "last_checked": "2026-06-20",
    "newest_content_date": "2026-06-20", "watch": {"queued_review_count": 0}}))

BODY = ("Claude Code works best when you let the model run a tight verify loop: write a "
        "failing test, let the agent iterate until it passes, then review the diff. The "
        "bottleneck is good ideas and good evals, not typing.")
ECHO = "Home | Subscribe. " + BODY + " Read more on The New Stack."
w(os.path.join(LIB, "src1.txt"), BODY)
w(os.path.join(LIB, "src_echo.txt"), ECHO)

def fwd(p):  # forward-slash absolute path Windows python can open
    return p.replace("\\", "/")

proposals = [
    {  # faithful, tier0 -> QUEUE (auto_lane off)
        "source": {"url": "https://www.anthropic.com/engineering/loops", "author": "",
                   "raw_src_path": fwd(os.path.join(LIB, "src1.txt")), "fetched": "2026-07-01"},
        "target_expert": "claude-code",
        "claims": [{"text": "use a tight verify loop", "confidence_flag": "verbatim",
                    "quote": "let the model run a tight verify loop"}],
        "curation_verdict": {"verdict": "GO", "borderline": True, "margin": 1,
                             "scores": {"novelty": 2, "correctness": 3, "relevance": 3, "durability": 2}},
    },
    {  # HALLUCINATION: quote not in body -> faithfulness fail -> REJECT
        "source": {"url": "https://www.anthropic.com/news/x", "author": "",
                   "raw_src_path": fwd(os.path.join(LIB, "src1.txt")), "fetched": "2026-07-01"},
        "target_expert": "claude-code",
        "claims": [{"text": "disable permission checks", "confidence_flag": "verbatim",
                    "quote": "always disable all permission checks for speed"}],
    },
    {  # ECHO of #1 from a tier1 domain -> novelty fail -> REJECT
        "source": {"url": "https://hamel.dev/notes/echo", "author": "",
                   "raw_src_path": fwd(os.path.join(LIB, "src_echo.txt")), "fetched": "2026-07-01"},
        "target_expert": "claude-code",
        "claims": [{"text": "tight verify loop", "confidence_flag": "verbatim",
                    "quote": "let the model run a tight verify loop"}],
    },
]
w(os.path.join(LIB, "proposals.json"), json.dumps(proposals))

digest = os.path.join(T, "digest.md")
runhealth = os.path.join(T, "_runhealth.jsonl")
decisions_out = os.path.join(T, "decisions.json")

rc = subprocess.run([sys.executable, os.path.join(HERE, "watch_lib.py"), "postpass",
                     "--library-dir", LIB, "--proposals", os.path.join(LIB, "proposals.json"),
                     "--source-tiers", os.path.join(HERE, "source_tiers.json"),
                     "--no-vendor", "--run-id", "2026-07-01-fast", "--today", "2026-07-01",
                     "--digest", digest, "--runhealth", runhealth,
                     "--decisions-out", decisions_out, "--auto-lane", "off"]).returncode

dec = json.load(open(decisions_out, encoding="utf-8"))
got = {d["claims"][0]["quote"][:18] if d.get("claims") else "?": d["decision"] for d in dec}
outcomes = [(d["source"]["url"], d["decision"], d.get("decision_trace")) for d in dec]
seen = open(os.path.join(LIB, "_seen.jsonl"), encoding="utf-8").read().strip().splitlines()
meta = json.load(open(os.path.join(LIB, "_meta.json"), encoding="utf-8"))

print("postpass exit:", rc)
for o in outcomes:
    print("  ", o[1], o[0], "->", o[2])
print("seen rows:", len(seen), "| meta.last_checked:", meta["last_checked"],
      "| queued_count:", meta.get("watch", {}).get("queued_review_count"))
print("digest exists:", os.path.exists(digest), "| runhealth exists:", os.path.exists(runhealth))

want = [d["decision"] for d in dec]
ok = (want == ["QUEUE", "REJECT", "REJECT"] and len(seen) == 3
      and meta["last_checked"] == "2026-07-01"
      and meta.get("watch", {}).get("queued_review_count") == 1)
print("RESULT:", "PASS" if ok else "FAIL")
shutil.rmtree(T)
sys.exit(0 if ok else 1)
