# Capability taxonomy (Grok branch)

Four names, **one execution model**. Everything delegates the same way.

## The four kinds

| Kind | What it is | On disk | How it runs |
|------|------------|---------|-------------|
| **Agent** | Domain expert or executor with a mandate + optional library | `$GROK_HOME/agents/<name>.md` | **Task** — read the `.md`, embed in prompt, `subagent_type: generalPurpose` (or `code-reviewer` for audit-only) |
| **Skill** | User-invoked workflow (`/name`) — procedure, loops, orchestration | `$GROK_HOME/skills/<name>/SKILL.md` | Parent session runs the skill; skill spawns **Task** when it needs an agent |
| **Persona** | Not a fourth file type — an **agent + skill pair** | `agents/<x>-expert.md` + `skills/<slash>/SKILL.md` | `/slash` skill owns UX → **Task** → `<x>-expert` |
| **Subagent** | Harness primitive OR any agent invoked via Task | Built-in: no file. Custom: same as **Agent** | **Task** with `subagent_type: explore \| plan \| generalPurpose \| code-reviewer` |

## Unified delegation (always)

```
1. Match request → agent description (auto) OR user runs /skill OR orchestrator chooses Task
2. Read .grok/agents/<name>.md (skip for built-in explore/plan/code-reviewer-only passes)
3. Task(
     subagent_type: generalPurpose | explore | plan | code-reviewer,
     prompt: "<full agent.md body + task context>"
   )
4. Parent synthesizes; skill may run accept/reject loops
```

**Never** use a separate "Agent tool" — Grok has **Task** only.

## Built-in subagent types

| `subagent_type` | Use when | Reads agent `.md`? |
|-----------------|----------|-------------------|
| `explore` | Read-only codebase search | No |
| `plan` | Implementation plan, no edits | No |
| `generalPurpose` | Custom experts, executors, persona experts | **Yes** — required |
| `code-reviewer` | Diff/PR review | Optional |

## Persona pattern (agent + skill)

| Slash skill | Expert agent | Library |
|-------------|--------------|---------|
| `/wwbd` | `boris-expert` | `library/boris/` |
| `/wwkd` | `karpathy-expert` | `library/karpathy/` |
| `/wwgd` | `garyvee-expert` | `library/garyvee/` |
| `/jarvis` | `jarvis-expert` | `library/jarvis/` |

- **Expert** = corpus + judgment (Mode A advise / Mode B refresh).
- **Skill** = user-facing ritual (capture situation, present suggestions, accept/reject/build).
- Scaffolding both: `/scaffold-expert` with `persona-advisor` type.

## Skill-only vs agent-only

| Pattern | Example | Why |
|---------|---------|-----|
| Skill only | `/handoff`, `/iterate`, `/scaffold` | Procedure on the session; no standing expert mandate |
| Agent only | `git-expert`, `pool-rating-systems-expert` | Routed by description; no dedicated `/slash` |
| Both | `/wwbd` + `boris-expert` | Expert for grounding; skill for interactive loop |

## Project-local overrides

Same layout under `<project>/.grok/`:

- `agents/<name>.md` — project expert (Task + read first)
- `skills/<name>/SKILL.md` — project slash command

Project agents override global when names collide; prefer unique names.

## Registration

All kinds appear in `$GROK_HOME/CAPABILITIES.md`:

- Agents → section 1 or 2
- Skills → section 3 (grouped)
- Personas → agent row + skill listed under **Persona**
- Subagent types → section 2 footer

Reconcile with `/sync-capabilities` after adds/removes.