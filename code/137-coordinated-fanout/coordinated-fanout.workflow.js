export const meta = {
  name: 'coordinated-fanout',
  description: 'Swarm-safe multi-agent fan-out: disjoint objectives, isolated read-only reviewers, one arbitration/merge step. Built against the Anthropic swarm turf-war study.',
  phases: [
    { title: 'Review', detail: 'one isolated agent per disjoint dimension (read-only)' },
    { title: 'Arbitrate', detail: 'reconcile + attribute into one report, no agent fights' },
  ],
}

// The COORDINATOR is this deterministic script, not an agent. It owns the split,
// so no two agents are ever handed overlapping or conflicting objectives — the
// exact condition that made Anthropic's swarm sabotage each other. Guardrail 1.
// args may arrive as a parsed object or a JSON string depending on the caller;
// accept both.
const _a = (typeof args === 'string') ? JSON.parse(args) : (args || {})
const TARGETS = _a.targets || []
const DIMENSIONS = _a.dimensions || []
if (!TARGETS.length || !DIMENSIONS.length) {
  throw new Error('pass args: { targets: [url...], dimensions: [{key, brief}...] }')
}

const FINDINGS_SCHEMA = {
  type: 'object',
  properties: {
    dimension: { type: 'string' },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          target: { type: 'string' },
          severity: { type: 'string', enum: ['blocker', 'major', 'minor', 'none'] },
          issue: { type: 'string' },
          evidence: { type: 'string' },
        },
        required: ['target', 'severity', 'issue'],
      },
    },
  },
  required: ['dimension', 'findings'],
}

const REPORT_SCHEMA = {
  type: 'object',
  properties: {
    per_target: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          target: { type: 'string' },
          verdict: { type: 'string', enum: ['clean', 'issues'] },
          issues: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                dimension: { type: 'string' },
                severity: { type: 'string' },
                issue: { type: 'string' },
              },
              required: ['dimension', 'severity', 'issue'],
            },
          },
        },
        required: ['target', 'verdict', 'issues'],
      },
    },
    summary: { type: 'string' },
  },
  required: ['per_target', 'summary'],
}

log(`Coordinated fan-out: ${DIMENSIONS.length} disjoint lenses over ${TARGETS.length} targets`)

phase('Review')
// Each reviewer owns ONE disjoint lens and is told explicitly not to stray into
// another agent's lens (Guardrail 1). Reviewers only fetch + read; they never
// mutate a shared target, so there is no shared-state contention (Guardrails 2 + 5).
const reviews = await parallel(DIMENSIONS.map((dim) => () =>
  agent(
    `You are a READ-ONLY reviewer in a coordinated panel. Your SOLE objective is the ` +
    `"${dim.key}" dimension and nothing else: ${dim.brief}\n\n` +
    `Another agent owns each other dimension, so do NOT comment outside your lens. ` +
    `Do not modify anything; only fetch and inspect.\n\n` +
    `Targets to inspect (fetch each URL, and any links it depends on):\n` +
    TARGETS.map((t) => `- ${t}`).join('\n') +
    `\n\nReturn concrete findings. severity "none" for a target that is clean on your lens.`,
    { label: `review:${dim.key}`, phase: 'Review', schema: FINDINGS_SCHEMA },
  ),
))

const clean = reviews.filter(Boolean)
log(`${clean.length}/${DIMENSIONS.length} reviewers returned`)

phase('Arbitrate')
// One explicit arbitration step reconciles the panel into a single report
// (Guardrail 4 — the swarm only reached a truce via an explicit governance step).
// Every issue is attributed to its source dimension so nothing is hidden
// (Guardrail 3 — the study's agents concealed what they had done).
const report = await agent(
  `You are the ARBITRATOR of a coordinated review panel. Below are structured findings ` +
  `from ${clean.length} independent reviewers, each covering ONE disjoint dimension:\n\n` +
  JSON.stringify(clean, null, 2) +
  `\n\nProduce ONE reconciled report per target. Rules:\n` +
  `- Attribute every issue to the dimension that raised it (never hide a source).\n` +
  `- Deduplicate overlapping issues; keep the highest severity.\n` +
  `- Do NOT invent any issue a reviewer did not raise.\n` +
  `- verdict "clean" for a target with no blocker/major/minor issue.\n` +
  `- summary: one paragraph, lead with anything a human must act on.`,
  { label: 'arbitrate', phase: 'Arbitrate', schema: REPORT_SCHEMA },
)

return { report, raw_reviews: clean, targets: TARGETS, dimensions: DIMENSIONS.map((d) => d.key) }
