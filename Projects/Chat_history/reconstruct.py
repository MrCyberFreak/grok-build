#!/usr/bin/env python3
"""
Reconstruct Grok chat history from backup export.

- Parses conversations + responses into clean message threads
- Associates projects (as agent/persona definitions)
- Maps file_attachments and card_attachments_json -> asset UUIDs
- Copies used media to ui/assets/ with proper extensions
- Outputs clean data.json + basic UI scaffold
"""
import json
import re
import shutil
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

# Paths
BASE = Path("raw/chat_backup/ttl/30d/export_data/a7a3aa8e-20d8-49be-983e-a736948648a6")
SRC_JSON = BASE / "prod-grok-backend.json"
ASSET_ROOT = BASE / "prod-mc-asset-server"

OUT_DIR = Path("ui")
ASSETS_DIR = OUT_DIR / "assets"
DATA_JSON = OUT_DIR / "data.json"

# Ensure clean output
if OUT_DIR.exists():
    shutil.rmtree(OUT_DIR)
OUT_DIR.mkdir(parents=True)
ASSETS_DIR.mkdir()

def normalize_time(t):
    """Convert Mongo-style or ISO time to ISO string."""
    if not t:
        return None
    if isinstance(t, dict):
        # {"$date": {"$numberLong": "17812..."}}
        num = None
        if "$date" in t:
            d = t["$date"]
            if isinstance(d, dict) and "$numberLong" in d:
                num = int(d["$numberLong"])
            elif isinstance(d, (int, float, str)):
                num = int(d)
        if num:
            # Treat as ms since epoch
            return datetime.fromtimestamp(num / 1000, tz=timezone.utc).isoformat()
    if isinstance(t, str):
        return t
    if isinstance(t, (int, float)):
        return datetime.fromtimestamp(t / 1000, tz=timezone.utc).isoformat()
    return str(t)

def detect_media(data: bytes):
    """Return (ext, media_type) where media_type in image|video|other."""
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg", "image"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png", "image"
    if data[0:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp", "image"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return ".gif", "image"
    if b"ftyp" in data[4:12] or data[4:8] in (b"ftyp", b"isom", b"mp42", b"avc1"):
        return ".mp4", "video"
    if data[0:4] == b"RIFF" and data[8:12] == b"AVI ":
        return ".avi", "video"
    if data.startswith(b"\x1a\x45\xdf\xa3"):  # webm/mkv
        return ".webm", "video"
    if data.startswith(b"PK\x03\x04"):
        return ".zip", "other"
    if data.lstrip().startswith(b"{") or data.lstrip().startswith(b"["):
        return ".json", "meta"
    return ".bin", "other"

def load_json():
    print("Loading source JSON...")
    return json.loads(SRC_JSON.read_text(encoding="utf-8"))

def parse_card_attachments(card_json_list):
    """card_attachments_json is list of JSON *strings*."""
    results = []
    if not isinstance(card_json_list, list):
        return results
    for item in card_json_list:
        if isinstance(item, str):
            try:
                obj = json.loads(item)
                results.append(obj)
            except Exception:
                pass
        elif isinstance(item, dict):
            results.append(item)
    return results

def extract_attachments_from_response(resp):
    """Return list of attachment dicts for a response."""
    atts = []
    # 1. file_attachments (usually user uploads)
    fas = resp.get("file_attachments")
    if isinstance(fas, list):
        for fid in fas:
            if isinstance(fid, str) and len(fid) > 20:
                atts.append({"id": fid, "kind": "upload", "prompt": None})

    # 2. card_attachments_json -> generated images
    cards = parse_card_attachments(resp.get("card_attachments_json"))
    for card in cards:
        if not isinstance(card, dict):
            continue
        img_uuid = None
        # Common locations
        if "imageUuid" in card:
            img_uuid = card["imageUuid"]
        elif "image_chunk" in card and isinstance(card["image_chunk"], dict):
            img_uuid = card["image_chunk"].get("imageUuid")
        if img_uuid and isinstance(img_uuid, str) and len(img_uuid) > 20:
            prompt = None
            if "imagePrompt" in card and isinstance(card["imagePrompt"], dict):
                prompt = card["imagePrompt"].get("prompt")
            elif "prompt" in card:
                prompt = card["prompt"]
            # Also try nested
            if not prompt and "image_chunk" in card:
                ip = card["image_chunk"].get("imagePrompt") or {}
                if isinstance(ip, dict):
                    prompt = ip.get("prompt")
            atts.append({
                "id": img_uuid,
                "kind": "generated",
                "prompt": prompt
            })
    return atts

def clean_message_content(raw: str) -> str:
    """Remove or simplify grok:render tags. Keep readable text."""
    if not isinstance(raw, str):
        return ""
    # Remove full <grok:render ...>...</grok:render> blocks for images (we render via attachments)
    cleaned = re.sub(
        r'<grok:render[^>]*type=["\']render_generated_image["\'][^>]*>.*?</grok:render>',
        "",
        raw,
        flags=re.DOTALL | re.IGNORECASE
    )
    # Also strip other render cards that are structural
    cleaned = re.sub(r'<grok:render[^>]*/>', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'<grok:render[^>]*>.*?</grok:render>', '[embedded content]', cleaned, flags=re.DOTALL | re.IGNORECASE)
    # Trim excessive whitespace
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned.strip()

def build_projects(raw_projects):
    projects = []
    for p in raw_projects:
        projects.append({
            "id": p.get("workspace_id"),
            "name": p.get("name") or "(unnamed)",
            "icon": p.get("icon"),
            "custom_personality": p.get("custom_personality"),
            "preferred_model": p.get("preferred_model"),
            "create_time": normalize_time(p.get("create_time")),
            "last_use_time": normalize_time(p.get("last_use_time")),
        })
    return projects

def build_conversations(raw_convs):
    conversations = []
    all_asset_ids = set()

    for c in raw_convs:
        co = c.get("conversation", {})
        cid = co.get("id")
        title = co.get("title") or "(untitled)"
        create_time = normalize_time(co.get("create_time"))
        modify_time = normalize_time(co.get("modify_time"))

        raw_responses = c.get("responses", [])
        messages = []
        for rw in raw_responses:
            r = rw.get("response", {})
            sender = r.get("sender", "unknown").lower()
            role = "user" if sender == "human" else "assistant"
            content = clean_message_content(r.get("message", ""))
            ts = normalize_time(r.get("create_time"))
            model = r.get("model")

            attachments = extract_attachments_from_response(r)
            for a in attachments:
                all_asset_ids.add(a["id"])

            messages.append({
                "id": r.get("_id") or r.get("id"),
                "role": role,
                "content": content,
                "timestamp": ts,
                "model": model,
                "attachments": attachments,
            })

        conversations.append({
            "id": cid,
            "title": title,
            "create_time": create_time,
            "modify_time": modify_time,
            "messages": messages,
            # project_id not populated in this export; we keep for future
            "project_id": co.get("project_id"),
            "system_prompt_name": co.get("system_prompt_name"),
        })

    return conversations, all_asset_ids

def copy_assets(used_ids, out_assets_dir):
    """Copy referenced assets. Return asset_info: id -> {path, type, size}"""
    print(f"Copying {len(used_ids)} referenced assets...")
    asset_info = {}
    copied = 0
    missing = 0

    for aid in sorted(used_ids):
        src_dir = ASSET_ROOT / aid
        src_file = src_dir / "content"
        if not src_file.exists():
            missing += 1
            continue
        try:
            raw = src_file.read_bytes()
            ext, mtype = detect_media(raw)
            dest_name = f"{aid}{ext}"
            dest = out_assets_dir / dest_name
            dest.write_bytes(raw)
            asset_info[aid] = {
                "path": f"assets/{dest_name}",
                "type": mtype,
                "size": len(raw),
                "ext": ext
            }
            copied += 1
        except Exception as e:
            print("  Error copying", aid, e)

    print(f"  Copied: {copied}, missing: {missing}")
    return asset_info

def main():
    raw = load_json()

    print("Building projects...")
    projects = build_projects(raw.get("projects", []))

    print("Building conversations and collecting attachments...")
    conversations, used_asset_ids = build_conversations(raw.get("conversations", []))
    print(f"  {len(conversations)} conversations, {len(used_asset_ids)} unique referenced assets")

    print("Copying media assets...")
    asset_info = copy_assets(used_asset_ids, ASSETS_DIR)

    # Also include media_posts if wanted (they have external links)
    media_posts = []
    for mp in raw.get("media_posts", []):
        media_posts.append({
            "id": mp.get("id"),
            "media_type": mp.get("media_type"),
            "create_time": normalize_time(mp.get("create_time")),
            "original_prompt": mp.get("original_prompt"),
            "link": mp.get("link"),
        })

    out_data = {
        "export_meta": {
            "source": "Grok backup export (prod-grok-backend.json)",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "projects": projects,
        "conversations": conversations,
        "media_posts": media_posts,
        "asset_info": asset_info,
    }

    DATA_JSON.write_text(json.dumps(out_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {DATA_JSON}")
    print(f"Assets in {ASSETS_DIR} : {len(asset_info)} files")

    # Also write a small summary
    summary = {
        "num_projects": len(projects),
        "num_conversations": len(conversations),
        "num_messages": sum(len(c["messages"]) for c in conversations),
        "num_assets_copied": len(asset_info),
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2))
    print("Summary:", summary)
    print("\nReconstruction complete. Next: build the UI.")

if __name__ == "__main__":
    main()
