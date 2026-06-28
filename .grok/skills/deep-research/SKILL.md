---
name: deep-research
description: Multi-source cited research report on a topic - web search, official docs, papers, and recent posts - with sources, confidence labels, and a concise verdict. Use when the user wants deep research, a literature review, market scan, or "find out everything about X". NOT for "has someone already solved this engineering problem" (use already-solved) and NOT for searching the local codebase.
argument-hint: "[topic or question]"
---

# deep-research (Grok global)

Produce a **cited research report** on the user's topic.

## Procedure

1. **Clarify scope** if the question is ambiguous (one question max, then proceed).

2. **Search broadly** with WebSearch - official docs, standards, recent posts, primary sources. Prefer 2024-2026 material when freshness matters.

3. **Open top sources** with WebFetch. Quote or paraphrase with URLs.

4. **Synthesize** into sections:
   - Executive summary (3-5 sentences)
   - Key findings (bulleted, each with source)
   - Conflicts / open questions
   - Practical implications for the user's context (if known)
   - Sources (linked)

5. **Label confidence:** `high` (primary source), `medium` (reputable secondary), `low` (inference or stale).

## Hard rules

- Never present inference as fact - label it.
- Prefer primary sources over SEO summaries.
- ASCII-safe output in chat; URLs are fine.
- If the topic is a Grok/Claude harness question, also grep read-only library corpora at `X:\Grok_Build\.grok\library/`.