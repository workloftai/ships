import { expect, mock, test } from 'claude-code/testing'
import { countAgents, parseFeed, resolveArgv } from '../hooks/register.js'

const FEED = JSON.stringify({
  title: 'LOOP',
  segments: [
    { label: 'research', value: 37 },
    { label: 'ship', value: 0 },
    { label: 'blocked', value: 9, alert: true },
  ],
  detail: '## board detail',
})

const BAND = {
  plugin: 'status-band',
  component: 'AbovePrompt',
  surface: 'terminal',
  viewport: { columns: 120, rows: 40 },
  props: { hasSurvey: false, isWorking: false, maxRows: 4, bodyColumns: 116, scroll: { offset: 0, bodyRows: 4 }, view: {} },
} as const

// The stubs every session-start test needs
function boot(on: any, opts: { stdout?: string; exitCode?: number; agents?: unknown[] } = {}) {
  const clock = mock.clock(on)
  mock.env(on, { STATUS_BAND_CMD: '["python3","loop_board.py","band-json"]' })
  const argvSeen: string[][] = []
  on('process.run', ($: any, e: any) => {
    argvSeen.push(e.argv)
    return { value: { exitCode: opts.exitCode ?? 0, stdout: opts.stdout ?? FEED, stderr: 'boom' } }
  })
  on('agent.list', () => ({ value: opts.agents ?? [] }))
  on('command.register', () => ({ value: undefined }))
  on('session.start', () => ({ cwd: '/work' }))
  // What Claude Code (and other mods) would draw in the band
  on('ui.render', () => ({ type: 'Box', props: {}, children: [] }))
  return { clock, argvSeen }
}

test('parseFeed keeps segments and rejects junk', () => {
  expect(parseFeed(FEED).segments.length).toBe(3)
  expect(parseFeed(FEED).segments[2].alert).toBe(true)
  expect(() => parseFeed('{"title":"x"}')).toThrow()
})

test('countAgents buckets statuses', () => {
  const c = countAgents([
    { status: 'running' }, { status: 'pending' }, { status: 'completed' },
    { status: 'idle' }, { status: 'failed' },
  ])
  expect(c).toEqual({ live: 2, done: 2, failed: 1 })
})

test('resolveArgv prefers userConfig, falls back to env JSON', () => {
  expect(resolveArgv(['gary', 'board'], '["x"]')).toEqual(['gary', 'board'])
  expect(resolveArgv([], '["x","y"]')).toEqual(['x', 'y'])
  expect(resolveArgv([], 'not json')).toEqual([])
  expect(resolveArgv(undefined, undefined)).toEqual([])
})

test('band draws the feed segments after session start', async ($, on) => {
  const { argvSeen } = boot(on)
  await $.session.start({ surface: 'terminal', isInteractive: true, cwd: '/work' })
  expect(argvSeen[0]).toEqual(['python3', 'loop_board.py', 'band-json'])
  const ui = await $.ui.mount(BAND)
  expect(await ui.find({ type: 'Text', text: 'LOOP' })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: 'research 37' })).toBeDefined()
  const blocked = await ui.find({ type: 'Text', text: 'blocked 9' })
  expect(blocked?.props.color).toBe('red')
  await ui.unmount()
})

test('a failing feed keeps the last good data and marks it stale', async ($, on) => {
  let fail = false
  const clock = mock.clock(on)
  mock.env(on, { STATUS_BAND_CMD: '["feed"]' })
  on('process.run', () => ({ value: fail ? { exitCode: 2, stdout: '', stderr: 'db down' } : { exitCode: 0, stdout: FEED, stderr: '' } }))
  on('agent.list', () => ({ value: [] }))
  on('command.register', () => ({ value: undefined }))
  on('session.start', () => ({ cwd: '/work' }))
  on('ui.render', () => ({ type: 'Box', props: {}, children: [] }))
  await $.session.start({ surface: 'terminal', isInteractive: true, cwd: '/work' })
  fail = true
  await clock.advance(60_000)
  const ui = await $.ui.mount(BAND)
  expect(await ui.find({ type: 'Text', text: 'research 37' })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: 'stale' })).toBeDefined()
  await ui.unmount()
})

test('subagent counts appear once agents exist', async ($, on) => {
  const { clock } = boot(on, { agents: [{ status: 'running' }, { status: 'completed' }] })
  await $.session.start({ surface: 'terminal', isInteractive: true, cwd: '/work' })
  await clock.advance(2_000)
  const ui = await $.ui.mount(BAND)
  expect(await ui.find({ type: 'Text', text: 'agents 1 running · 1 done' })).toBeDefined()
  await ui.unmount()
})

test('/band refreshes and prints the detail', async ($, on) => {
  boot(on)
  await $.session.start({ surface: 'terminal', isInteractive: true, cwd: '/work' })
  const answer = await $.command.run({ command: 'band', args: '' })
  expect(answer.text).toMatch(/^## board detail/)
})

test('no command set says so in the band', async ($, on) => {
  mock.clock(on)
  mock.env(on, {})
  on('agent.list', () => ({ value: [] }))
  on('command.register', () => ({ value: undefined }))
  on('session.start', () => ({ cwd: '/work' }))
  on('ui.render', () => ({ type: 'Box', props: {}, children: [] }))
  await $.session.start({ surface: 'terminal', isInteractive: true, cwd: '/work' })
  const ui = await $.ui.mount(BAND)
  expect(await ui.find({ type: 'Text', text: /no feed command set/ })).toBeDefined()
  await ui.unmount()
})
