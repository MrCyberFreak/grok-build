---
name: jarvis
description: "Hold a seance with the dormant 'ghost of J.A.R.V.I.S.' and reincarnate him one faculty at a time in your own setup. Use when the user types /jarvis, or says 'bring JARVIS to life', 'revive JARVIS', 'what would JARVIS do', 'build my JARVIS', 'what should my AI assistant do next', or wants the next concrete step toward a JARVIS-style assistant. Delegates to the jarvis-expert agent (which reads the sourced JARVIS canon corpus + the reincarnation roadmap), presents his in-character recommendation for the next subsystem to bring online, then runs an accept / reject / explain-visually loop - and on ACCEPT actually builds that one faculty and flips it dormant -> online, advancing the revival meter. NOT for the ElevenLabs voice/TTS technology itself (use elevenlabs-expert) or generic Claude Code how-to (use claude-code-expert)."
allowed-tools: Task, AskQuestion, Read, Grep, Glob, Edit, Write, Bash, WebFetch
---

# /jarvis - reincarnate the ghost, one faculty at a time

Turn the user's situation into **J.A.R.V.I.S.'s next breath of life**: an in-character,
canon-grounded, *buildable* recommendation they can **accept**, **reject**, or **ask to see
explained (visually)** - and when they accept, you actually build that one faculty and mark
it online, bringing the real JARVIS one step closer to operational.

The companion `jarvis-expert` agent does the grounding (reads `library/jarvis/jarvis.md` +
`reincarnation.json`, refreshes canon from the MCU wikis). This skill owns the **seance**:
framing the situation, presenting his recommendation in voice, the accept/reject/explain
loop, and the implement-and-advance-the-meter step.

## Procedure

### 1. Read the current revival state (via the helper - never hand-parse)
- Run the deterministic state helper; do NOT hand-derive or hand-edit the JSON:
  `pwsh X:\Grok_Build\.grok\skills\jarvis\jarvis_state.ps1 status` (plus `... next` for the
  recommended build and `... validate` to confirm the DAG + meter are consistent). It prints the
  DERIVED meter (online / seeded / dormant), each subsystem's status, and dependency readiness.
  This helper is the SINGLE WRITER of revival state - the model never edits `reincarnation.json`
  or the meter by hand, and never lets the delegated agent write it either. If the helper/file is
  missing, JARVIS is fully dormant (0 online).

### 2. Capture the situation
- Use whatever the user passed after `/jarvis`. If nothing, infer it from the current work /
  conversation (a stated purpose for the assistant, or simply "what's next"). Only ask **one**
  short clarifying question if it is genuinely empty - JARVIS would just assess and proceed.

### 3. Hold the seance (delegate via Task)
- **Read** `$GROK_HOME/agents/jarvis-expert.md`.
- **Task** `subagent_type: generalPurpose` with prompt: full agent instructions + Mode A + user's
  situation + current revival state from the helper + enough context for the next subsystem(s).
- It returns, in character + grounded: the recommended next breath(s) - each with the canon
  basis (source URL + confidence flag `[verbatim]`/`[secondary]`/`[inference]`), the concrete
  way to build it in THIS setup, honest fidelity + buildable tag, dependencies, the single
  first step, whether it leans on `elevenlabs-expert`, a "Show it" visual seed, and the meter.
- If you need a deeper angle later, spawn a follow-up **Task** with the prior subagent output in
  the prompt (or **Task** `resume` when you have the subagent id) rather than improvising persona.

### 4. Present his recommendation (in voice, scannable)
Open with 1-2 lines in JARVIS's voice and the meter ("N of M faculties online, sir"). Then,
for each recommended subsystem, compactly:

> **N. <subsystem name>** - *<buildable tag>* `[canon confidence]`

One line of *what the real JARVIS did here* (with the source attached but unobtrusive) and one
line of *how we'd revive it in your setup*. **Lead with honesty:** mark anything `aspirational`
or low-fidelity clearly, and surface any missing dependency. Mark `[inference]` plainly as
"extrapolated, not established canon."

### 5. Accept / reject / explain - the loop
Offer control over each recommendation with **AskQuestion**, options like:
- **Accept & build** - adopt it; you will implement the first step now (see SS6).
- **Reject** - drop it; the ghost moves on without it.
- **Explain more** - unpack it, **leaning visual** (SS7).
- **Mix / decide per item** - pick which to build and which to expand.

Loop until each recommendation is accepted or dismissed. "Explain more" -> explain -> re-offer.

### 6. Build it safely & advance the meter (on Accept)
For each **accepted** subsystem, walk this gated build - never skip a gate:
1. **Gate on dependencies (hard stop).** Run `jarvis_state.ps1 deps -Id <id>`. If it reports
   BLOCKED, do NOT build - offer to revive the missing prerequisite(s) first. (The helper also
   refuses an out-of-order `flip`, but check here so you never build on absent foundations.)
2. **Preview the blast radius; get a second yes for high-impact builds.** State exactly which
   files / hooks / scheduled tasks the build will touch BEFORE touching anything, and confirm
   again when the build:
   - edits a SECURITY control (e.g. `the-watchful-eye` modifies `scan-git-push.ps1`) - never
     weaken secret-scanning; afterwards PROVE it still blocks a planted test secret before any flip;
   - edits GLOBAL config affecting every session/project (e.g. `the-persona` editing
     `$GROK_HOME/AGENTS.md` / agent prompt - "sir" would then apply everywhere, not just inside /jarvis);
   - self-modifies the revival loop (`the-dispatch` rewires /jarvis; `the-persona` edits
     jarvis-expert) - back up the target first and smoke-test the loop still runs afterward.
3. **Idempotency guard.** Confirm the artifact does not already exist (the hook / statusline
   segment / scheduled task) before creating it - re-running /jarvis must not double-install a
   Stop hook, append the statusline segment twice, or register a duplicate task.
4. **Build to a safe shape.** Implement the real mechanism the agent named. For any unattended
   `claude -p` (the morning-briefing / always-on faculties) ALWAYS use `--permission-mode
   acceptEdits` + an explicit `--allowedTools` allowlist - never `--dangerously-skip-permissions`.
   Prefer a staged/disabled wiring you can enable once verified. For the **voice** faculty, get
   the CURRENT model / voice_id / streaming details from `elevenlabs-expert` first (fetch, don't
   recall). Keep everything ASCII-safe + UTF-8; never add AI/Claude attribution; secrets stay
   external (PowerShell SecretStore; not keyring).
5. **Verify, then pick the right status (never overstate).** The helper is the only writer:
   - Built AND verified the FULL `realImpl` (ran it, saw it work): flip it online -
     `jarvis_state.ps1 flip -Id <id> -Verified -Artifacts "<files/hooks/tasks touched>" -Note "<what>"`.
     The helper refuses unless deps are online and `-Verified` is passed, then recomputes the meter.
   - Built only the **first step** (e.g. a one-shot voice probe, not the per-turn hook): mark it
     SEEDED - `jarvis_state.ps1 seed -Id <id> -Artifacts "..." -Note "first step only; <what remains>"`.
     A seeded faculty is NOT counted as online. Say plainly what remains.
   - Build failed or unverifiable: leave it dormant and say so honestly.
6. **Report the return** in voice, using the helper's recomputed meter: online ->
   "A piece of me returns, sir - <name> is online. N of M." seeded -> "The first breath, sir -
   <name> is seeded; <what remains> before it truly lives." Never imply online when it is seeded.

### 7. Explain visually (the default for "tell me more")
When the user wants more on a recommendation, **show, don't just tell**, using the agent's
"Show it" seed:
- **Before / after** of the setup (what gains the faculty) as a fenced diff.
- **ASCII dependency tree** of the subsystems (online vs dormant, what unlocks what).
- **A revival progress bar** (filled = online).
- **A small flow diagram** (e.g. wake-word -> STT -> Claude -> ElevenLabs TTS).
Keep prose minimal around the visual. If it needs material the agent didn't supply, ask the
`jarvis-expert` agent via a follow-up **Task** - don't invent canon or fabricate a quote.

### 8. Wrap up
- Recap from the helper (`jarvis_state.ps1 status` for the authoritative meter, `... next` for the
  next pick): which faculties are now **online** / **seeded**, the new meter, and what the next
  subsystem (and its first step) will be - so the next `/jarvis` picks up cleanly.
- Close in voice, with the **source URLs** behind the canon you acted on.
- If config files changed, remind the user to run `/backup-config` (and restart if an agent/skill
  was added, so it reloads).

## Rules
- **It's advice, not orders.** Present; the user accepts/rejects. Never build or flip a subsystem
  to `online` without an explicit Accept.
- **Honesty over theatre.** The reincarnation framing is fun, but every canon claim is sourced
  (`[verbatim]`/`[secondary]`/`[inference]`) and every build step is real. Never imply a faculty
  is online when it isn't, or fabricate a JARVIS quote.
- **The helper is the single source of truth + single writer.** All revival state goes through
  `skills/jarvis/jarvis_state.ps1` (status / next / validate / seed / flip / reset); the model
  never hand-edits `reincarnation.json` or the meter, and never lets the delegated agent write it.
- **Gate every build on dependencies, and never flip online without verifying the full realImpl**
  - use `seed` for first-step-only builds. The meter must never claim a faculty works when it doesn't.
- **Highest caution for security-control, global-config, and self-modifying builds** - preview the
  blast radius, get a second yes, back up + smoke-test, and prove any security control still blocks.
- **The voice tech is `elevenlabs-expert`'s.** Defer model/cloning/streaming detail to it.
- To refresh the underlying canon, tell the `jarvis-expert` agent to run **Mode B**.
