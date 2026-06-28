# Capability Index (Grok global)

Canonical inventory for Grok Build. **Read on demand** — do not `@`-import every turn.

- **Location:** `X:\Grok_Build\.grok\CAPABILITIES.md`
- **Agents:** `.grok/agents/`
- **Skills:** `.grok/skills/` + `.grok/bundled/skills/`
- **Libraries:** `.grok/library/`
- **Reconcile drift:** run `/sync-capabilities` after adding or editing agents/skills
- **Taxonomy:** `rules/05-capability-taxonomy.md` — agents, skills, personas, subagents use the same **Task** delegation model

---

## 0. How capabilities relate (read once)

| Kind | File | Invoked | Executes via |
|------|------|---------|--------------|
| **Agent** | `.grok/agents/<name>.md` | Auto-routing or orchestrator | **Task** + read agent file |
| **Skill** | `.grok/skills/<name>/SKILL.md` | `/name` | Session runs skill; skill **Task**s to agents when needed |
| **Persona** | agent + skill pair (e.g. `boris-expert` + `/wwbd`) | `/wwbd` etc. | Skill UX → **Task** → persona expert |
| **Subagent** | built-in types OR any agent | **Task** `subagent_type` | `explore` / `plan` / `generalPurpose` / `code-reviewer` |

**One rule:** custom experts always = read `.grok/agents/<name>.md` → **Task** with that body in the prompt. No separate agent primitive.

---

## 1. Expert agents + offline libraries

Delegate via **Task** after reading `.grok/agents/<name>.md`. Answer flow: grep `$GROK_HOME/library/<tool>/` first → live docs if stale (`_meta.json` `last_updated` > ~30 days).

| Agent | Covers | Library |
|-------|--------|---------|
| `grok-build-expert` | Grok Build CLI (config, skills, subagents, hooks, MCP) | `library/grok-build/grok-build.md` |
| `grok-expert` | xAI Grok models & API | `library/grok/grok.md` |
| `claude-code-expert` | Claude Code CLI/harness (reference) | `library/claude-code/claude-code.md` |
| `claude-expert` | Claude/Anthropic API & models | `library/claude/claude.md` |
| `claude-design-expert` | Claude Design canvas | `library/claude-design/claude-design.md` |
| `git-expert` | git CLI & workflows | `library/git/git.md` |
| `github-expert` | GitHub platform, gh, Actions | `library/github/github.md` |
| `huggingface-expert` | Hugging Face Hub & libraries | `library/huggingface/huggingface.md` |
| `frontend-design-expert` | UI/UX, Tailwind, a11y | `library/frontend-design/frontend-design.md` |
| `react-expert` | React, Vite, Next.js | `library/react/react.md` |
| `frontend-framework-expert` | Vue, Angular, Svelte, Solid | `library/frontend-framework/frontend-framework.md` |
| `web-deploy-expert` | PaaS deploy, CI/CD | `library/web-deploy/web-deploy.md` |
| `notion-expert` | Notion app & API | `library/notion/notion.md` |
| `mcp-expert` | MCP spec & SDKs | `library/mcp/mcp.md` |
| `obsidian-expert` | Obsidian plugins & API | `library/obsidian/obsidian.md` |
| `elevenlabs-expert` | ElevenLabs voice API | `library/elevenlabs/elevenlabs.md` |
| `desktop-ui-expert` | Desktop GUI framework selection | `library/desktop-ui/desktop-ui.md` |
| `agile-expert` | Agile umbrella | `library/agile/agile.md` |
| `scrum-expert` | Scrum framework | `library/scrum/scrum.md` |
| `sprint-expert` | Sprint facilitation | `library/sprint/sprint.md` |
| `kanban-expert` | Kanban flow | `library/kanban/kanban.md` |
| `agile-scaling-expert` | SAFe, LeSS, Nexus | `library/agile-scaling/agile-scaling.md` |
| `agile-metrics-expert` | Velocity, DORA, forecasting | `library/agile-metrics/agile-metrics.md` |
| `agile-backlog-expert` | Stories, refinement | `library/agile-backlog/agile-backlog.md` |
| `boris-expert` | WWBD persona | `library/boris/boris.md` |
| `karpathy-expert` | WWKD persona | `library/karpathy/karpathy.md` |
| `garyvee-expert` | WWGD persona | `library/garyvee/garyvee.md` |
| `jarvis-expert` | JARVIS revival advisor | `library/jarvis/jarvis.md` |
| `reddit-expert` | Reddit policy (vendored) | `library/reddit/reddit.md` |
| `pool-rating-systems-expert` | Pool data semantics | `library/pool-rating-systems-expert/` |
| `rating-systems-expert` | Rating theory (papers) | `library/rating-systems/rating-systems.md` |
| `tiktok-platform-monetization` | TikTok native monetization | `library/tiktok-platform-monetization/` |
| `faceless-content-strategy` | Faceless short-form growth | `library/faceless-content-strategy/` |
| `brand-deals-sponsorship` | Creator brand deals | `library/brand-deals-sponsorship/` |
| `digital-products-passive-income` | Digital product income | `library/digital-products-passive-income/` |
| `audience-analytics-growth` | Account analytics | `library/audience-analytics-growth/` |
| `creator-legal-compliance` | Creator legal basics | `library/creator-legal-compliance/` |
| `indie-product-gtm-strategist` | Indie product GTM | `library/indie-product-gtm-strategist/` |

All library paths resolve under `$GROK_HOME/library/` (grep, never read whole files).

## 2. Other global agents

| Agent | Use for |
|-------|---------|
| `code-explainer` | Trace flows across files (read-only) |
| `skill-scout` | Spot skill opportunities |
| `skill-builder` | Build skill from approved spec |
| `agentic-systems-architect` | Multi-agent architecture critic |
| `agent-eval-strategist` | LLM pipeline epistemics |
| `predictive-model-critic` | Tabular model audit |
| `opportunity-discovery-strategist` | Idea-engine meta-validity |
| `windows-delivery-engineer` | Windows packaging & scheduling |
| `python-data-engineer` | Python ETL executor |
| `scrape-resilience-engineer` | Scraper anti-bot resilience |
| `entity-resolution-engineer` | Record linkage / de-dup |
| `roster-steward` | Capability gap analysis |
| `indie-product-gtm-strategist` | Product GTM |
| `product-monetization-validator` | Pre-build demand test |
| `sales-outreach-closer` | Solo outbound sales copy |
| `data-acquisition-legal-risk-expert` | Scraping/data legal risk flags |

**Built-in Task types:** `explore`, `plan`, `generalPurpose`, `code-reviewer`

## 3. Skills (slash commands)

Global skills live in `.grok/skills/`. Invoke with `/name`.

**Session:** `handoff`, `handon`, `recover-session`, `distill`, `wrap`, `oneprompt`, `safe-commit`

**Build:** `iterate`, **`swarm-build`**, `frontend-aesthetics`, **`scaffold`**, `scaffold-expert`, `vendor-corpus`

**Orchestration (native):** **`council`**, **`insight-amplify`**

**Research:** `already-solved`, **`deep-research`**, `propagate`, `routing-audit`, `watch-review`

**Persona:** `wwbd`, `wwkd`, `wwgd`, `jarvis`, `grill-me`, `council`

**Agile:** `user-stories`, `sprint-plan`, `retro`, `backlog-refine`, `kanban-flow`

**Grok bundled:** `check-work`, `create-skill`, `help`, `docx`, `xlsx`, `pptx`, `code-review`, `imagine`

**Grok harness:** `update-config`, `verify`, `run`, `simplify`, `sync-capabilities`, `backup-config`

**Cherry-picked:** `security-review`, `init-repo`, `repo-doctor`, `stack-check`, `humanizer`, `planning-with-files`, `security-awareness`, `session-report`, `frontend-design`, `agents-md-improver`

**MCP:** `reddit` (stdio via `.grok/scripts/reddit-mcp-launch.cmd`)

## 4. Hooks (Grok)

Loaded from `.grok/hooks/grok-hooks.json`. Scripts under `.grok/hooks/`.

## 5. Maintenance

After adding/removing agents or skills, run `/sync-capabilities` and update `rules/02-capabilities-routing.md`.