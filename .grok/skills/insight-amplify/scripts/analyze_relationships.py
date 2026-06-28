#!/usr/bin/env python
"""analyze_relationships.py - the ecosystem graph for /insight-amplify.

The user asked the amplifier to "evaluate the relationship between agents, skills,
experts, libraries - everything." This script builds that graph DETERMINISTICALLY by
joining three cheap, precise sources:
  - the config inventory      (gather_state.py output)   -> what exists
  - the usage rollup          (aggregate_usage.py output) -> what is actually invoked
  - the on-disk agent/skill/library files + the CLAUDE.md "Capabilities" block

It emits nodes + edges + a set of HARD, unambiguous flags:
  - libraryless_experts : an agent references library/<x>/ that does not exist, or is a
                          docs-backed/persona expert with no matching corpus
  - orphan_libraries    : a library/<x>/ corpus with no agent that uses it
  - dead_agents/skills  : exist on disk but never invoked in any transcript (usage == 0)
  - doc_drift           : on disk but undocumented in CLAUDE.md, or documented but missing
  - skill_agent_edges   : which skills invoke which agents (and which skills invoke none)
  - overlap_candidates  : agent pairs with high description-keyword overlap (HINTS only)

Judgment (is a dead agent worth keeping? is an overlap real redundancy?) is deliberately
left to the swarm (roster-steward / skill-scout). This script only supplies the graph and
the flags so those judges argue from facts, not recollection.

Usage:
  python analyze_relationships.py --inventory inv.json --usage usage.json
         [--config-dir DIR] [--pretty]
"""
import argparse
import glob
import json
import os
import re
import sys
from collections import defaultdict

DEFAULT_CONFIG_DIR = os.environ.get("GROK_HOME") or r"X:\Grok_Build\.grok"
LIBRARY_ROOT = os.environ.get("CLAUDE_LIBRARY_ROOT") or r"X:\Grok_Build\.grok\library"

LIBRARY_REF_RE = re.compile(r"library/([A-Za-z0-9_.-]+)/")
AGENT_SUFFIXES = ("-expert", "-engineer", "-strategist", "-critic", "-architect",
                  "-validator", "-steward", "-closer", "-analyst", "-growth",
                  "-sponsorship", "-income", "-compliance", "-monetization")
BACKTICK_RE = re.compile(r"`([A-Za-z0-9:_/-]+)`")
DOCS_BACKED_HINTS = ("library/", "offline-library", "docs-backed", "corpus",
                     "live-docs", "persona", "source-cited", "grounded in")
STOPWORDS = set("""a an the and or for of to in on with without not use used using when
whenever proactively into your you it its is are be this that these those via use uses
NOT for x y do does doing how what which their them they other others any all only also
claude code agent agents skill skills expert experts user request requests consult
whenever named matching live docs reads first falls back grounds claims source date url
prefer most specific delegate handle handling per about over across new ned""".split())


def read_text(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return ""


def read_json(path):
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


def list_library_dirs(config_dir):
    for base in (os.path.join(config_dir, "library"), LIBRARY_ROOT):
        if os.path.isdir(base):
            return sorted(d for d in os.listdir(base)
                          if os.path.isdir(os.path.join(base, d)))
    return []


def name_to_lib_candidates(name):
    """Plausible library dir names for an agent (e.g. boris-expert -> boris)."""
    cands = {name}
    for suf in AGENT_SUFFIXES:
        if name.endswith(suf):
            cands.add(name[: -len(suf)])
    return cands


def tokenize(text):
    toks = re.findall(r"[a-z][a-z0-9-]{3,}", (text or "").lower())
    return {t for t in toks if t not in STOPWORDS}


def jaccard(a, b):
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def build(config_dir, inventory, usage):
    agents = inventory.get("agents", [])
    skills = inventory.get("skills", [])
    plugin_skills = inventory.get("plugin_skills", [])
    commands = inventory.get("commands", [])

    lib_dirs = set(list_library_dirs(config_dir))
    cap_usage = usage.get("capability_usage", {}) if usage else {}
    agent_usage = cap_usage.get("agents", {})
    skill_usage = cap_usage.get("skills", {})
    command_usage = cap_usage.get("commands", {})

    def skill_liveness(name):
        """A skill counts as used if invoked via the Skill tool OR typed as /name."""
        s = skill_usage.get(name, {})
        c = command_usage.get(name, {})
        return {"occurrences": s.get("occurrences", 0) + c.get("occurrences", 0),
                "sessions": max(s.get("sessions", 0), c.get("sessions", 0))}

    agent_names = [a["name"] for a in agents]
    agent_name_set = set(agent_names)
    skill_names = [s["name"] for s in skills]

    # --- agent <-> library -------------------------------------------------
    agent_records = []
    libs_with_agent = set()
    libraryless = []
    agent_tokens = {}
    for a in agents:
        name = a["name"]
        body = read_text(os.path.join(config_dir, "agents", name + ".md"))
        desc = a.get("description", "")
        refs = set(LIBRARY_REF_RE.findall(body))
        cands = name_to_lib_candidates(name)
        matched = sorted((refs & lib_dirs) | (cands & lib_dirs))
        broken_refs = sorted(refs - lib_dirs)   # claims a library that is not on disk
        for lib in matched:
            libs_with_agent.add(lib)
        looks_docs_backed = any(h in body.lower() or h in desc.lower()
                                for h in DOCS_BACKED_HINTS)
        used = agent_usage.get(name, {})
        rec = {
            "name": name,
            "library": matched[0] if matched else None,
            "library_refs": sorted(refs),
            "broken_library_refs": broken_refs,
            "looks_docs_backed": looks_docs_backed,
            "invocations": used.get("occurrences", 0),
            "sessions_used": used.get("sessions", 0),
        }
        agent_records.append(rec)
        agent_tokens[name] = tokenize(desc)
        if broken_refs:
            libraryless.append({
                "agent": name,
                "broken_refs": broken_refs,
                "reason": "references library/" + "/, library/".join(broken_refs)
                          + "/ which is not on disk",
            })

    # soft hint (judgment for the swarm): reads docs-backed/persona but has no corpus
    docs_backed_no_corpus = sorted(
        r["name"] for r in agent_records
        if r["looks_docs_backed"] and not r["library"])
    orphan_libraries = sorted(lib_dirs - libs_with_agent)

    # --- skill -> agent / skill edges --------------------------------------
    skill_edges = []
    for s in skills:
        name = s["name"]
        body = read_text(os.path.join(config_dir, "skills", name, "SKILL.md")).lower()
        invokes_agents = sorted({an for an in agent_name_set if an.lower() in body})
        invokes_skills = sorted({sn for sn in skill_names
                                 if sn != name and re.search(r"\b" + re.escape(sn.lower()) + r"\b", body)})
        live = skill_liveness(name)
        skill_edges.append({
            "skill": name,
            "invokes_agents": invokes_agents,
            "invokes_skills": invokes_skills,
            "invocations": live["occurrences"],
            "sessions_used": live["sessions"],
        })

    # --- dead (exists, never invoked) --------------------------------------
    builtin_agents = {"general-purpose", "generalPurpose", "Explore", "explore",
                      "Plan", "plan", "code-reviewer", "claude",
                      "statusline-setup", "claude-code-guide"}
    dead_agents = sorted(r["name"] for r in agent_records
                         if r["invocations"] == 0 and r["name"] not in builtin_agents)
    dead_skills = sorted(e["skill"] for e in skill_edges if e["invocations"] == 0)

    # --- doc drift vs the AGENTS.md / CAPABILITIES.md block ------------------
    cap_text = ""
    for name in ("CAPABILITIES.md", "AGENTS.md", "CLAUDE.md"):
        cap_text += read_text(os.path.join(config_dir, name)) + "\n"
    documented = set()
    m = re.search(r"(?ims)^##\s*Capabilities.*", cap_text)
    cap_block = m.group(0) if m else cap_text
    for tok in BACKTICK_RE.findall(cap_block):
        documented.add(tok)
    on_disk = agent_name_set | set(skill_names)
    undocumented = sorted(n for n in on_disk if n not in documented)
    # only agent-shaped names can be "missing" - built-in/plugin skills are
    # legitimately documented without a file under skills/.
    documented_missing = sorted(
        d for d in documented
        if d.endswith(AGENT_SUFFIXES) and d not in on_disk)

    # --- overlap candidates (HINTS only) -----------------------------------
    overlap = []
    names = [r["name"] for r in agent_records]
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            sc = jaccard(agent_tokens[names[i]], agent_tokens[names[j]])
            if sc >= 0.18:
                overlap.append({"a": names[i], "b": names[j], "score": round(sc, 3)})
    overlap.sort(key=lambda x: x["score"], reverse=True)
    overlap = overlap[:15]

    return {
        "config_dir": config_dir,
        "counts": {
            "agents": len(agents),
            "user_skills": len(skills),
            "plugin_skills": len(plugin_skills),
            "commands": len(commands),
            "libraries": len(lib_dirs),
            "agents_with_library": len([r for r in agent_records if r["library"]]),
            "agents_ever_invoked": len([r for r in agent_records if r["invocations"] > 0]),
            "skills_ever_invoked": len([e for e in skill_edges if e["invocations"] > 0]),
        },
        "agents": sorted(agent_records, key=lambda r: r["invocations"], reverse=True),
        "skill_agent_edges": skill_edges,
        "flags": {
            "libraryless_experts": libraryless,
            "docs_backed_no_corpus": docs_backed_no_corpus,
            "orphan_libraries": orphan_libraries,
            "dead_agents": dead_agents,
            "dead_skills": dead_skills,
            "undocumented_on_disk": undocumented,
            "documented_but_missing": documented_missing,
            "overlap_candidates": overlap,
            "skills_invoking_no_agent": sorted(e["skill"] for e in skill_edges
                                               if not e["invokes_agents"]),
        },
    }


def main(argv):
    p = argparse.ArgumentParser(description="Ecosystem relationship graph for /insight-amplify.")
    p.add_argument("--inventory", required=True, help="gather_state.py JSON output")
    p.add_argument("--usage", required=True, help="aggregate_usage.py JSON output")
    p.add_argument("--config-dir", default=DEFAULT_CONFIG_DIR)
    p.add_argument("--pretty", action="store_true")
    args = p.parse_args(argv)

    inventory = read_json(args.inventory)
    usage = read_json(args.usage)
    if inventory is None:
        sys.stderr.write("error: could not read inventory %r\n" % args.inventory)
        return 2
    if usage is None:
        sys.stderr.write("error: could not read usage %r\n" % args.usage)
        return 2

    out = build(args.config_dir, inventory, usage)
    text = json.dumps(out, indent=2 if args.pretty else None, ensure_ascii=True)
    sys.stdout.write(text + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
