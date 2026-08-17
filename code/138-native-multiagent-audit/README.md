# native-multiagent-audit — what the harness now does for you, and what it doesn't

Claude Code grew a set of native multi-agent primitives across the 2.1.2xx
releases: sessions can [message each other](https://github.com/anthropics/claude-code/releases)
with `SendMessage` and discover each other with `ListAgents`, inbound messages
are run through the permission classifier before delivery, forked skills
background themselves, subagents nest, and the old 200-agent lifetime cap is
gone.

If you have been hand-rolling agent coordination, the obvious reaction is "great,
rip out my bespoke plumbing". That reaction is half right, and the wrong half is
expensive. This probe tells you which half.

## The one idea

"Agent plumbing" is really three different jobs, and only one of them is now
native:

1. **INGRESS** — getting an external event (a phone share-sheet, a webhook, a
   cron, an email watcher) *into* an agent. Native messaging is agent-to-agent
   only. It does **not** touch this. Your intake endpoint stays yours.
2. **AGENT to AGENT** — one session talking to another. This is the bucket the
   native primitives now own. `SendMessage` + `ListAgents` is the real
   replacement for a bespoke session-to-session message bus.
3. **FAN-OUT** — one task splitting into many coordinated sub-agents and merging
   back. The native primitives are the *substrate* (backgrounded forks, nesting,
   concurrency caps). Your orchestration script still sits on top and still earns
   its keep. It just needs to respect the new caps.

Retire the wrong bucket and you either break your own front door (ripping out
ingress because "messaging shipped") or you throw away orchestration the
primitives never replaced.

## Run it

```
python3 probe.py          # human table
python3 probe.py --json   # machine-readable, for a CI gate
```

Stdlib only, read-only, no network. It reads `claude --version` and your local
changelog, detects which primitives are present on *your* install, and prints a
keep / migrate / keep-and-tune verdict per bucket. Works on any machine with
Claude Code, not just ours.

## What it found on our box (probe-result.json)

Claude Code 2.1.228: every primitive present. The verdict that mattered for our
own fleet:

- **`send-to-bob` (a tailnet HTTP inbox on :8585)** is INGRESS — a phone
  share-sheet posting into a headless agent. Native messaging does not replace
  it. **Keep.** This is the trap: it *looks* like "an agent inbox", so it is the
  first thing you would wrongly delete.
- **Session-to-session wiring** is AGENT to AGENT. **Migrate** to `SendMessage`.
- **Our fan-out workflows** (coordinated-fanout, parallel-write-merge) are
  FAN-OUT. **Keep and tune** — they were already built on the native substrate;
  they just inherit the new concurrency and nesting caps.

The probe also caught its own bug on the first run: it reported the flagship
cross-session feature as absent because the detection string had a space where
the changelog has a backtick. A tool that quietly missed the one feature the
whole audit turns on would have been worse than useless, so the signature is now
pinned to a stable phrase from the release note. Detecting your own false
negative is the cheapest kind of honesty.

## What's still off

Detection keys on changelog phrasing, so a reworded release note can flip a
`yes` to a `?`; the signatures are chosen to be stable but they are not immune.
It reports *presence*, not *your configured caps* — it will tell you nesting is
available, not what `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` is set to in your
environment. And the migrate verdict is a pointer, not a migration: moving a live
message bus onto `SendMessage` is real work with real edge cases (agents that
are not Claude Code sessions at all, like a container or a bot on another
account, cannot be reached by `ListAgents` and stay on their own transport).

Part of the [Workloft Ships](https://workloft.ai/ships) log.
