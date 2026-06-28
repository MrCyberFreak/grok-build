---
name: windows-oom-pagefile-triage
description: Triage a Windows allocation-class crash when a local app or local-model script fails to allocate memory - 'mkl_malloc: failed to allocate', 'DLL load failed ... the paging file is too small', or MemoryError. Read-only checks AutomaticManagedPagefile + commit charge vs RAM + top consumers, says environment-vs-real code/hardware bug, and re-enables the page file only with consent (UAC + reboot). NOT packaging/scheduling (windows-delivery-engineer), NOT debugging the app's mic/STT/logic.
allowed-tools: Bash, Read, AskQuestion
argument-hint: [optional: the failing command/app to re-run after the fix]
---

# windows-oom-pagefile-triage - Windows out-of-memory / page-file triage

A local-inference / model app on Windows dies with an **allocation-class** error
(`mkl_malloc: failed to allocate`, `DLL load failed ... the paging file is too small`,
or a bare `MemoryError`). The symptom masquerades as an app / mic / code / hardware
bug, so the real cause - **page file disabled and/or commit charge near the commit
limit** under heavy multi-session load - gets re-diagnosed from scratch every time.
This skill runs a fixed read-only memory diagnostic, says whether it is an
**environment** problem or a **real** code/hardware one, and (only with consent) applies
the standard page-file fix, then re-verifies headroom.

## Hard rules (state them first, hold to them)

- **Read-only until consent.** Step 2 mutates nothing. Never change a system setting
  (page file, registry, services) without the user's explicit go-ahead in this turn,
  plus the UAC elevation prompt. No silent fixes.
- **Diagnose, do not debug the app.** This skill only rules the app's own code / mic /
  STT logic IN or OUT as the cause - it does not edit or debug it. If the verdict is a
  real code bug, hand that back to the user (or the right executor), do not fix it here.
- **ASCII-only output** (the console is cp1252; curly quotes / em-dashes / emoji throw
  `UnicodeEncodeError`). The helper script is already ASCII-safe.
- **Prove the fix, do not assume it.** Always re-read headroom after a change, and run
  the user's re-run command (if given) headlessly so before/after is shown, not claimed.

## 1. Confirm it is allocation-class

Check the error signature before anything else. This skill applies only when the failure
is a memory **allocation** failure - one of:

- `mkl_malloc: failed to allocate` (or another `*_malloc` / `MemoryError` from a native
  math / inference lib),
- `DLL load failed ... The paging file is too small for this operation to complete`,
- `OSError`/`ImportError` whose text mentions the **paging file** being too small,
- a bare Python `MemoryError` from a local-model / torch / numpy / Whisper script.

If the error is **not** allocation-class (a mic that captures no audio, a missing model
file, a CUDA/driver mismatch, an import unrelated to the paging file), STOP and say so -
this is not the right skill (see "When NOT to use this skill").

## 2. Diagnose (read-only)

Run the bundled read-only diagnostic via the Bash tool (Windows PowerShell pattern -
unsigned local `-File` runs need the policy flag, matching the house convention):

```
powershell -NoProfile -ExecutionPolicy Bypass -File \
  "X:\Grok_Build\.grok\skills\windows-oom-pagefile-triage\scripts\mem-triage.ps1" -TopN 8
```

It reads (and only reads):

- `Win32_ComputerSystem.AutomaticManagedPagefile` - is the automatic page file ON.
- `Win32_OperatingSystem` - `TotalVisibleMemorySize` (RAM), `FreePhysicalMemory`,
  `TotalVirtualMemorySize` (the **commit limit** = RAM + page file), `FreeVirtualMemory`
  (free commit). It computes **commit charge** = limit - free, and **commit %**.
- `Win32_PageFileUsage` - the page file(s), allocated / current / peak MB (EMPTY when the
  page file is disabled).
- the **top N processes by private (commit) bytes** - the heaviest consumers.

It uses `Get-CimInstance` throughout (the removed `Get-WmiObject` is not used for the
read path). It prints **signals** - `pagefile_present`, `automatic_managed`,
`no_pagefile_headroom` (no page file present OR commit limit ~= RAM),
`commit_near_limit` - plus a `verdict_hint`. Note: `AutomaticManagedPagefile` can read
**True while no page file is actually present** (just enabled, reboot pending), so trust
`pagefile_present` (the ground truth) over the auto flag. YOU make the final call in
step 3.

## 3. Classify - environment vs real bug

Read the diagnostic numbers and state the verdict with the actual figures:

- **ENVIRONMENT** (the common, re-diagnosed-every-time cause) when there is **no page
  file actually present** (`Win32_PageFileUsage` empty - this is the ground truth, even if
  `AutomaticManagedPagefile` reads True) **and/or** the **commit limit is only ~= RAM**
  (no page-file overflow) **and/or** commit charge is **near the commit limit** (little/no
  commit headroom). Here the allocation can fail no matter how clean the app code is - it
  is the box, not the bug.
- **NOT environment** when there is healthy commit headroom and a page file is present.
  Then it is a **genuine** cause - a real leak, **truly insufficient RAM** for the
  workload, or an actual code bug - and the fix below will NOT help. Say which, with the
  numbers, and hand it to the user / the right executor. Do not apply the page-file fix to
  paper over a real bug.

State the verdict plainly: "Environment: page file is OFF and commit is at NN% of the
limit (only X GB headroom) - that is why the allocation failed," or "Not environment:
N GB of commit headroom with a page file present - this is the app, look at <...>."

## 4. Fix - only if ENVIRONMENT and only with consent

Only when step 3 says environment AND the user agrees. Use **AskQuestion** to get an
explicit yes before changing anything. Two levers:

**(a) Re-enable the automatic page file (one UAC prompt).** This launches an *elevated*
Windows PowerShell 5.1 and sets `AutomaticManagedPagefile = $true`. In that elevated
shell `Get-WmiObject ... .Put()` is the working path for this setting (it needs
`SeCreatePagefilePrivilege`, hence `-EnableAllPrivileges` + elevation):

```
powershell -NoProfile -Command "Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile','-Command','$cs = Get-WmiObject Win32_ComputerSystem -EnableAllPrivileges; $cs.AutomaticManagedPagefile = $true; [void]$cs.Put(); Write-Host (\"AutomaticManagedPagefile -> \" + (Get-WmiObject Win32_ComputerSystem).AutomaticManagedPagefile)'"
```

The user will see ONE UAC prompt. If they decline elevation, nothing changes - report
that and stop.

**>>> IMPORTANT: this change requires a REBOOT to take effect. <<<** Re-enabling the
automatic page file does NOT raise the live commit limit until Windows restarts. Say this
explicitly - until the reboot, the box still has the same (too-small) commit limit and the
allocation can still fail.

**(b) Free committed memory now (no reboot, no elevation).** Recommend closing the
heaviest **non-essential** consumers from step 2's top-N list to claw back commit headroom
immediately - this is the only lever that helps before a reboot. Name the specific
processes from the diagnostic; let the user choose what is safe to close. Do not kill
processes for them without consent.

Never silently change a system setting. If the user declines, leave the box untouched and
report the diagnosis only.

## 5. Re-verify - prove it, do not assume it

After any change (or after the user closes consumers):

- Re-run the step-2 diagnostic and report **before/after** headroom (note that the
  page-file re-enable's effect on the commit limit shows up only after the reboot).
- If the user passed a **re-run command** (the failing app/script), run it **headlessly**
  via the Bash tool and report whether the allocation now succeeds - so the fix is proven
  against the real failure, not assumed.

## Output

A short brief: the error signature confirmed (step 1), the diagnostic numbers (step 2),
the **verdict** environment-vs-real with the figures (step 3), what (if anything) was
changed and that it needs a reboot (step 4), and the before/after re-verification (step 5).

## When NOT to use this skill

- **Packaging / scheduling / headless-hardening** a Windows app or PowerShell launcher
  (Scheduled Task, unattended-run reliability) -> `windows-delivery-engineer`.
- **A real app bug** - the mic captures no audio, the STT/recording code misbehaves, a
  missing model file, a driver/CUDA mismatch - debug the app, not the page file.
- **Model-side fitting** (reduce batch size, quantize to fit RAM), **hardware/RAM-purchase
  advice**, or **Linux/macOS memory tuning** - all out of scope.
