#!/usr/bin/env python3
"""
Verification loop for the Grok Chat History UI.

Run this to check:
- data.json integrity
- Number of conversations and messages
- Basic simulation of what select would do
- File presence for assets referenced
"""

import json
from pathlib import Path
import sys

UI_DIR = Path(__file__).parent / "ui"
DATA_FILE = UI_DIR / "data.json"
INDEX_FILE = UI_DIR / "index.html"

def main():
    print("=== Grok UI Verification Loop ===")
    errors = []
    warnings = []

    # 1. Check files exist
    if not DATA_FILE.exists():
        errors.append("data.json missing")
        print("FAIL: data.json not found")
        sys.exit(1)
    if not INDEX_FILE.exists():
        errors.append("index.html missing")

    print(f"UI dir: {UI_DIR}")
    print(f"data.json size: {DATA_FILE.stat().st_size / 1024:.1f} KB")

    # 2. Load and validate data
    try:
        with open(DATA_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        errors.append(f"Failed to parse data.json: {e}")
        print("FAIL:", e)
        sys.exit(1)

    print("Top keys:", list(data.keys()))

    convs = data.get("conversations", [])
    print(f"Conversations: {len(convs)}")

    if not convs:
        errors.append("No conversations in data")
    else:
        c0 = convs[0]
        print(f"  Sample title: {c0.get('title')}")
        msgs = c0.get("messages", [])
        print(f"  Sample messages: {len(msgs)}")
        if msgs:
            print(f"  First msg role: {msgs[0].get('role')}")
            print(f"  First msg preview: {msgs[0].get('content','')[:60]!r}")

    # Check every conv has messages array
    bad_convs = [c for c in convs if not isinstance(c.get("messages"), list)]
    if bad_convs:
        errors.append(f"{len(bad_convs)} conversations missing 'messages' list")

    total_msgs = sum(len(c.get("messages", [])) for c in convs)
    print(f"Total messages across all: {total_msgs}")

    # 3. Asset references
    asset_info = data.get("asset_info", {})
    print(f"Assets registered: {len(asset_info)}")

    referenced = set()
    for c in convs:
        for m in c.get("messages", []):
            for att in m.get("attachments", []):
                if isinstance(att, dict) and "id" in att:
                    referenced.add(att["id"])

    missing_assets = [rid for rid in referenced if rid not in asset_info]
    if missing_assets:
        warnings.append(f"{len(missing_assets)} referenced assets have no entry in asset_info")
        print("  Warning: some attachments not in asset_info (expected for generated images)")

    # 4. Check index.html has key UI pieces (simple grep)
    html = INDEX_FILE.read_text(encoding="utf-8")
    checks = [
        ("conversations-list", "#conversations-list" in html),
        ("messages-container", "messages-container" in html),
        ("selectConversation", "function selectConversation" in html),
        ("renderConversations", "function renderConversations" in html),
        ("Verify button", "runUIVerification" in html),
        ("console.log in select", "console.log('selectConversation called" in html),
    ]
    for name, ok in checks:
        status = "OK" if ok else "MISSING"
        print(f"  {name}: {status}")
        if not ok:
            warnings.append(f"UI check failed: {name}")

    # 5. Summary
    print("\n=== Verification Summary ===")
    if errors:
        print("ERRORS:")
        for e in errors:
            print("  -", e)
    if warnings:
        print("WARNINGS:")
        for w in warnings:
            print("  -", w)
    if not errors and not warnings:
        print("All basic checks passed.")

    print("\nNext steps for user:")
    print("  1. Open http://localhost:8765 (or run python launch_viewer.py)")
    print("  2. Press F12 → Console")
    print("  3. Click a conversation in the left list")
    print("  4. Click the 'Verify' button at bottom of left sidebar")
    print("  5. Report the console output here.")

    if errors:
        sys.exit(1)

if __name__ == "__main__":
    main()
