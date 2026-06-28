#!/usr/bin/env python3
"""Analyze the Grok chat backup to understand schema, media refs, and prepare reconstruction."""
import json
import re
from pathlib import Path
from collections import Counter, defaultdict

BASE = Path("raw/chat_backup/ttl/30d/export_data/a7a3aa8e-20d8-49be-983e-a736948648a6")
JSON_PATH = BASE / "prod-grok-backend.json"
ASSET_DIR = BASE / "prod-mc-asset-server"

data = json.loads(JSON_PATH.read_text(encoding="utf-8"))

print("=== ROOT KEYS ===")
print(list(data.keys()))
print("conversations:", len(data["conversations"]))
print("projects:", len(data["projects"]))
print("media_posts:", len(data["media_posts"]))

# Projects
print("\n=== PROJECTS (name + personality preview) ===")
for p in data["projects"]:
    name = p.get("name") or "(unnamed)"
    pers = (p.get("custom_personality") or "")[:80].replace("\n", " ")
    print(f"  {p['workspace_id']} | {name}")
    if pers:
        print(f"      personality: {pers}...")

# Conversations overview
convs = data["conversations"]
print("\n=== CONVERSATIONS overview ===")
print("Total:", len(convs))
titles = [c["conversation"].get("title", "(untitled)") for c in convs]
print("Sample titles:", titles[:5])

# Response structure deep dive
senders = Counter()
models = Counter()
attach_count = 0
attach_uuids = set()

for c in convs:
    for rw in c.get("responses", []):
        r = rw.get("response", {})
        senders[r.get("sender", "?")] += 1
        if r.get("model"):
            models[r["model"]] += 1
        fas = r.get("file_attachments") or []
        if isinstance(fas, list):
            for a in fas:
                if isinstance(a, str) and len(a) > 10:
                    attach_uuids.add(a)
                    attach_count += 1

print("\n=== SENDERS ===")
print(dict(senders))
print("\n=== MODELS ===")
print(dict(models))
print("\nTotal file_attachment refs:", attach_count, "unique UUIDs:", len(attach_uuids))

# Check which attachments exist on disk
on_disk = {d.name for d in ASSET_DIR.iterdir() if d.is_dir()}
matched = attach_uuids & on_disk
print("Matched on disk assets via file_attachments:", len(matched))

# Look for asset_ids on conv
conv_asset_ids = set()
for c in convs:
    aids = c.get("conversation", {}).get("asset_ids") or []
    if isinstance(aids, list):
        conv_asset_ids.update(aids)
print("Unique conv asset_ids:", len(conv_asset_ids))
print("Matched conv assets:", len(conv_asset_ids & on_disk))

# Parse messages for special Grok render cards and generated images
card_ids = set()
image_refs = []
for c in convs:
    for rw in c.get("responses", []):
        msg = rw.get("response", {}).get("message", "") or ""
        if isinstance(msg, str):
            for m in re.finditer(r'card_id=["\']([^"\']+)["\']', msg):
                card_ids.add(m.group(1))
            # Look for image src or asset like refs
            for m in re.finditer(r'(https?://[^\s"\'<>]+\.(?:jpg|jpeg|png|webp|gif))', msg, re.I):
                image_refs.append(m.group(1))

print("\n=== GENERATED / RENDER CARDS ===")
print("Unique card_ids found:", len(card_ids))
print("Sample:", list(card_ids)[:8])

# Check a sample message with image card for clues on asset mapping
print("\n=== SAMPLE MESSAGE WITH RENDER ===")
for c in convs:
    for rw in c.get("responses", []):
        msg = rw.get("response", {}).get("message", "") or ""
        if isinstance(msg, str) and "generated_image_card" in msg:
            print(msg[:600])
            break
    else:
        continue
    break

# Look for how generated images map to UUID assets. Maybe inside metadata or elsewhere.
print("\n=== Checking for other potential asset refs in metadata or elsewhere ===")
other_refs = set()
for c in convs[:10]:
    for rw in c.get("responses", []):
        md = rw.get("response", {}).get("metadata") or {}
        for v in str(md).split():
            if len(v) == 36 and v.count("-") == 4:
                other_refs.add(v)
print("Potential UUIDs in metadata sample:", len(other_refs & on_disk))

print("\nDone analysis.")
