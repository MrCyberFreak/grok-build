# X-drive only - no C: access

## Policy

All Grok state, secrets, modules, temp files, and agent I/O stay on **X:\**.

| What | X: location | C: junction (redirect only) |
|------|-------------|---------------------------|
| Grok home | `X:\Grok_Build\.grok` | `%USERPROFILE%\.grok` |
| Claude profile | `X:\Grok_Build\.grok\claude-profile` | `%USERPROFILE%\.claude` |
| SecretStore vault | `X:\Grok_Build\.grok\secretmanagement` | `%LOCALAPPDATA%\Microsoft\PowerShell\secretmanagement` |
| PS modules | `X:\Grok_Build\.grok\powershell\Modules` | `%USERPROFILE%\Documents\PowerShell\Modules` |
| Temp | `X:\Grok_Build\.tmp` | `%TEMP%` / `%TMP%` (user env) |

Run `X:\Grok_Build\.grok\bootstrap-x-drive.ps1` after install or login to (re)apply junctions.

## Agent enforcement

- `config.toml` denies **all** Read/Edit/Write/Delete on `C:/**` and `X:/Claude_Code/**`
- `hooks/path-guard.ps1` blocks C:, user-profile paths, foreign X: trees, and `bootstrap-x-drive.ps1` (unless `.tmp\allow-c-drive-bootstrap` exists)
- Application code under `Projects/` must persist to project `.grok/` or `library/` on X: — never `%APPDATA%` or `Path.home()`
- Scripts use `$GROK_HOME` / `X:\Grok_Build\...` — never `expanduser("~")`, `$HOME`, or `%USERPROFILE%`

## bootstrap-x-drive.ps1

**User-only.** Agents never run it. Junction mode (touches C:) requires `.tmp\allow-c-drive-bootstrap`. `-EnvOnly` sets X: env vars without C: junctions.

## Claude Code tree

`X:\Claude_Code\` is **off limits**. Killswitch: `.tmp\allow-claude-code-access` only after explicit user OK in chat.

## Audit

```powershell
powershell -NoProfile -File X:/Grok_Build/.grok/scripts/c-drive-audit.ps1
```

## Allowed C: touch (non-agent)

- `bootstrap-x-drive.ps1` creating junctions (one-time redirect setup)
- Windows OS binaries on C: (not Grok state)