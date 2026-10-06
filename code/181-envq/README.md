# 181 · Ask about a key without reading it

Write-up: https://workloft.ai/ships/ask-about-a-key-without-reading-it-2026-10-06.html

`envq` is the confined read from OpenAPPA's playbook, without the engine. The
secret file is read by `envq`, not by the agent, and the agent only gets back a
fixed-shape answer. Secret values never reach its context, so
[egress-gate](../179-egress-gate) does not mark the session as having read secrets.

```
envq keys  [FILE...]          key NAMES in each env file
envq where KEY                which env files define KEY
envq has   KEY                "yes <file>" (exit 0) or "no" (exit 1)
envq len   KEY                length, plus a public prefix (sk-, ghp_, glpat-) if any
envq run [-f FILE]... -- CMD  run CMD with the keys loaded; every secret value in
                              its output is replaced by [KEY]
```

Files default to `secret_env_files` in `policy.toml`; add more with `-f`.

## What changed in egress_gate.py

- `confined_secret_read()`: a Bash call that is an `envq` call does not add the
  `secrets` label. `envq run -- CMD` may chain anything inside CMD, because its
  output is redacted. The other subcommands must stand alone: `envq keys; cat .env`
  still marks the session.
- Other labels are untouched: `envq run -- cat ~/call-transcripts/x.md` still
  marks the session client-confidential.
- The first time a session is marked `secrets`, the PostToolUse hook tells the
  agent about envq (`additionalContext`), once.

## Result on our own sessions

77% of the shell commands that marked a session as having read secrets (301 of
389) only needed a key name, a yes/no, or the key loaded to call an API.
Replaying with those through envq (`compare.py --assume-envq` in
[180](../180-openappa-vs-egress-gate)):

| | before | with envq |
|---|---|---|
| sessions marked | 29 | 25 |
| OpenAPPA blocks on clean calls | 59 | 51 |
| of which the session carried `secrets` | 42 | 26 |

The rest is mostly `personal`: files sent to the agent over Telegram. That is
a policy question, not a code one.

## Known gaps

- `envq run` redacts exact values of 8+ characters. A command that prints a
  transformed secret (base64, a slice, a hash) gets it through.
- It is a convention. An agent can still `cat .env`; the gate then marks the
  session as before, and the nudge tells it what to use next time.

Run the tests: `python3 -m pytest -q tests` (19 tests, 4 new).
