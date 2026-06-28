#!/usr/bin/env python
"""aggregate_usage.py - our OWN number-crunch over the raw /insights data.

The whole point of the revamped /insight-amplify is that it does NOT feed off the
built-in report's pre-chewed conclusions. It reads the SAME raw files /insights reads
and forms its own assessment. This script owns the deterministic, quantitative half of
that: it rolls up the per-session facets + session-meta and scans the raw transcripts
to learn WHICH capabilities (agents/skills/commands) the user actually invokes - the
signal that tells dead-on-disk capabilities apart from live ones.

It reads (all robust to missing files):
  - usage-data/facets/*.json       -> qualitative per-session LLM analysis
  - usage-data/session-meta/*.json -> quantitative per-session metrics
  - <config-dir>/projects/**/*.jsonl -> raw transcripts (capability-invocation scan)

It emits one compact JSON object (ASCII-only; cp1252 console safe) consumed by
analyze_relationships.py, the swarm, and render_report.py. NO judgment here - just
counts, rollups, and the painful-session list. Judgment is the swarm's job.

Usage:
  python aggregate_usage.py [--usage-data DIR] [--config-dir DIR]
                            [--since YYYY-MM-DD] [--max-transcripts N]
                            [--no-transcripts] [--pretty]
"""
import argparse
import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict

DEFAULT_CONFIG_DIR = os.environ.get("GROK_HOME") or r"X:\Grok_Build\.grok"
DEFAULT_USAGE_DATA = os.path.join(DEFAULT_CONFIG_DIR, "usage-data")


def read_json(path):
    """Load a JSON file; return None on any failure (missing/locked/bad)."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError, UnicodeDecodeError):
        return None


def ascii_safe(s):
    if s is None:
        return ""
    s = re.sub(r"\s+", " ", str(s)).strip()
    return s.encode("ascii", "replace").decode("ascii")


def project_label(path):
    """Shorten a full project_path to its leaf folder name for grouping."""
    if not path:
        return "(unknown)"
    p = str(path).replace("\\", "/").rstrip("/")
    return ascii_safe(p.split("/")[-1] or p)


def merge_counter(dst, src):
    """Add a {key: int} dict from a session into a running Counter."""
    if isinstance(src, dict):
        for k, v in src.items():
            try:
                dst[ascii_safe(k)] += int(v)
            except (TypeError, ValueError):
                continue


def load_sessions(usage_data, since):
    """Join facets + session-meta by session id. Returns list of merged dicts."""
    facets = {}
    for fp in glob.glob(os.path.join(usage_data, "facets", "*.json")):
        d = read_json(fp)
        if isinstance(d, dict):
            sid = d.get("session_id") or os.path.splitext(os.path.basename(fp))[0]
            facets[sid] = d
    metas = {}
    for mp in glob.glob(os.path.join(usage_data, "session-meta", "*.json")):
        d = read_json(mp)
        if isinstance(d, dict):
            sid = d.get("session_id") or os.path.splitext(os.path.basename(mp))[0]
            metas[sid] = d
    sessions = []
    for sid in set(facets) | set(metas):
        f = facets.get(sid, {})
        m = metas.get(sid, {})
        start = m.get("start_time", "")
        if since and start and start[:10] < since:
            continue
        sessions.append({"id": sid, "facet": f, "meta": m, "start": start})
    sessions.sort(key=lambda s: s["start"] or "")
    return sessions


def rollup(sessions):
    """Aggregate the merged sessions into histograms + totals + a friction list."""
    tools = Counter()
    languages = Counter()
    outcomes = Counter()
    satisfaction = Counter()
    session_types = Counter()
    friction_types = Counter()
    success_types = Counter()
    helpfulness = Counter()
    error_cats = Counter()
    goal_cats = Counter()
    projects = defaultdict(lambda: {"sessions": 0, "output_tokens": 0,
                                    "outcomes": Counter(), "friction": 0})
    totals = Counter()
    starts = []
    painful = []   # the actual failing sessions, with evidence, for "become one with the data"

    for s in sessions:
        f, m = s["facet"], s["meta"]
        if s["start"]:
            starts.append(s["start"])
        merge_counter(tools, m.get("tool_counts"))
        merge_counter(languages, m.get("languages"))
        merge_counter(error_cats, m.get("tool_error_categories"))
        merge_counter(satisfaction, f.get("user_satisfaction_counts"))
        merge_counter(friction_types, f.get("friction_counts"))
        merge_counter(goal_cats, f.get("goal_categories"))
        if f.get("outcome"):
            outcomes[ascii_safe(f["outcome"])] += 1
        if f.get("session_type"):
            session_types[ascii_safe(f["session_type"])] += 1
        if f.get("primary_success"):
            success_types[ascii_safe(f["primary_success"])] += 1
        if f.get("claude_helpfulness"):
            helpfulness[ascii_safe(f["claude_helpfulness"])] += 1

        for k in ("user_message_count", "assistant_message_count", "input_tokens",
                  "output_tokens", "git_commits", "git_pushes", "lines_added",
                  "lines_removed", "files_modified", "tool_errors",
                  "user_interruptions", "duration_minutes"):
            try:
                totals[k] += int(m.get(k, 0) or 0)
            except (TypeError, ValueError):
                pass
        totals["sessions"] += 1

        proj = project_label(m.get("project_path"))
        projects[proj]["sessions"] += 1
        try:
            projects[proj]["output_tokens"] += int(m.get("output_tokens", 0) or 0)
        except (TypeError, ValueError):
            pass
        if f.get("outcome"):
            projects[proj]["outcomes"][ascii_safe(f["outcome"])] += 1

        # a session is "painful" if it carries any friction signal
        fcount = f.get("friction_counts") or {}
        fsum = sum(int(v) for v in fcount.values()) if isinstance(fcount, dict) else 0
        interrupts = 0
        try:
            interrupts = int(m.get("user_interruptions", 0) or 0)
        except (TypeError, ValueError):
            pass
        if fsum or interrupts or f.get("friction_detail"):
            projects[proj]["friction"] += 1
            painful.append({
                "id": s["id"],
                "project": proj,
                "outcome": ascii_safe(f.get("outcome", "")),
                "friction_score": fsum + interrupts,
                "friction_types": {ascii_safe(k): int(v) for k, v in fcount.items()}
                                  if isinstance(fcount, dict) else {},
                "friction_detail": ascii_safe(f.get("friction_detail", "")),
                "summary": ascii_safe(f.get("brief_summary", "")),
                "first_prompt": ascii_safe(m.get("first_prompt", ""))[:200],
            })

    painful.sort(key=lambda p: p["friction_score"], reverse=True)
    proj_out = {}
    for name, d in sorted(projects.items(), key=lambda kv: kv[1]["sessions"], reverse=True):
        proj_out[name] = {
            "sessions": d["sessions"],
            "output_tokens": d["output_tokens"],
            "friction_sessions": d["friction"],
            "outcomes": dict(d["outcomes"]),
        }

    return {
        "date_range": {"start": (min(starts)[:10] if starts else ""),
                       "end": (max(starts)[:10] if starts else "")},
        "totals": dict(totals),
        "tools": dict(tools.most_common()),
        "languages": dict(languages.most_common()),
        "outcomes": dict(outcomes.most_common()),
        "satisfaction": dict(satisfaction.most_common()),
        "session_types": dict(session_types.most_common()),
        "friction_types": dict(friction_types.most_common()),
        "success_types": dict(success_types.most_common()),
        "helpfulness": dict(helpfulness.most_common()),
        "error_categories": dict(error_cats.most_common()),
        "goal_categories": dict(goal_cats.most_common()),
        "projects": proj_out,
        "painful_sessions": painful,
    }


# --- capability-invocation scan over raw transcripts -------------------------

SUBAGENT_RE = re.compile(r'"subagent_type"\s*:\s*"([^"]+)"')
SKILL_RE = re.compile(r'"skill"\s*:\s*"([^"]+)"')
CMDNAME_RE = re.compile(r"<command-name>\s*/?([A-Za-z0-9:_-]+)")


def scan_transcripts(config_dir, max_transcripts):
    """Single streaming pass per transcript; tally agent/skill/command invocations.

    The signal we want is which capabilities actually get USED, so a dead-on-disk
    agent/skill (exists but never invoked) can be told apart from a live one. We
    count DISTINCT sessions that invoked each capability (a fairer signal than raw
    occurrence count), plus a total-occurrence tally.
    """
    files = []
    # Grok session transcripts
    sessions_root = os.path.join(config_dir, "sessions")
    for pattern in ("**/chat_history.jsonl", "**/events.jsonl", "**/updates.jsonl"):
        files.extend(glob.glob(os.path.join(sessions_root, pattern), recursive=True))
    # Claude-compat project transcripts (if present)
    proj_root = os.path.join(config_dir, "projects")
    files.extend(glob.glob(os.path.join(proj_root, "**", "*.jsonl"), recursive=True))
    files = sorted(set(files))
    if max_transcripts and max_transcripts > 0:
        files = files[-max_transcripts:]   # newest by name is non-deterministic; keep all by default
    agents_sessions = defaultdict(set)
    skills_sessions = defaultdict(set)
    cmds_sessions = defaultdict(set)
    agents_hits = Counter()
    skills_hits = Counter()
    cmds_hits = Counter()
    scanned = 0
    for fp in files:
        sid = os.path.splitext(os.path.basename(fp))[0]
        try:
            with open(fp, encoding="utf-8", errors="replace") as fh:
                blob = fh.read()
        except OSError:
            continue
        # cheap whole-file substring gates before the (costlier) regex findall
        if "subagent_type" in blob:
            for m in SUBAGENT_RE.findall(blob):
                agents_hits[m] += 1
                agents_sessions[m].add(sid)
        if '"skill"' in blob:
            for m in SKILL_RE.findall(blob):
                skills_hits[m] += 1
                skills_sessions[m].add(sid)
        if "<command-name>" in blob:
            for m in CMDNAME_RE.findall(blob):
                cmds_hits[m] += 1
                cmds_sessions[m].add(sid)
        scanned += 1

    def fold(hits, sess):
        return {ascii_safe(k): {"occurrences": hits[k], "sessions": len(sess[k])}
                for k in sorted(hits, key=lambda x: hits[x], reverse=True)}

    return {
        "transcripts_scanned": scanned,
        "agents": fold(agents_hits, agents_sessions),
        "skills": fold(skills_hits, skills_sessions),
        "commands": fold(cmds_hits, cmds_sessions),
    }


def main(argv):
    p = argparse.ArgumentParser(description="Deterministic usage rollup for /insight-amplify.")
    p.add_argument("--usage-data", default=DEFAULT_USAGE_DATA)
    p.add_argument("--config-dir", default=DEFAULT_CONFIG_DIR)
    p.add_argument("--since", default=None, help="only sessions on/after this YYYY-MM-DD")
    p.add_argument("--max-transcripts", type=int, default=0, help="0 = scan all")
    p.add_argument("--no-transcripts", action="store_true",
                   help="skip the (slower) transcript capability scan")
    p.add_argument("--pretty", action="store_true")
    args = p.parse_args(argv)

    sessions = load_sessions(args.usage_data, args.since)
    out = rollup(sessions)
    out["usage_data"] = args.usage_data
    out["since"] = args.since or ""
    if args.no_transcripts:
        out["capability_usage"] = {"transcripts_scanned": 0, "agents": {},
                                   "skills": {}, "commands": {}, "skipped": True}
    else:
        out["capability_usage"] = scan_transcripts(args.config_dir, args.max_transcripts)

    text = json.dumps(out, indent=2 if args.pretty else None, ensure_ascii=True)
    sys.stdout.write(text + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
