#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
_seed_watch_json.py - one-shot (re-runnable) seeder for per-library watch.json.

Writes library/<x>/watch.json for every expert library, encoding the docs-mirror
vs evolving-practice classification, cadence, the owning expert agent, and the
initial watched-source mapping. By default it will NOT overwrite an existing
watch.json (so it never clobbers your later hand-tuning); pass --force to rewrite.

This file is the human-readable record of the initial classification. The watch
runner reads each watch.json at run time; you maintain them by hand thereafter.

  python _seed_watch_json.py --root X:\\Claude_Code\\Global\\library            # dry-run
  python _seed_watch_json.py --root X:\\Claude_Code\\Global\\library --apply
  python _seed_watch_json.py --root ... --apply --force                          # rewrite all
"""

import argparse
import json
import os
import sys
import tempfile

# Each entry: dir -> (agent, klass, cadence, source_ids, extra_sources, topics)
# source_ids reference ids in watchlist.global.json. extra_sources are per-expert
# {url, kind, tier, verified, note}. Tier-3 (lead-only) social handles are listed
# so discovery can FOLLOW them to a real source, never cite them.
DOCS = "docs-mirror"
EVOLVE = "evolving-practice"

# unverified per-expert source helper
def src(url, kind, tier, note):
    return {"url": url, "kind": kind, "tier": tier, "verified": False, "note": note}

LIB = {
    # ---------------- docs-mirror (refresh on docs change; watch = NEW pages only)
    "claude-code": ("claude-code-expert", DOCS, "twice-weekly",
        ["claude-code-docs-changelog", "anthropic-news", "anthropic-engineering"],
        [src("https://code.claude.com/docs/sitemap.xml", "sitemap", 0, "new doc pages only; content currency stays on refresh_libraries.ps1")],
        ["claude-code", "harness", "hooks", "skills", "subagents"]),
    "claude": ("claude-expert", DOCS, "twice-weekly",
        ["anthropic-news", "anthropic-research"],
        [src("https://docs.claude.com/sitemap.xml", "sitemap", 0, "new model/API doc pages only")],
        ["models", "api", "pricing", "tool-use", "caching"]),
    "claude-design": ("claude-design-expert", DOCS, "weekly",
        ["anthropic-news"],
        [src("https://support.claude.com/en/", "html-index", 0, "Claude Design support docs - new pages only")],
        ["claude-design", "canvas", "exports"]),
    "grok": ("grok-expert", DOCS, "weekly", [],
        [src("https://docs.x.ai/docs/changelog", "html-index", 0, "xAI docs changelog - new Grok models ship fast")],
        ["grok", "xai-api", "models"]),
    "grok-build": ("grok-build-expert", DOCS, "weekly", [],
        [src("https://docs.x.ai/docs/grok-build", "html-index", 0, "Grok Build CLI docs - new pages only")],
        ["grok-build", "cli"]),
    "notion": ("notion-expert", DOCS, "weekly", [],
        [src("https://developers.notion.com/changelog", "html-index", 0, "Notion API changelog - new pages only")],
        ["notion", "api", "databases"]),
    "mcp": ("mcp-expert", DOCS, "weekly", [],
        [src("https://modelcontextprotocol.io/sitemap.xml", "sitemap", 0, "MCP spec/docs - new pages + spec revisions")],
        ["mcp", "spec", "sdks"]),
    "obsidian": ("obsidian-expert", DOCS, "weekly", [],
        [src("https://docs.obsidian.md/", "html-index", 0, "Obsidian dev docs - new API pages only")],
        ["obsidian", "plugin-api", "dataview"]),
    "agile": ("agile-expert", DOCS, "weekly", [],
        [src("https://agilemanifesto.org/", "html-index", 1, "Manifesto is frozen; watch for rare official updates only")],
        ["agile", "manifesto", "lean", "xp"]),
    "scrum": ("scrum-expert", DOCS, "weekly", [],
        [src("https://scrumguides.org/", "html-index", 0, "Scrum Guide - watch for a NEW edition (2020 is current)")],
        ["scrum", "scrum-guide"]),
    "sprint": ("sprint-expert", DOCS, "weekly", [],
        [src("https://scrumguides.org/", "html-index", 0, "event definitions frozen; facilitation technique catalogs evolve")],
        ["sprint", "facilitation", "retro"]),
    "kanban": ("kanban-expert", DOCS, "weekly", [],
        [src("https://kanbanguides.org/", "html-index", 0, "ProKanban guide is versioned - watch for a new version")],
        ["kanban", "flow", "wip"]),
    "agile-metrics": ("agile-metrics-expert", DOCS, "weekly", [],
        [src("https://dora.dev/research/", "html-index", 1, "DORA benchmarks change yearly - re-verify thresholds")],
        ["ebm", "dora", "flow-metrics", "forecasting"]),
    "agile-scaling": ("agile-scaling-expert", DOCS, "weekly", [],
        [src("https://scaledagileframework.com/", "html-index", 1, "SAFe/LeSS/DA evolve; Nexus/Scrum@Scale frozen")],
        ["safe", "less", "nexus", "scaling"]),
    "agile-backlog": ("agile-backlog-expert", DOCS, "weekly", [],
        [src("https://www.scrum.org/resources", "html-index", 1, "stable practitioner techniques - new resources only")],
        ["user-stories", "invest", "prioritization"]),

    # ---------------- evolving-practice (continual discovery of NEW credible material)
    "boris": ("boris-expert", EVOLVE, "twice-weekly",
        ["anthropic-engineering", "anthropic-news", "claude-code-docs-changelog", "addyosmani", "simonwillison"],
        [src("https://code.claude.com/docs/en/best-practices", "html-index", 0, "living doc Boris shaped"),
         src("https://x.com/bcherny", "x", 3, "LEAD-ONLY: x.com blocks direct fetch; use a readable mirror, follow to a real source")],
        ["agentic-coding", "harness", "verification-loops", "engineering-taste"]),
    "karpathy": ("karpathy-expert", EVOLVE, "twice-weekly",
        ["karpathy", "anthropic-research", "simonwillison", "eugeneyan", "lilianweng", "hamel", "kaggle-blog"],
        [src("https://x.com/karpathy", "x", 3, "LEAD-ONLY: follow to his blog/talks; never cite the timeline")],
        ["ml", "llm", "agents", "learning", "software-2.0"]),
    "garyvee": ("garyvee-expert", EVOLVE, "weekly", [],
        [src("https://garyvaynerchuk.com/", "html-index", 1, "his essays"),
         src("https://x.com/garyvee", "x", 3, "LEAD-ONLY social"),
         src("https://www.youtube.com/@garyvee", "x", 3, "LEAD-ONLY: DailyVee/keynotes; transcribe, do not cite the page")],
        ["attention", "personal-brand", "content", "entrepreneurship"]),
    "tiktok-platform-monetization": ("tiktok-platform-monetization", EVOLVE, "weekly", [],
        [src("https://newsroom.tiktok.com/", "html-index", 0, "official program/payout changes"),
         src("https://support.tiktok.com/", "html-index", 0, "creator program eligibility/rules")],
        ["creator-rewards", "tiktok-shop", "payouts", "eligibility"]),
    "brand-deals-sponsorship": ("brand-deals-sponsorship", EVOLVE, "weekly", [],
        [src("https://www.ftc.gov/business-guidance/advertising-marketing", "html-index", 0, "FTC disclosure guidance"),
         src("https://www.asa.org.uk/", "html-index", 0, "ASA/CAP disclosure rules (UK)")],
        ["sponsorship-rates", "disclosure", "deal-structures"]),
    "audience-analytics-growth": ("audience-analytics-growth", EVOLVE, "weekly", [],
        [src("https://newsroom.tiktok.com/", "html-index", 0, "algorithm/analytics changes")],
        ["engagement-benchmarks", "audience-pivot", "reactivation"]),
    "creator-legal-compliance": ("creator-legal-compliance", EVOLVE, "weekly", [],
        [src("https://www.ftc.gov/business-guidance/advertising-marketing", "html-index", 0, "FTC ad-disclosure"),
         src("https://support.tiktok.com/en/safety-hc", "html-index", 0, "TikTok policy/copyright/strikes")],
        ["policy", "copyright", "disclosure", "refunds"]),
    "faceless-content-strategy": ("faceless-content-strategy", EVOLVE, "weekly", [],
        [src("https://newsroom.tiktok.com/", "html-index", 0, "format/algorithm shifts")],
        ["faceless-formats", "niche-selection", "audience-pivot"]),
    "digital-products-passive-income": ("digital-products-passive-income", EVOLVE, "weekly", [],
        [src("https://gumroad.com/help", "html-index", 2, "platform fee/feature changes"),
         src("https://stan.store/", "html-index", 2, "platform fee changes")],
        ["digital-products", "platform-fees", "funnel", "unit-economics"]),
    "pool-rating-systems-expert": ("pool-rating-systems-expert", EVOLVE, "weekly", [],
        [src("https://www.fargorate.com/", "html-index", 0, "FargoRate official changes"),
         src("https://playnapa.com/", "html-index", 0, "NAPA CSR/rules changes")],
        ["fargorate", "napa-csr", "apa-sl", "crosswalks"]),
    "data-acquisition-legal-risk-expert": ("data-acquisition-legal-risk-expert", EVOLVE, "weekly", [],
        [src("https://www.ftc.gov/", "html-index", 0, "regulator guidance"),
         src("https://www.law.cornell.edu/uscode/text/18/1030", "html-index", 0, "CFAA primary statute")],
        ["scraping-legality", "cfaa", "robots", "pii-retention"]),
    "indie-product-gtm-strategist": ("indie-product-gtm-strategist", EVOLVE, "weekly", [],
        [src("https://stripe.com/pricing", "html-index", 0, "payment fee schedule - re-verify before quoting"),
         src("https://simonwillison.net/atom/everything/", "atom", 1, "indie launch/dev-tool distribution practice")],
        ["pricing", "packaging", "distribution", "launch"]),
}

README = ("Per-library watch config. class = docs-mirror (refresh on doc change; the "
          "watch only surfaces NEW pages) or evolving-practice (continually discover new "
          "credible material). cadence twice-weekly = also crawled by the fast run. "
          "source_ids reference watchlist.global.json; extra_sources are per-expert. "
          "auto_lane off until calibration is green (then 'tier0' enables the narrow "
          "Tier-0 auto-integrate lane). Human-owned: the watch runner READS this, never "
          "rewrites it. Seeded 2026-06-27 by _seed_watch_json.py.")


def write_atomic(path, obj):
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".tmp_", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(tmp, path)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)

    wrote, skipped, missing = [], [], []
    for d, (agent, klass, cadence, sids, extra, topics) in sorted(LIB.items()):
        libdir = os.path.join(args.root, d)
        if not os.path.isdir(libdir):
            missing.append(d)
            continue
        path = os.path.join(libdir, "watch.json")
        if os.path.exists(path) and not args.force:
            skipped.append(d + " (exists)")
            continue
        obj = {
            "_README": README,
            "library": d,
            "expert_agent": agent,
            "class": klass,
            "cadence": cadence,
            "auto_lane": "off",
            "source_ids": sids,
            "extra_sources": extra,
            "topics": topics,
        }
        if args.apply:
            write_atomic(path, obj)
        wrote.append(d)

    sys.stdout.write("seed watch.json: %d %s, %d skipped, %d missing-dir\n"
                     % (len(wrote), "written" if args.apply else "would-write",
                        len(skipped), len(missing)))
    for w in wrote:
        sys.stdout.write("  + %s  [%s]\n" % (w, LIB[w][1]))
    for s in skipped:
        sys.stdout.write("  . %s\n" % s)
    for m in missing:
        sys.stdout.write("  ? missing dir: %s\n" % m)
    return 0


if __name__ == "__main__":
    sys.exit(main())
