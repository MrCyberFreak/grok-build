#!/usr/bin/env python
"""gather_state.py - deterministic live-config inventory for /insight-amplify.

This is the heart of the "subtract what exists" step. The amplifier's whole value
is loading the user's REAL state into context so it can drop /insights suggestions
the user already adopted. That subtraction must be precise and cheap, so this step
is deterministic (a glob/parse pass), not an agent guess.

It enumerates what the user ALREADY HAS:
  - skills      (Global/skills/<name>/SKILL.md           -> name + description)
  - plugin_skills (SKILL.md from ENABLED plugins only    -> plugin:skill + description)
                 installed-cache plugin: counts unless enabledPlugins says false;
                 seed-cache plugin: counts ONLY if enabledPlugins says true (opt-in,
                 because the vendored seed is disabled by default). Never counts the
                 inert seed as available - that would be false coverage.
  - commands    (Global/commands/*.md                    -> name + description)
  - agents      (Global/agents/*.md                      -> name + description)
  - hooks       (Global/settings.json + each project's   -> event + matcher + command)
                 .claude/settings.json hook entries)
  - claude_md   (Global/CLAUDE.md + each project's CLAUDE.md -> section/rule headings)
  - workflows   (Global/workflows/*.js + project .claude/workflows/*)

Robust to missing dirs/files (a project without .claude/settings.json must not crash).
Emits a compact JSON object the skill body reads. ASCII-only output (cp1252 console).

Usage:
  python gather_state.py [--config-dir DIR] [--projects-root DIR] [--pretty]

Defaults: --config-dir   = $GROK_HOME or X:\\Grok_Build\\.grok
          --projects-root = X:\\Grok_Build\\Projects
"""
import argparse
import glob
import json
import os
import re
import sys

DEFAULT_CONFIG_DIR = os.environ.get("GROK_HOME") or r"X:\Grok_Build\.grok"
DEFAULT_PROJECTS_ROOT = r"X:\Grok_Build\Projects"


def read_text(path):
    """Read a file as UTF-8; return '' on any failure (missing/locked/bad encoding)."""
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return ""


def ascii_safe(s):
    """Collapse to a single line and strip non-ASCII so console output never throws."""
    if not s:
        return ""
    s = re.sub(r"\s+", " ", s).strip()
    return s.encode("ascii", "replace").decode("ascii")


def parse_frontmatter(text):
    """Return the YAML-ish frontmatter block as a dict of top-level scalar keys.

    Deliberately shallow: we only need `name` and `description`, and a regex parse
    avoids a hard pyyaml dependency. Handles a leading `---` fenced block.
    """
    fields = {}
    # tolerate a leading UTF-8 BOM before the frontmatter fence (escape, no literal BOM)
    text = text.lstrip("\ufeff")
    m = re.match(r"^---\s*\r?\n(.*?)\r?\n---\s*\r?\n", text, re.DOTALL)
    if not m:
        return fields
    block = m.group(1)
    # match `key: value` at the start of a line (value runs to end of line)
    for km in re.finditer(r"(?m)^([A-Za-z0-9_-]+):[ \t]*(.*)$", block):
        key = km.group(1).strip()
        val = km.group(2).strip()
        # strip a single layer of wrapping quotes
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        if key not in fields:
            fields[key] = val
    return fields


def first_heading_or_name(path, text):
    """Fallback display name when frontmatter lacks `name`: the file/dir stem."""
    return os.path.splitext(os.path.basename(path))[0]


def gather_skills(config_dir):
    out = []
    pattern = os.path.join(config_dir, "skills", "*", "SKILL.md")
    for sk in sorted(glob.glob(pattern)):
        text = read_text(sk)
        fm = parse_frontmatter(text)
        name = fm.get("name") or os.path.basename(os.path.dirname(sk))
        out.append({
            "name": ascii_safe(name),
            "description": ascii_safe(fm.get("description", "")),
            "source": "user",
        })
    return out


def _ver_key(v):
    """Natural-sort key for a version dir so 1.12.0 ranks above 1.9.0."""
    key = []
    for p in re.split(r"[.\-+_]", v or ""):
        key.append((0, int(p)) if p.isdigit() else (1, p))
    return key


def load_enabled_plugins(config_dir, projects_root):
    """Merge enabledPlugins across settings scopes -> {"plugin@marketplace": bool}.

    Honors user/local/managed (global) + each project's settings(.local).json. Later
    files override earlier ones (good-enough precedence; the authoritative resolver is
    `claude plugin list --json`, which also handles defaultEnabled and orphaned versions).
    """
    merged = {}
    files = [
        os.path.join(config_dir, "settings.json"),
        os.path.join(config_dir, "settings.local.json"),
        os.path.join(config_dir, "managed-settings.json"),
    ]
    if os.path.isdir(projects_root):
        for entry in sorted(os.listdir(projects_root)):
            for sub in (".grok", ".claude"):
                cd = os.path.join(projects_root, entry, sub)
                files.append(os.path.join(cd, "settings.json"))
                files.append(os.path.join(cd, "settings.local.json"))
    for f in files:
        text = read_text(f)
        if not text.strip():
            continue
        try:
            data = json.loads(text)
        except (ValueError, TypeError):
            continue
        ep = data.get("enabledPlugins")
        if isinstance(ep, dict):
            for k, v in ep.items():
                merged[str(k)] = bool(v)
    return merged


def _plugin_cache_roots(config_dir):
    """(root, kind) pairs to scan. Grok-only: GROK_HOME tree on X: drive only."""
    roots = [
        (os.path.join(config_dir, "plugins", "cache"), "installed"),
        (os.path.join(config_dir, "marketplace-cache"), "installed"),
        (os.path.join(config_dir, "plugins-seed", "cache"), "seed"),
    ]
    # Only honor explicit env overrides that stay on X: (Grok home tree).
    for env_name, kind in (("GROK_PLUGIN_CACHE_DIR", "installed"),
                           ("CLAUDE_CODE_PLUGIN_CACHE_DIR", "installed"),
                           ("GROK_PLUGIN_SEED_DIR", "seed"),
                           ("CLAUDE_CODE_PLUGIN_SEED_DIR", "seed")):
        val = os.environ.get(env_name)
        if not val:
            continue
        norm = os.path.normcase(os.path.abspath(val))
        if norm.startswith(os.path.normcase(r"X:\Grok_Build")):
            roots.append((val, kind))
    return roots


def gather_plugin_skills(config_dir, projects_root):
    """Enumerate SKILL.md from ENABLED plugins only (skips disabled + inert seed).

    Layout: cache/<marketplace>/<plugin>/<version>/skills/<skill>/SKILL.md (and a
    single-skill plugin's root .../<version>/SKILL.md). For each (marketplace, plugin)
    the newest version dir wins (orphaned old versions are ignored). Enablement gate:
      installed-cache -> included unless enabledPlugins["plugin@marketplace"] is False
      seed-cache      -> included ONLY if enabledPlugins["plugin@marketplace"] is True
    """
    enabled = load_enabled_plugins(config_dir, projects_root)
    out = []
    seen = set()
    for root, kind in _plugin_cache_roots(config_dir):
        if not os.path.isdir(root):
            continue
        # group candidate SKILL.md files by (marketplace, plugin)
        by_plugin = {}
        patterns = [
            os.path.join(root, "*", "*", "*", "skills", "*", "SKILL.md"),
            os.path.join(root, "*", "*", "*", "SKILL.md"),  # single-skill plugin root
        ]
        for pattern in patterns:
            for sk in glob.glob(pattern):
                rel = os.path.relpath(sk, root).split(os.sep)
                if len(rel) == 6:        # mkt/plugin/ver/skills/<name>/SKILL.md
                    marketplace, plugin, version, skill_dir = rel[0], rel[1], rel[2], rel[4]
                elif len(rel) == 4:      # mkt/plugin/ver/SKILL.md (single-skill)
                    marketplace, plugin, version, skill_dir = rel[0], rel[1], rel[2], rel[1]
                else:
                    continue
                by_plugin.setdefault((marketplace, plugin), []).append(
                    (version, skill_dir, sk))
        for (marketplace, plugin), items in by_plugin.items():
            key = plugin + "@" + marketplace
            state = enabled.get(key)
            if kind == "seed":
                if state is not True:        # vendored seed is opt-in
                    continue
            else:                            # installed cache
                if state is False:           # explicitly disabled
                    continue
            newest = sorted({v for v, _, _ in items}, key=_ver_key)[-1]
            for version, skill_dir, sk in items:
                if version != newest:
                    continue
                if (key, sk) in seen:
                    continue
                seen.add((key, sk))
                fm = parse_frontmatter(read_text(sk))
                sname = fm.get("name") or skill_dir
                out.append({
                    "name": ascii_safe(plugin + ":" + sname),
                    "description": ascii_safe(fm.get("description", "")),
                    "source": "plugin",
                    "plugin": ascii_safe(plugin),
                    "marketplace": ascii_safe(marketplace),
                    "version": ascii_safe(newest),
                    "store": kind,
                })
    out.sort(key=lambda r: r["name"])
    return out


def gather_commands(config_dir):
    out = []
    pattern = os.path.join(config_dir, "commands", "*.md")
    for cmd in sorted(glob.glob(pattern)):
        text = read_text(cmd)
        fm = parse_frontmatter(text)
        out.append({
            "name": ascii_safe(fm.get("name") or first_heading_or_name(cmd, text)),
            "description": ascii_safe(fm.get("description", "")),
        })
    return out


def gather_agents(config_dir):
    out = []
    pattern = os.path.join(config_dir, "agents", "*.md")
    for ag in sorted(glob.glob(pattern)):
        text = read_text(ag)
        fm = parse_frontmatter(text)
        out.append({
            "name": ascii_safe(fm.get("name") or first_heading_or_name(ag, text)),
            "description": ascii_safe(fm.get("description", "")),
        })
    return out


def _hooks_from_settings(path, scope):
    """Flatten a settings.json hooks block into [{scope,event,matcher,command}]."""
    rows = []
    text = read_text(path)
    if not text.strip():
        return rows
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return rows
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return rows
    for event, entries in hooks.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            matcher = entry.get("matcher", "")
            for h in entry.get("hooks", []) or []:
                if not isinstance(h, dict):
                    continue
                rows.append({
                    "scope": scope,
                    "event": ascii_safe(str(event)),
                    "matcher": ascii_safe(str(matcher)),
                    "command": ascii_safe(str(h.get("command", h.get("type", "")))),
                })
    return rows


def _hooks_from_grok_json(path, scope):
    """Flatten a Grok hooks/*.json file into [{scope,event,matcher,command}]."""
    rows = []
    text = read_text(path)
    if not text.strip():
        return rows
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return rows
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return rows
    for event, entries in hooks.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            matcher = entry.get("matcher", "")
            for h in entry.get("hooks", []) or []:
                if not isinstance(h, dict):
                    continue
                rows.append({
                    "scope": scope,
                    "event": ascii_safe(str(event)),
                    "matcher": ascii_safe(str(matcher)),
                    "command": ascii_safe(str(h.get("command", h.get("type", "")))),
                })
    return rows


def gather_hooks(config_dir, projects_root):
    rows = []
    # Grok global hooks
    hooks_dir = os.path.join(config_dir, "hooks")
    if os.path.isdir(hooks_dir):
        for hp in sorted(glob.glob(os.path.join(hooks_dir, "*.json"))):
            rows.extend(_hooks_from_grok_json(hp, "global:" + os.path.basename(hp)))
    # Claude-compat settings.json (if present)
    rows.extend(_hooks_from_settings(os.path.join(config_dir, "settings.json"), "global"))
    if os.path.isdir(projects_root):
        for entry in sorted(os.listdir(projects_root)):
            proj = os.path.join(projects_root, entry)
            if not os.path.isdir(proj):
                continue
            for sub, label in ((".grok", "grok"), (".claude", "claude")):
                sp = os.path.join(proj, sub, "settings.json")
                if os.path.isfile(sp):
                    rows.extend(_hooks_from_settings(sp, "project:" + entry + ":" + label))
                hdir = os.path.join(proj, sub, "hooks")
                if os.path.isdir(hdir):
                    for hp in sorted(glob.glob(os.path.join(hdir, "*.json"))):
                        rows.extend(_hooks_from_grok_json(
                            hp, "project:" + entry + ":" + label + ":" + os.path.basename(hp)))
    return rows


def gather_claude_md(config_dir, projects_root):
    """Return rule/section headings from the global + each project's CLAUDE.md."""
    out = []

    def headings(path, scope):
        text = read_text(path)
        if not text:
            return
        hs = []
        for hm in re.finditer(r"(?m)^(#{2,3})[ \t]+(.+?)[ \t]*$", text):
            hs.append(ascii_safe(hm.group(2)))
        out.append({"scope": scope, "path": path, "headings": hs})

    for name, scope in (("AGENTS.md", "global"), ("CLAUDE.md", "global-compat")):
        p = os.path.join(config_dir, name)
        if os.path.isfile(p):
            headings(p, scope)
    if os.path.isdir(projects_root):
        for entry in sorted(os.listdir(projects_root)):
            proj = os.path.join(projects_root, entry)
            for name in ("AGENTS.md", "CLAUDE.md"):
                cm = os.path.join(proj, name)
                if os.path.isfile(cm):
                    headings(cm, "project:" + entry)
    return out


def gather_workflows(config_dir, projects_root):
    out = []
    for wf in sorted(glob.glob(os.path.join(config_dir, "workflows", "*.js"))):
        out.append({"scope": "global", "name": ascii_safe(os.path.basename(wf))})
    if os.path.isdir(projects_root):
        for entry in sorted(os.listdir(projects_root)):
            proj = os.path.join(projects_root, entry)
            for sub in (".grok", ".claude"):
                wdir = os.path.join(proj, sub, "workflows")
                if os.path.isdir(wdir):
                    for wf in sorted(glob.glob(os.path.join(wdir, "*"))):
                        if os.path.isfile(wf):
                            out.append({
                                "scope": "project:" + entry + ":" + sub.strip("."),
                                "name": ascii_safe(os.path.basename(wf)),
                            })
    return out


def build_inventory(config_dir, projects_root):
    skills = gather_skills(config_dir)
    plugin_skills = gather_plugin_skills(config_dir, projects_root)
    commands = gather_commands(config_dir)
    agents = gather_agents(config_dir)
    hooks = gather_hooks(config_dir, projects_root)
    claude_md = gather_claude_md(config_dir, projects_root)
    workflows = gather_workflows(config_dir, projects_root)
    return {
        "config_dir": config_dir,
        "projects_root": projects_root,
        "counts": {
            "skills": len(skills),
            "plugin_skills": len(plugin_skills),
            "skills_total": len(skills) + len(plugin_skills),
            "commands": len(commands),
            "agents": len(agents),
            "hooks": len(hooks),
            "claude_md_files": len(claude_md),
            "workflows": len(workflows),
        },
        "skills": skills,
        "plugin_skills": plugin_skills,
        "commands": commands,
        "agents": agents,
        "hooks": hooks,
        "claude_md": claude_md,
        "workflows": workflows,
    }


def main(argv):
    p = argparse.ArgumentParser(description="Deterministic live-config inventory for /insight-amplify.")
    p.add_argument("--config-dir", default=DEFAULT_CONFIG_DIR)
    p.add_argument("--projects-root", default=DEFAULT_PROJECTS_ROOT)
    p.add_argument("--pretty", action="store_true", help="indent the JSON output")
    args = p.parse_args(argv)

    inv = build_inventory(args.config_dir, args.projects_root)
    text = json.dumps(inv, indent=2 if args.pretty else None, ensure_ascii=True)
    # ensure_ascii=True already guarantees cp1252-safe output
    sys.stdout.write(text + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
