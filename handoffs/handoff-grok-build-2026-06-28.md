# Handoff — 2026-06-28

## Focus
Enforced strict separation of Git push locations: every project must use its own GitHub repository; global Grok harness changes only go to the grok-build repo. Updated /wrap, /backup-config, /safe-commit, scaffolding, templates, and global AGENTS.md with guards, routing, and documentation to prevent cross-contamination.

## State
- Version control: git repo on main (X:\Grok_Build is the grok-build repo)
- Working tree / files: Modified harness files (.gitignore, .grok/AGENTS.md, multiple .grok/skills/*SKILL.md); many untracked items under .grok/ and Projects/ as expected in the setup

## Done this session
- Added/enforced rule in .grok/AGENTS.md: projects push exclusively to own GH repos; global to grok-build only.
- Updated project-template/AGENTS.template.md with concrete repo conventions and gh create instructions.
- Enhanced .grok/skills/scaffold/SKILL.md and project-template/scaffold-project.ps1 to actively set up per-project GitHub remotes during scaffolding and document the URL.
- Overhauled .grok/skills/backup-config/SKILL.md: correct $GROK_ROOT, limit to .grok/ paths only, added root-vs-project guards, removed legacy Claude references.
- Updated .grok/skills/wrap/SKILL.md: clarified scopes (project repo vs grok-build), fixed global check logic.
- Updated .grok/skills/safe-commit/SKILL.md and /update-config with explicit refusal/routing for global vs project.
- Brought over and adapted hooks, refined .gitignore for the monorepo setup.
- Inspected all git/push functions to ensure correct target locations.

## In progress / not done
- /wrap itself (this handoff)
- Potential further testing of the new guards on actual project vs global scenarios
- Any remaining legacy path references in other skills/docs

## Key decisions & context
- Consolidated global harness in one grok-build repo; projects get their own to avoid "bunch of new repos" while keeping separation.
- Scaffolding is the enforcement point for future projects.
- All commits use `git commit -- <paths>` only; secret-scan before push.
- When CWD is project, git targets project remote; global operations must use workspace root + .grok/ filter.

## Next steps
- Review and approve the selective commit of harness changes to grok-build (see below).
- For any active Projects/, ensure they have their own remote set (use /scaffold or gh repo create if needed).
- Test /wrap and /backup-config from both project and global contexts.
- Update any user projects' AGENTS.md if they predate the new rule.

## Gotchas / open questions
- CRLF normalization warnings on Windows (git config core.autocrlf may help).
- Untracked items in status (normal for this harness setup; be selective).
- Ensure $GROK_ROOT = "X:\Grok_Build" is used consistently in global flows.
- If a project dir has no own .git, it may inherit root — scaffolding should prevent this.