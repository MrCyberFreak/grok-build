---
name: user-stories
description: Write, split, or refine agile user stories with INVEST and acceptance criteria. Use when the user says 'write a user story', 'turn this requirement/feature into stories', 'split this story or epic', 'add acceptance criteria', 'is this story INVEST/ready', or 'refine this backlog item'. Produces well-formed stories ("As a <role>, I want <goal>, so that <benefit>") with Gherkin acceptance criteria and sensible splits. NOT for ordering/estimating a whole backlog (use backlog-refine), selecting a sprint's work (use sprint-plan), or generic methodology questions (delegate to the agile-expert subagent).
---

# Write / split / refine user stories

Produce small, valuable, testable user stories. For any exact definition (INVEST,
Definition of Ready vs Done, splitting patterns), delegate to the **`agile-backlog-expert`**
subagent — it reads the offline guides and cites sources; do not invent the canon.

## Procedure
1. **Clarify the need.** Who is the user/persona? What outcome do they want, and *why*
   (the benefit)? What constraints/edge cases exist? Ask before assuming.
2. **Write the story** in the canonical form:
   `As a <role>, I want <goal>, so that <benefit>.` The "so that" clause is mandatory —
   it carries the value.
3. **Apply INVEST** — Independent, Negotiable, Valuable (slice **vertically**, end-to-end,
   never by architectural layer), Estimable, Small, Testable. Flag any criterion the story
   fails and fix it.
4. **Add acceptance criteria** as Gherkin scenarios:
   `Given <context>  When <action>  Then <observable result>` (happy path + key error/edge
   paths). These are the "conditions of satisfaction" and become the tests.
5. **Split if too big** (won't fit comfortably in a Sprint). Use a recognised pattern:
   workflow steps · business-rule variations · happy vs error path · data
   variations/entry methods · simple-then-complex · CRUD operations · defer
   performance · defer platform/interface. Each split must still be a vertical,
   valuable slice.
6. **Output** each story with: title, the As-a/I-want/so-that line, acceptance criteria,
   and (if relevant) parent epic, notes/assumptions, and open questions. Offer to write
   them to a file or backlog if the user has one.

## Notes
- A story is "a promise of a conversation," not a full spec (Three Cs: Card, Conversation,
  Confirmation).
- **Definition of Ready** is a useful team checklist but is **not** part of the Scrum
  Guide — mention it as optional, not canon.
- Don't estimate or rank here — that's `backlog-refine`.
