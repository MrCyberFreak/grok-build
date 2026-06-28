export const meta = {
  name: 'gen-laymans',
  description: 'Generate the per-block LAYMANS twin (everyday-words, zero-jargon, analogy-driven) for an existing amplified-insights findings.json, index-aligned to the findings arrays.',
  phases: [{ title: 'Laymans', detail: 'three parallel re-voicers cover disjoint section groups' }],
}

// args.findings = absolute path to the corrected findings.json (agents Read it themselves).
const FP = (args && args.findings) || 'X:/Grok_Build/.grok/usage-data/.amplify/findings.json'

const RULES = `
LAYMANS re-voicing rules (this is NOT "plain English with jargon defined" - it is genuinely laymans):
Write for a smart but NON-technical reader who does NOT know what a hook, an agent, a CLAUDE.md, a
commit, frontmatter, or "PostToolUse" is.
- ZERO jargon. Do not name a technical term and define it - AVOID the term and use an everyday
  ANALOGY instead (e.g. not "a hook (an automatic check)" but "an automatic safety-catch, like a
  spell-checker that runs the instant you type"). If a tool/agent name must appear, describe what
  it DOES in plain words.
- Say what it MEANS FOR THE USER, in the second person ("you"); for any problem or suggestion, say
  what they would DO about it - concrete.
- Keep the substance and the specific numbers, but TRANSLATE them (e.g. "88,461 added vs 3,821
  removed" -> "you pile on new code and almost never delete - about 23 new lines for every 1 you
  cut"). Do NOT invent and do NOT dumb down into vagueness; stay faithful to the finding.
- 2-4 short, readable sentences per twin. ASCII only (straight quotes, plain hyphens, no emoji).
Read the findings file at ${FP}. Return arrays INDEX-ALIGNED to the findings arrays: SAME ORDER and
SAME LENGTH as the corresponding findings array, one laymans twin per block.`

phase('Laymans')

const GROUP_A = {
  type: 'object', additionalProperties: false,
  required: ['headline', 'key_pattern', 'ecosystem_summary', 'overlaps', 'gaps', 'verify_loop', 'work_areas', 'usage_narrative'],
  properties: {
    headline: { type: 'string' }, key_pattern: { type: 'string' },
    ecosystem_summary: { type: 'string' }, overlaps: { type: 'string' },
    gaps: { type: 'string' }, verify_loop: { type: 'string' },
    work_areas: { type: 'array', items: { type: 'string' } },
    usage_narrative: { type: 'array', items: { type: 'string' } },
  },
}
const GROUP_B = {
  type: 'object', additionalProperties: false,
  required: ['wins', 'friction', 'recommendations'],
  properties: {
    wins: { type: 'array', items: { type: 'string' } },
    friction: { type: 'array', items: { type: 'string' } },
    recommendations: { type: 'array', items: { type: 'string' } },
  },
}
const GROUP_C = {
  type: 'object', additionalProperties: false,
  required: ['dead_capabilities', 'dropped', 'horizon'],
  properties: {
    dead_capabilities: { type: 'array', items: { type: 'string' } },
    dropped: { type: 'array', items: { type: 'string' } },
    horizon: { type: 'array', items: { type: 'string' } },
  },
}

const [a, b, c] = await parallel([
  () => agent(`${RULES}

COVER THESE BLOCKS (laymans twin for each):
- headline (string), key_pattern (string)
- ecosystem_summary = laymans twin of findings.ecosystem.summary
- overlaps = ONE laymans paragraph summarizing findings.ecosystem.overlaps (which helper tools
  overlap and what you'd do)
- gaps = ONE laymans paragraph for findings.ecosystem.gaps
- verify_loop = laymans twin of findings.verify_loop (what got fixed before vs what keeps coming
  back, and why)
- work_areas[] index-aligned to findings.work_areas (what each area of your work actually is)
- usage_narrative[] index-aligned to findings.usage_narrative (how you actually work)`,
    { schema: GROUP_A, label: 'laymans:A narrative', effort: 'high' }),

  () => agent(`${RULES}

COVER THESE BLOCKS (laymans twin for each):
- wins[] index-aligned to findings.wins (what is going well and why it matters to you)
- friction[] index-aligned to findings.friction (what goes wrong, what it costs you, in plain terms)
- recommendations[] index-aligned to findings.recommendations (each suggestion: what it is in
  everyday words, why it helps you, and what you'd be agreeing to if you Accept it)`,
    { schema: GROUP_B, label: 'laymans:B wins+friction+recs', effort: 'high' }),

  () => agent(`${RULES}

COVER THESE BLOCKS (laymans twin for each):
- dead_capabilities[] index-aligned to findings.ecosystem.dead_capabilities (which helper tools you
  built but never use, and whether to drop or keep them)
- dropped[] index-aligned to findings.dropped_as_satisfied (suggestions skipped because you already
  do them)
- horizon[] index-aligned to findings.horizon (things you could explore next)`,
    { schema: GROUP_C, label: 'laymans:C eco+dropped+horizon', effort: 'high' }),
])

return { ...(a || {}), ...(b || {}), ...(c || {}) }
