// status-band: a one-line band above the prompt, fed by any command that
// prints JSON, plus a live count of this session's subagents.

// Statuses that count as "still working"
const LIVE = ['pending', 'running', 'waiting']

// What the band shows, shared by the hooks below
let feed = null // last good feed: { title, segments, detail }
let feedError = '' // why the last run failed, if it did
let lastRun = 0 // ms timestamp of the last successful run
let agents = { live: 0, done: 0, failed: 0 }

// Parse and sanity-check the feed command's stdout
export function parseFeed(stdout) {
  const d = JSON.parse(stdout)
  if (!d || !Array.isArray(d.segments)) throw new Error('feed JSON has no segments array')
  return {
    title: String(d.title || 'STATUS'),
    segments: d.segments.map(s => ({
      label: String(s.label),
      value: s.value,
      alert: Boolean(s.alert),
    })),
    detail: typeof d.detail === 'string' ? d.detail : '',
  }
}

// Count subagents by status
export function countAgents(list) {
  const out = { live: 0, done: 0, failed: 0 }
  for (const a of list || []) {
    if (LIVE.includes(a.status)) out.live += 1
    else if (a.status === 'completed' || a.status === 'idle') out.done += 1
    else if (a.status === 'failed' || a.status === 'killed') out.failed += 1
  }
  return out
}

// Run the feed command and keep the result
async function refresh($, argv) {
  if (!argv || argv.length === 0) {
    feedError = 'no feed command set (pluginConfigs → command)'
    $.ui.invalidate('ui.render')
    return
  }
  try {
    const r = await $.process.run(argv, { timeoutMs: 20_000 })
    if (r.exitCode !== 0) throw new Error('exit ' + r.exitCode + ': ' + r.stderr.slice(0, 120))
    feed = parseFeed(r.stdout)
    feedError = ''
    lastRun = await $.clock.now()
  } catch (err) {
    // Keep the last good feed on screen, and say it's stale
    feedError = String((err && err.message) || err).slice(0, 120)
  }
  $.ui.invalidate('ui.render')
}

// Re-read this session's subagents; redraw only when the counts change
async function pollAgents($) {
  try {
    const next = countAgents(await $.agent.list())
    if (next.live !== agents.live || next.done !== agents.done || next.failed !== agents.failed) {
      agents = next
      $.ui.invalidate('ui.render')
    }
  } catch {
    // $.agent.list can be refused by a policy mod; the band just omits agents
  }
}

// The feed command: the userConfig list, else STATUS_BAND_CMD as a JSON array
export function resolveArgv(configured, envValue) {
  if (Array.isArray(configured) && configured.length > 0) return configured.map(String)
  if (!envValue) return []
  try {
    const parsed = JSON.parse(envValue)
    return Array.isArray(parsed) ? parsed.map(String) : []
  } catch {
    return []
  }
}

export function register(on, options) {
  const everyMs = Math.max(10, Number(options && options.interval_seconds) || 60) * 1000
  let argv = []

  on('session.start', async ($, e, next) => {
    argv = resolveArgv(options && options.command, await $.env.get('STATUS_BAND_CMD'))
    await refresh($, argv)
    $.clock.every(everyMs, () => refresh($, argv))
    $.clock.every(2_000, () => pollAgents($))
    try {
      await $.command.register({
        name: 'band',
        description: 'Refresh the status band and print its detail',
        immediate: true,
      })
    } catch {
      // A taken name shouldn't stop the band from drawing
    }
    return next(e)
  })

  // A new subagent: redraw now rather than at the next poll
  on('agent.spawn', async ($, e, next) => {
    const result = await next(e)
    pollAgents($)
    return result
  }).catch(async ($, e, next) => next(e)) // never block a subagent over a redraw

  on('command.run', { command: 'band' }, async ($) => {
    await refresh($, argv)
    if (!feed) return { text: 'status-band: no data yet. ' + feedError }
    const age = Math.round(((await $.clock.now()) - lastRun) / 1000)
    return { text: (feed.detail || 'No detail in feed.') + '\n\n(refreshed ' + age + 's ago)' }
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const { Box, Text } = $.ui.resolve(e)
    // Keep whatever other mods draw in the band
    const others = await next(e)
    const parts = []

    if (feed) {
      parts.push(Text({ bold: true, children: [feed.title] }))
      feed.segments.forEach(s => {
        parts.push(
          Text({
            color: s.alert ? 'red' : undefined,
            dimColor: !s.alert && !s.value,
            children: [s.label + ' ' + s.value],
          }),
        )
      })
    } else {
      const why = feedError || 'waiting for first feed…'
      parts.push(Text({ dimColor: true, children: ['status-band: ' + why] }))
    }

    if (feedError && feed) parts.push(Text({ color: 'yellow', children: ['stale'] }))

    const total = agents.live + agents.done + agents.failed
    if (total > 0) {
      parts.push(Text({ dimColor: true, children: ['│'] }))
      parts.push(
        Text({
          bold: agents.live > 0,
          children: [
            'agents ' + agents.live + ' running · ' + agents.done + ' done' +
              (agents.failed ? ' · ' + agents.failed + ' failed' : ''),
          ],
        }),
      )
    }

    const band = Box({ key: 'status-band', flexDirection: 'row', columnGap: 2, children: parts })
    if (!others) return band
    return Box({ flexDirection: 'column', children: [band, others] })
  })
}
