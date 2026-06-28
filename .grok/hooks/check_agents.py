#!/usr/bin/env python
"""Validate Claude Code agent frontmatter + description hygiene.

Catches the failure mode where a malformed `description:` makes an agent's YAML
frontmatter unparseable, so the harness SILENTLY de-registers the agent.

Usage:  python check_agents.py [CONFIG_DIR]
Exit:   0 = no hard failures (warnings allowed); 1 = >=1 agent file is invalid.
Output: ASCII-only (Windows cp1252 console safe).
"""
import sys, os, glob, re

_args = [a for a in sys.argv[1:] if not a.startswith("--")]
QUIET = ("--fail-only" in sys.argv) or ("--quiet" in sys.argv)  # hook mode: stay silent unless a hard failure
cfg = _args[0] if _args else (os.environ.get("GROK_HOME") or r"X:\Grok_Build\.grok")
agents_dir = os.path.join(cfg, "agents")

try:
    import yaml
    HAVE_YAML = True
except Exception:
    HAVE_YAML = False
    print("  WARN  pyyaml not installed - shallow structural check only (install pyyaml for full YAML validation).")

agent_files = sorted(glob.glob(os.path.join(agents_dir, "*.md")))
agent_names = set(os.path.splitext(os.path.basename(f))[0] for f in agent_files)
command_names = set(os.path.splitext(os.path.basename(p))[0]
                    for p in glob.glob(os.path.join(cfg, "commands", "*.md")))
skill_names = set(os.path.basename(os.path.dirname(s))
                  for s in glob.glob(os.path.join(cfg, "skills", "*", "SKILL.md")))
workflow_names = set(os.path.splitext(os.path.basename(p))[0]
                     for p in glob.glob(os.path.join(cfg, "workflows", "*.js")))
builtin_agents = {"general-purpose", "explore", "plan", "claude-code-guide", "claude", "statusline-setup"}
# skills/commands shipped by Claude Code itself (not files under this config dir):
builtin_skills = {"code-review", "simplify", "verify", "run", "init", "review", "security-review",
                  "update-config", "keybindings-help", "fewer-permission-prompts", "loop", "schedule",
                  "deep-research", "claude-api"}
valid = (set(n.lower() for n in (agent_names | command_names | skill_names | workflow_names))
         | builtin_agents | builtin_skills)

fail = 0
warn = 0
for f in agent_files:
    base = os.path.splitext(os.path.basename(f))[0]
    text = open(f, encoding="utf-8").read()
    m = re.match(r"^---\r?\n(.*?)\r?\n---", text, re.S)
    if not m:
        print("  FAIL  %s : no '---' frontmatter block" % base); fail += 1; continue
    block = m.group(1)
    if HAVE_YAML:
        try:
            d = yaml.safe_load(block)
        except Exception as e:
            print("  FAIL  %s : frontmatter does NOT parse -> %s" % (base, str(e).splitlines()[0][:80]))
            fail += 1; continue
        if not isinstance(d, dict) or not d.get("name") or not d.get("description"):
            print("  FAIL  %s : frontmatter missing name and/or description" % base); fail += 1; continue
        name = str(d["name"]); desc = str(d["description"])
    else:
        nm = re.search(r"(?m)^name:[ \t]*(.*)$", block)
        dm = re.search(r"(?m)^description:[ \t]*(.*)$", block)
        if not (nm and dm and dm.group(1).strip()):
            print("  FAIL  %s : missing name/description line" % base); fail += 1; continue
        name = nm.group(1).strip(); desc = dm.group(1).strip()

    # --- hygiene (warnings, not failures) ---
    if name != base:
        warn += 1
        if not QUIET: print("  WARN  %s : name field '%s' != filename" % (base, name))
    low = desc.lower()
    if "proactively" not in low:
        warn += 1
        if not QUIET: print("  WARN  %s : description has no proactivity nudge ('proactively')" % base)
    for ref in set(re.findall(r"\buse ([a-z][a-z0-9]*-[a-z0-9-]+)", low)):
        if ref not in valid:
            warn += 1
            if not QUIET: print("  WARN  %s : handoff points to '%s' - not an agent/skill/command on disk" % (base, ref))

if not QUIET or fail:
    print("")
    print("  Agents checked: %d   hard-failures: %d   warnings: %d" % (len(agent_files), fail, warn))
sys.exit(1 if fail else 0)
