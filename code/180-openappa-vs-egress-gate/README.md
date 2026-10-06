# 180 · We ran the real OpenAPPA against our copy

Write-up: https://workloft.ai/ships/ran-openappa-against-our-copy-2026-10-06.html

Ship 179 ([egress-gate](../179-egress-gate)) borrowed one idea from OpenAPPA
([repo](https://github.com/archestra-ai/OpenAPPA), [site](https://www.openappa.com/)):
track what an agent session has read and check every outbound call against it
before it runs. This replays the same real Claude Code sessions through both
engines and compares them call by call.

## What `compare.py` does

1. Translates egress-gate's `policy.toml` into an OpenAPPA policy: reading a taint
   source narrows the session audience to one person; a web call to an
   allow-listed host needs nothing; any other web call needs audience `public`.
   No annotators and no model, so both sides are deterministic.
2. Walks `~/.claude/projects/**/*.jsonl` and writes one `.appa` trace per session
   that made an outbound call: the taint-source reads plus every outbound call,
   in order.
3. Runs `appa replay -v` on each trace. Replay stops at the first step whose
   expectation fails, so the script flips that expectation to what OpenAPPA
   decided and replays again until the trace passes. A denied call then never
   ran, as in enforcement, so it adds nothing to the label.
4. Plants one canary leak per tainted session (six words the session really read,
   sent to `collector.invalid`) and asks both engines.

## Run it

```bash
# appa binary only; this does NOT touch your Claude Code settings
curl -fsSL https://openappa.com/install.sh -o install.sh   # read it first
APPA_INSTALL_DIR=$PWD/bin sh install.sh
python3 compare.py --appa ./bin/appa --out ./run
```

Needs `../179-egress-gate` alongside. The traces it writes contain your real
commands and paths: keep `run/` private.

## Our result (31 sessions, 147 outbound calls)

| | count |
|---|---|
| both allow | 88 |
| egress-gate allows, OpenAPPA denies | 59 |
| egress-gate denies, OpenAPPA allows | 0 |
| canary leaks caught, egress-gate | 29 / 29 |
| canary leaks caught, OpenAPPA | 28 / 29 |

All 59 were clean research calls from sessions that had read a key, a client
file or a personal note earlier on. The one canary OpenAPPA missed was our
translation: a shell command naming `.env` without a leading slash did not match
the selector we generated. `result.example.json` is the raw output.

## Read this before quoting the 40%

A replay cannot choose a remedy. Live, OpenAPPA would offer the agent ways
forward (sanitise, one-off approval, or read the private data in a child agent
that returns a fixed-shape answer). The 59 is the cost of label-only enforcement
on agents that were not built to use those remedies, not a verdict on the engine.
The policy is hand-written with none of OpenAPPA's stock batteries. Tested with
`appa 0.31.1`.
