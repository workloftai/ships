export const meta = {
  name: 'parallel-write-merge',
  description: 'Swarm-safe multi-agent WRITE fan-out: one git worktree per writer (isolation) + one deterministic conflict-resolving merge/verify step. The write-half companion to coordinated-fanout. Built against the Anthropic swarm turf-war study.',
  phases: [
    { title: 'Setup', detail: 'coordinator creates repo + one worktree/branch per writer' },
    { title: 'Write', detail: 'one isolated agent per disjoint task, commits to its own branch' },
    { title: 'Merge', detail: 'single deterministic merge of every branch + verify (no agent fights)' },
  ],
}

// The COORDINATOR is this deterministic script; the swarm study's core failure was
// many agents mutating ONE shared tree and clobbering each other (lost updates,
// hidden edits, sabotage). We remove the shared state entirely: every writer gets
// its OWN worktree + branch, so no two writers can ever touch the same working
// copy. Contention is deferred to ONE explicit merge step — the arbitration point.
// args may arrive parsed or as a JSON string; accept both.
const _a = (typeof args === 'string') ? JSON.parse(args) : (args || {})
const REPO = _a.repo                       // path to a git repo (NEVER conexus)
const TARGET = _a.target || 'calc.py'      // the shared file writers all edit
const VERIFY = _a.verify || `python3 test_${TARGET.replace(/\.py$/, '')}.py`
const TASKS = _a.tasks || []               // [{ key, brief }] — each a disjoint edit
if (!REPO || !TASKS.length) {
  throw new Error('pass args: { repo: "/abs/path", target?, verify?, tasks: [{key, brief}] }')
}

const SETUP_SCHEMA = {
  type: 'object',
  properties: {
    ok: { type: 'boolean' },
    base_branch: { type: 'string' },
    worktrees: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          key: { type: 'string' },
          path: { type: 'string' },   // isolated worktree dir for this writer
          branch: { type: 'string' }, // its own branch off base
        },
        required: ['key', 'path', 'branch'],
      },
    },
    note: { type: 'string' },
  },
  required: ['ok', 'base_branch', 'worktrees'],
}

const WRITE_SCHEMA = {
  type: 'object',
  properties: {
    key: { type: 'string' },
    committed: { type: 'boolean' },
    branch: { type: 'string' },
    summary: { type: 'string' },
  },
  required: ['key', 'committed', 'branch'],
}

const MERGE_SCHEMA = {
  type: 'object',
  properties: {
    merged_branches: { type: 'array', items: { type: 'string' } },
    conflicts_resolved: { type: 'integer' },
    verify_passed: { type: 'boolean' },
    verify_output: { type: 'string' },
    edits_landed: { type: 'integer' },
    edits_expected: { type: 'integer' },
    summary: { type: 'string' },
  },
  required: ['merged_branches', 'verify_passed', 'edits_landed', 'edits_expected'],
}

log(`Parallel write-merge: ${TASKS.length} isolated writers over ${REPO}/${TARGET}`)

// ---- Phase 1: Setup. One agent, deterministic git plumbing, owns the split. ----
phase('Setup')
const setup = await agent(
  `You are the COORDINATOR's setup step for a swarm-safe parallel-write run. Do ONLY this, ` +
  `then return the structured result:\n` +
  `1. cd "${REPO}". Confirm it is a git repo with a clean tree (git status). If not a repo, ` +
  `   git init, add a .gitattributes line "${TARGET} merge=union", commit everything as "base".\n` +
  `   ALWAYS ensure ".gitattributes" contains "${TARGET} merge=union" and is committed — that ` +
  `   union driver is the deterministic conflict resolver for additive edits.\n` +
  `2. Note the base branch name (main or master).\n` +
  `3. For EACH task key [${TASKS.map((t) => t.key).join(', ')}], create an isolated worktree ` +
  `   at "${REPO}/../wt-<key>" on a NEW branch "w/<key>" off the base branch:\n` +
  `     git worktree add -b w/<key> <path> <base>\n` +
  `Return every worktree's key, absolute path, and branch. Do NOT edit ${TARGET} yourself.`,
  { label: 'setup', phase: 'Setup', schema: SETUP_SCHEMA },
)
if (!setup || !setup.ok) throw new Error('setup failed: ' + JSON.stringify(setup))
const byKey = Object.fromEntries(setup.worktrees.map((w) => [w.key, w]))

// ---- Phase 2: Write. Each agent is ISOLATED in its own worktree + branch. ----
// A writer physically cannot see or clobber another writer's work — the shared
// tree that made the swarm sabotage each other simply does not exist here.
phase('Write')
const writes = await parallel(TASKS.map((task) => () => {
  const wt = byKey[task.key]
  if (!wt) return Promise.resolve(null)
  return agent(
    `You are an ISOLATED writer. Your ONLY workspace is the worktree "${wt.path}" on branch ` +
    `"${wt.branch}". Do NOT cd anywhere else; another agent owns every other worktree.\n\n` +
    `Your single disjoint task: ${task.brief}\n\n` +
    `Edit ONLY "${wt.path}/${TARGET}" to accomplish it, then, inside "${wt.path}":\n` +
    `  git add -A && git commit -m "${task.key}"\n` +
    `Do not merge, rebase, or touch any other branch. Return whether you committed.`,
    { label: `write:${task.key}`, phase: 'Write', schema: WRITE_SCHEMA },
  )
}))
const committed = writes.filter(Boolean).filter((w) => w.committed)
log(`${committed.length}/${TASKS.length} writers committed to their own branch`)

// ---- Phase 3: Merge. ONE agent, ONE arbitration point. No two writers fight. ----
phase('Merge')
const merge = await agent(
  `You are the MERGE/ARBITRATION step — the ONLY place writer edits meet. In "${REPO}", on the ` +
  `base branch "${setup.base_branch}":\n` +
  `1. Sequentially merge each writer branch: ${committed.map((w) => w.branch).join(', ')}\n` +
  `     git merge --no-edit <branch>   (the "${TARGET} merge=union" driver auto-resolves ` +
  `     overlapping additive hunks; count how many merges reported a conflict/auto-resolve).\n` +
  `2. git worktree prune.\n` +
  `3. Run the verify command in "${REPO}": ${VERIFY}\n` +
  `4. Report: which branches merged, conflicts_resolved, whether verify passed (verbatim tail ` +
  `   of its output), and edits_landed vs edits_expected (${TASKS.length}). ` +
  `If verify FAILS, say so plainly — do not claim success.`,
  { label: 'merge+verify', phase: 'Merge', schema: MERGE_SCHEMA },
)

return {
  repo: REPO,
  target: TARGET,
  writers: TASKS.map((t) => t.key),
  committed: committed.map((w) => w.branch),
  merge,
  verified: !!(merge && merge.verify_passed),
}
