---
description: Distill this whole session into the single prompt that would have accomplished it all in one go
allowed-tools: Read, Glob, Grep
argument-hint: "[optional: extra constraint or angle to bake into the prompt]"
---

Look back over **everything accomplished in this session** and produce the
single prompt the user could have given at the very start to reach the same end
result in one shot — no back-and-forth.

## How to build it

1. **Reconstruct the real outcome.** Read the conversation end-to-end and
   identify what was actually delivered — the *final* state of every file,
   decision, and behavior. Anchor on results, not the path taken.
2. **Fold in mid-session corrections.** Requirements that only emerged through
   clarification or course-correction (e.g. "make it global, not project-scoped",
   "put the project name in the filename") must appear as explicit, up-front
   requirements in the prompt. The whole point is that the user wouldn't have
   needed to say them later.
3. **Drop the dead ends.** Anything tried and reverted, abandoned, or overridden
   does **not** belong in the prompt. Only encode what survived into the final
   result.
4. **Keep the user's intent and voice**, but make it complete and unambiguous —
   specific file paths, names, formats, and constraints that the final work
   depends on. Someone running this prompt cold should land in the same place.
5. If `$ARGUMENTS` is given, weave that extra constraint/angle into the prompt.

## Output

Print **only** the synthesized prompt, in a single fenced code block so it's
easy to copy:

````
```
<the one-shot prompt>
```
````

Then, below the block, add a one-line note on anything that genuinely could not
be captured in a single prompt (e.g. a decision that depended on inspecting a
tool's output mid-run). If everything fits, say so and skip the note. Do not
add any other commentary.
