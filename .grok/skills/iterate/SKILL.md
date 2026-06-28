---
name: iterate
description: Build or write anything in verified increments - build the smallest slice, self-check it, adjust, and repeat until it meets the bar. Use when building or changing code, a UI / page / component, a script, a tool, or a feature. For UI it renders the page headless, Reads the screenshot back, and critiques it; for logic it runs tests / typecheck / the app and reads the output. Self-checking is automatic - the build-verify gate hook soft-blocks finishing once big changes go unverified. NOT for one-shot read-only review of an existing diff (use code-review) or design direction before any code (use frontend-aesthetics).
---

# iterate - build in verified increments

A standing loop: never build a large batch and hope. Build the smallest reviewable
slice, prove it works (or see exactly how it fails), adjust, and repeat. Verify
**before** (does it already exist / what's the bar), **during** (each slice), and
**after** (the whole change). This is the default for any build/write task, not a
special mode.

This pairs with two hooks that make it automatic:
- `hooks/build-verify-record.ps1` (PostToolUse) accumulates how much code/UI changed
  without a verify, and resets when a verify command runs.
- `hooks/build-verify-gate.ps1` (Stop) soft-BLOCKS finishing once changes are *big*
  and still unverified (capped so it never hard-locks). Small edits never gate.

## The loop

1. **Set the bar (before).** State what "done and correct" means for this slice in
   one line - the observable outcome you'll check against (a route renders X, the
   test passes, the function returns Y, no console errors). Check prior art first
   (the standing rule) so you're not rebuilding something that exists.
2. **Build the smallest slice.** One coherent change you can verify now - not the
   whole feature. Smaller slice = sharper signal when it breaks.
3. **Self-check the slice (during).** Route by artifact - see the table below. Run
   the check and look at the ACTUAL output / screenshot, not your expectation of it.
4. **Critique honestly.** Compare what you observed against the bar from step 1.
   List what's wrong or missing. Be your own adversary - "does this actually meet
   it?" not "does this look plausible?".
5. **Adjust, then repeat 2-4** until the slice meets the bar with zero known defects.
6. **After the whole change:** do a final pass over the assembled result (re-render
   the key routes / re-run the suite), and `/code-review` the diff for bugs you
   introduced. Report what you verified and HOW, and flag honestly anything you
   could not confirm.

## Self-check routing - match the check to the artifact

| You changed... | Verify it by... |
|---|---|
| **A UI / page / component** | Render it headless and Read the screenshot back, then critique the visual against the brief. Use the helper below. Check the real routes/states, light + dark, and a narrow width. |
| **Generated single-file HTML** (embedded JS) | `visual-verify.ps1 -CheckHtml` (runs `node --check` on inline scripts + greps for expected content markers) THEN render it. Silent client-side breaks otherwise reach the user. |
| **Logic / a function / data layer** | Run the test suite (or write a focused test), or a quick Node/Python smoke run with stubbed I/O, and read the output. |
| **A running app (server/SPA)** | Start it, hit the real route, and screenshot/inspect it. Use the built-in `/run` and `/verify` skills to launch and drive it. |
| **A script / CLI / tool** | Execute it on a real input and show the actual output + exit code. Test the failure paths, not just the happy path. |
| **Config / hooks / harness** | Feed it a representative input (pipe a mock payload to a hook; load the JSON) and confirm the observed behavior, including the negative case. |

## Visual verification helper

`skills/iterate/scripts/visual-verify.ps1` - generalizes the proven headless
Edge/Chrome screenshot pattern into one reusable tool (works on this box with zero
installs; auto-detects Edge then Chrome).

```powershell
# Render a static prototype route to a PNG (then Read the PNG):
powershell -File skills/iterate/scripts/visual-verify.ps1 `
  -Url "X:/proj/prototype/index.html#/players" -Out "X:/proj/.tmp/players.png"

# Render a running dev server:
powershell -File skills/iterate/scripts/visual-verify.ps1 -Url "http://localhost:5173/#/overview"

# Static smoke-check a generated HTML file (catches silent JS breaks):
powershell -File skills/iterate/scripts/visual-verify.ps1 `
  -Url "X:/proj/out.html" -CheckHtml -Expect "Compose","Reports"
```

Options: `-Size 1440,900` (viewport), `-Wait 4000` (ms for JS to run),
`-Engine auto|edge|chrome`, `-Timeout 30000`. After a `RENDER OK -> <path>` line,
**Read that PNG** and critique it - the screenshot is the verification, not the
exit code. Exit codes: 0 ok, 2 bad input/missing file, 3 check failed, 4 no
browser, 5 launch/timeout, 6 no screenshot.

## Windows gotchas (already handled / watch for)

- The helper gives each render a unique `--user-data-dir` so concurrent verifies
  don't collide on a profile lock.
- After stopping a background dev server, the vite/node child can be orphaned and
  keep its port (drifts 5173 -> 5174). Free it before restart:
  `Get-NetTCPConnection -State Listen -LocalPort <port> | %{ Stop-Process -Id $_.OwningProcess -Force }`.
  A persistent `:4173` survivor across sessions is usually a detached pm2 daemon -
  tear it down scoped (`pm2 delete <name>` then `pm2 save --force`), never `pm2 kill`.
- Keep output paths space-free where you can; the helper URL-encodes file paths.

## Stopping rule

Stop iterating when the slice meets the bar with no known defects AND a fresh
verify of the assembled whole passes - not when it merely "looks done". If you
genuinely cannot verify something in this environment, say so explicitly and say
why, rather than implying it works.
