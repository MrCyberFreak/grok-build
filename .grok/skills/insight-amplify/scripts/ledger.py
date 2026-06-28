#!/usr/bin/env python
"""ledger.py - manage the /insight-amplify friction ledger (append-only JSONL).

The friction ledger is the data-engine memory that turns /insight-amplify from a
one-off report into a flywheel: each painful pattern becomes a permanent, recurring,
measurable entry, and the verify loop reports whether a proposed guard got installed
and whether the pattern reappeared. It mirrors the /distill -> forward-acting-rule
pattern pointed at agent friction.

Ledger file (default): X:\\Grok_Build\\Global\\usage-data\\friction-ledger.jsonl
APPEND-ONLY: existing lines are never rewritten. One JSON object per line.

Schema (one object/line), exactly per the spec:
  {
    "id": "destructive-ops-001",
    "first_seen": "2026-06-22",
    "last_seen":  "2026-06-22",
    "pattern": "destructive-first script wiped vetted assets",
    "category": "destructive-ops | overreach | encoding | truncation | other",
    "evidence": ["transcript/session ref or report finding"],
    "proposed_guard": { "home": "hook|rule|memory",
                        "desc": "pre-tool dry-run gate on rm/Remove-Item" },
    "guard_status": "proposed | installed | verified-fires | recurred",
    "recurrences": 0
  }

Subcommands:
  append           append one new entry (dates passed IN; default = today)
  list             print existing entries (JSON array, or --ids for just ids)
  recurrence-check given current friction ids/categories, report which prior guards
                   advanced or recurred

All dates are accepted as explicit --date / --first-seen / --last-seen args for
determinism and testing; they DEFAULT to today only as a convenience.

Usage examples:
  python ledger.py append --id destructive-ops-001 \
      --pattern "destructive-first script wiped vetted assets" \
      --category destructive-ops \
      --evidence "report:2026-06-22 build_seed.py finding" \
      --guard-home hook \
      --guard-desc "pre-tool dry-run gate on rm/Remove-Item" \
      --date 2026-06-22
  python ledger.py list
  python ledger.py list --ids
  python ledger.py recurrence-check --id destructive-ops-001 --category overreach
"""
import argparse
import datetime
import json
import os
import sys

DEFAULT_LEDGER = os.path.join(
    os.environ.get("GROK_HOME") or r"X:\Grok_Build\.grok",
    "usage-data", "friction-ledger.jsonl",
)
VALID_CATEGORIES = ("destructive-ops", "overreach", "encoding", "truncation", "other")
VALID_HOMES = ("hook", "rule", "memory")
VALID_STATUSES = ("proposed", "installed", "verified-fires", "recurred")


def today():
    return datetime.date.today().isoformat()


def ascii_safe(s):
    """Keep console + file output cp1252-safe."""
    if s is None:
        return ""
    return str(s).encode("ascii", "replace").decode("ascii")


def load_entries(path):
    """Read all ledger lines into a list of dicts. Missing file = empty ledger.

    Malformed lines are skipped with a stderr note rather than crashing - the
    ledger is precious, so we never let one bad line block a read.
    """
    entries = []
    if not os.path.isfile(path):
        return entries
    try:
        with open(path, encoding="utf-8") as f:
            for n, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except ValueError:
                    sys.stderr.write("  WARN  skipped malformed ledger line %d\n" % n)
    except OSError as e:
        sys.stderr.write("  WARN  could not read ledger: %s\n" % ascii_safe(e))
    return entries


def append_entry(path, entry):
    """Append one JSON object as a new line. Creates the file/dir if needed.

    APPEND-ONLY: opens in 'a' mode; existing lines are never touched. Ensures the
    file ends with a newline before writing so we never join two records.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # guarantee a trailing newline on the existing file
    if os.path.isfile(path) and os.path.getsize(path) > 0:
        with open(path, "rb") as f:
            f.seek(-1, os.SEEK_END)
            last = f.read(1)
        if last not in (b"\n", b"\r"):
            with open(path, "a", encoding="utf-8") as f:
                f.write("\n")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=True) + "\n")


def cmd_append(args):
    path = args.ledger
    existing = load_entries(path)
    existing_ids = {e.get("id") for e in existing}
    if args.id in existing_ids:
        sys.stderr.write(
            "error: id %r already in the ledger (append-only; this would duplicate it).\n"
            "       If the pattern recurred, record that via recurrence-check / a new "
            "status entry, not a re-append of the same id.\n" % args.id
        )
        return 2

    first_seen = args.first_seen or args.date or today()
    last_seen = args.last_seen or args.date or today()
    entry = {
        "id": ascii_safe(args.id),
        "first_seen": ascii_safe(first_seen),
        "last_seen": ascii_safe(last_seen),
        "pattern": ascii_safe(args.pattern),
        "category": ascii_safe(args.category),
        "evidence": [ascii_safe(e) for e in (args.evidence or [])],
        "proposed_guard": {
            "home": ascii_safe(args.guard_home),
            "desc": ascii_safe(args.guard_desc),
        },
        "guard_status": ascii_safe(args.guard_status),
        "recurrences": int(args.recurrences),
    }
    append_entry(path, entry)
    sys.stdout.write("appended: %s\n" % entry["id"])
    return 0


def cmd_list(args):
    entries = load_entries(args.ledger)
    if args.ids:
        for e in entries:
            sys.stdout.write(ascii_safe(e.get("id", "")) + "\n")
        return 0
    sys.stdout.write(json.dumps(entries, indent=2, ensure_ascii=True) + "\n")
    return 0


def cmd_recurrence_check(args):
    """Given the CURRENT run's friction ids + categories, report prior-guard status.

    For each prior ledger entry, say whether a guard it proposed still appears as
    current friction (by id or category) -> a candidate RECURRENCE (the pattern came
    back), or whether the proposed guard advanced (installed / verified-fires). This
    is the verify-loop signal: did the guard fire, and did the failure mode recur.
    """
    entries = load_entries(args.ledger)
    current_ids = set(args.id or [])
    current_cats = set(args.category or [])

    report = {
        "ledger": args.ledger,
        "ledger_entries": len(entries),
        "current_ids": sorted(current_ids),
        "current_categories": sorted(current_cats),
        "advancing": [],   # guard_status moved off "proposed" (installed/verified)
        "recurred": [],    # pattern still present in this run's friction
        "open_proposed": [],  # proposed before, not advanced, not currently recurring
    }
    for e in entries:
        eid = e.get("id", "")
        cat = e.get("category", "")
        status = e.get("guard_status", "proposed")
        recurs = int(e.get("recurrences", 0) or 0)
        still_present = (eid in current_ids) or (cat in current_cats)
        row = {
            "id": eid,
            "category": cat,
            "guard_status": status,
            "recurrences": recurs,
            "proposed_guard": e.get("proposed_guard", {}),
        }
        if still_present:
            report["recurred"].append(row)
        elif status in ("installed", "verified-fires"):
            report["advancing"].append(row)
        elif status == "proposed":
            report["open_proposed"].append(row)
        elif status == "recurred":
            report["recurred"].append(row)

    sys.stdout.write(json.dumps(report, indent=2, ensure_ascii=True) + "\n")
    return 0


def build_parser():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ledger", default=DEFAULT_LEDGER,
                   help="path to the friction-ledger.jsonl (default: usage-data/friction-ledger.jsonl)")
    sub = p.add_subparsers(dest="cmd", required=True)

    ap = sub.add_parser("append", help="append one new friction entry (append-only)")
    ap.add_argument("--id", required=True, help="stable id, e.g. destructive-ops-001")
    ap.add_argument("--pattern", required=True, help="one-line description of the friction pattern")
    ap.add_argument("--category", required=True, choices=VALID_CATEGORIES)
    ap.add_argument("--evidence", action="append", default=[],
                    help="a transcript/session ref or report finding (repeatable)")
    ap.add_argument("--guard-home", dest="guard_home", required=True, choices=VALID_HOMES,
                    help="most-enforcing home for the proposed guard")
    ap.add_argument("--guard-desc", dest="guard_desc", required=True,
                    help="what the guard does, e.g. 'pre-tool dry-run gate on rm/Remove-Item'")
    ap.add_argument("--guard-status", dest="guard_status", default="proposed", choices=VALID_STATUSES)
    ap.add_argument("--recurrences", type=int, default=0)
    ap.add_argument("--date", default=None, help="explicit date for both seen-fields (default: today)")
    ap.add_argument("--first-seen", dest="first_seen", default=None)
    ap.add_argument("--last-seen", dest="last_seen", default=None)
    ap.set_defaults(func=cmd_append)

    lp = sub.add_parser("list", help="print existing entries")
    lp.add_argument("--ids", action="store_true", help="print only the ids, one per line")
    lp.set_defaults(func=cmd_list)

    rp = sub.add_parser("recurrence-check",
                        help="report which prior guards advanced or recurred vs this run's friction")
    rp.add_argument("--id", action="append", default=[],
                    help="a friction id present in THIS run (repeatable)")
    rp.add_argument("--category", action="append", default=[],
                    help="a friction category present in THIS run (repeatable)")
    rp.set_defaults(func=cmd_recurrence_check)
    return p


def main(argv):
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        # argparse exits with 2 on bad args; pass it through cleanly
        return e.code if isinstance(e.code, int) else 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
