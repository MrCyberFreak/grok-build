---
name: untrusted-repo-static-audit
description: Static, read-only security audit of an untrusted / third-party CLONED repo WITHOUT installing, building, or running it. Use when asked to audit, vet, or security-review a clone without running it, check whether a cloned repo is safe to use, do a read-only security pass over clones, or check a repo for supply-chain / install-hook / exec / SSRF / prompt-injection risk before trusting it; produces a per-repo SECURITY-AUDIT.md. NOT for running tests, reviewing your own code, or dependency upgrades.
allowed-tools: Read, Grep, Glob, Bash, Write
---

Statically vet an **untrusted / third-party cloned repository** for security risk
**without installing, building, or running any of it**, then write a per-repo
`SECURITY-AUDIT.md`. The target is internet-sourced code you do not yet trust —
treat it as hostile until the audit says otherwise.

## The hard rule (state this first, enforce it throughout)

**The audit is STATIC and READ-ONLY.** On the audited repo and its dependencies you
may ONLY: read source files, run `git log` / `git rev-parse` / `git remote`, and
`grep`. You must **NEVER** install, build, import, run, or execute any of it:

- No `npm install` / `npm ci` / `npm run` / `npx`, no `yarn`, no `pnpm`.
- No `pip install` / `uv sync` / `setup.py` / `pyproject` build, no `python`/`python -m`,
  no `pytest`, no importing the package.
- No `make`, no `docker build`/`docker run`, no executing any script the repo ships.

Bash is allowed **only** for read-only `git`/`grep`/file listing on the target —
never to install, build, or run it. If the user asks you to run the repo (or its
tests, or its install), **refuse and explain why**: installing/running untrusted
code is exactly the risk this audit exists to characterize, and many of these repos
execute code by design. Offer instead to finish the static audit and recommend the
isolation under which it *could* later be run.

State the read-only constraint explicitly at the top of your work and at the top of
the SECURITY-AUDIT.md you produce.

## Procedure

### 1. Set scope and state the constraint
- Identify the target path(s) — one repo or several clones. Confirm which trees are
  in scope and which (e.g. the wrapper project's own root) are out of scope.
- State up front, in chat: this is a static read-only audit; nothing will be
  installed, built, or executed.

### 2. Record provenance (per repo)
- Capture the upstream URL and the current HEAD SHA for each repo. Prefer
  `git -C <repo> remote -v` and `git -C <repo> rev-parse HEAD`. If the clone's
  nested `.git/` was stripped, record the upstream + cloned commit from whatever
  source documents it.
- Write provenance into a `CLONE-PROVENANCE.md` (or a provenance section of the
  audit doc). Format: a table of `local dir | upstream | cloned commit (HEAD)`.
  Note if a tree is no longer a pristine clone (local edits applied).

### 3. Grep/read for risk surfaces (minimum checklist)
Search every repo for each category below. Use Grep/Glob/Read only. For each hit,
open the file and read enough context to judge it — do not report a raw grep line as
a finding.

- **Code-exec sinks** — `subprocess(..., shell=True)`, `os.system`, `eval(`/`exec(`,
  `child_process`, `spawn`/`execSync`, shell backticks, `new Function(`/`Function(`,
  `runpy`/`importlib...exec_module`, and any "run this LLM-proposed code/command"
  path. Trace whether **LLM or web-derived input reaches the sink**.
- **Install/build hooks** — `setup.py`/`pyproject` build hooks, `package.json`
  `scripts` (`preinstall`/`install`/`postinstall`/`prepare`), Makefile install
  targets, anything that runs at install time. (Standard native-binary postinstalls
  like `esbuild`/`fsevents` are usually dev-only — note them, don't over-flag.)
- **Deserialization** — `pickle`, unsafe `yaml.load` (vs `yaml.safe_load`),
  `marshal`, `torch.load`, `eval`-based config loading.
- **Network / SSRF + secrets exfil** — outbound calls to attacker-influenceable
  URLs: caller-supplied `callback_url`, config-controlled `base_url`, raw
  `requests`/`httpx`/`fetch` to user-supplied hosts, `git clone` of
  attacker-selected URLs. Flag missing scheme/host allowlists. Separately grep for
  **hardcoded secrets/keys** (distinguish real key shapes from `.env.example`
  placeholders and deliberately-invalid test fixtures).
- **Prompt-injection surfaces** — untrusted text (scraped web pages, files,
  tool output) flowing into an LLM that then drives **code execution or tool
  calls**. The dividing line: injected text reaching a *text* sink (prompt,
  embedding, markdown file) can poison results but not execute; reaching a
  *command/code* sink is RCE.
- **Dependency typosquats / unpinned git deps** — suspicious or near-miss package
  names, `git+https://` deps with no commit pin, `>=`-only ranges with no committed
  lockfile (supply-chain drift). Verify lockfiles resolve to public registries.
- **Fake / broken sandboxes** — "sandbox" code that does not actually isolate
  (e.g. bind-mounting `/` read-write, retaining host network/UID/credentials).
  A misleading sandbox is more dangerous than none.

### 4. Triage each finding
For every finding record: **severity** (Critical / High / Medium / Low / Info),
**file:line**, **why it matters**, and whether it is **by-design vs accidental**.
Call out **false positives explicitly** (e.g. PyTorch `nn.Module.eval()` is not
Python `eval()`; list-form `subprocess.run([...])` with no `shell=True` is not
shell injection). By-design RCE (an agent that runs LLM-proposed code) is addressed
by *isolation*, not by editing the code — say so.

### 5. Write SECURITY-AUDIT.md
Default output path `<repo>/SECURITY-AUDIT.md` (configurable per the user's request;
for a multi-repo set, one shared doc covering all is fine). Use the template below.
Give a per-repo **verdict** on whether it is safe to run and under what isolation.
Be honest about what the static pass could NOT determine.

## SECURITY-AUDIT.md template

```markdown
# Security Audit — <target>

- **Date:** <YYYY-MM-DD>
- **Scope:** <repos/paths audited; what is explicitly excluded>
- **Method:** **Static / read-only only.** Source inspected with Read/Grep/Glob.
  **Nothing was installed, built, imported, or executed**, and no network calls
  were made.
- **Threat model:** <untrusted internet-sourced code; intended use; does any of it
  execute code by design?>

---

## 1. Executive summary

| Repo | Role/intent | Install-time exec | By-design code/cmd exec | Hardcoded secrets | Verdict |
|---|---|---|---|---|---|
| <name> | <role> | <None/finding> | <None/finding> | <None/finding> | <verdict> |

**Top takeaways**
1. <the few things that actually matter, most important first>

---

## 2. Cross-cutting findings
- <patterns that span multiple repos: prompt-injection→exec, SSRF family,
  deserialization, dependency hygiene>

---

## 3. Per-repo detail

### 3.1 <repo> — <upstream slug> · Verdict: <verdict>

<1-2 lines: what it is, build system, entry points, where the attack surface is.>

| Severity | Category | Location | Description |
|---|---|---|---|
| Critical/High/Medium/Low/Info | <category> | `file:line` | <what & why; by-design vs accidental> |

**Reuse:** <can it be reused, and under what isolation/conditions?>

---

## 4. Reuse / safe-to-run guidance
- <per target: safe to run as-is? sandbox required? which sandbox (rootless
  container / gVisor / VM, dropped network, no host creds)? what to allowlist?>

---

## 5. Limitations / what this audit did NOT do
- **Static only.** Nothing installed/run/network-tested; transitive dependency
  trees not resolved (no `npm audit`/`pip-audit`); runtime behavior not observed.
- Findings reflect the cloned snapshots as of <date>; upstream may have changed.
- These repos are **not "cleared" for execution** unless explicitly stated, and
  any by-design exec paths must never run outside isolation.
```

## Out of scope (do not do these here)
- **Dynamic analysis** — running the code, fuzzing, observing runtime behavior.
- **Dependency installation** of any kind (no `npm/pip/uv install`, no `npm audit`
  / `pip-audit`, which install/resolve).
- **Running tests.**
- **Fixing the audited code.** Hardening the repo is a separate step done only after
  this audit and with explicit approval; this skill only finds and reports.

## When NOT to use this skill
- Running a repo's test suite — that requires executing it; refuse here.
- Reviewing the user's **own** new code for secure coding — that's a normal
  code/security review of a diff, not an untrusted-clone audit.
- General dependency upgrades / bumping `package.json` versions.

A real, completed example of the intended output style and verdict tone lives at
`X:\Grok_Build\Projects\Playground\_research-audit\SECURITY-AUDIT.md` (with
provenance at `_research-audit\CLONE-PROVENANCE.md`). Mirror its structure and
honesty when available.
