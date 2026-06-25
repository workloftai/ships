# repro-triage

A cheap gate to run before you spend real time implementing a paper.

We keep a backlog of "implement this paper" tasks. The expensive part was never
typing the code, it was deciding which papers deserve the build at all. Hosted
agents like alphaXiv's autoarxiv now do the boring 80% (fix the repo setup, run
a minimal reproduction, estimate the full replication cost), but they sit behind
a login, so you cannot drop one into an automated pipeline. And reproduction is
not implementation: "the code ran" is not "the result matched".

So this is the part you *can* automate: a static, dependency-free scorer that
checks four cheap signals and recommends one of four actions.

| Signal | Question |
|---|---|
| `official_code` | Is there an official repo at all? |
| `env_pinned` | Is the environment pinned (requirements / lock / pyproject / env.yml)? |
| `runnable_entry` | Is there an obvious entrypoint or a tests directory? |
| `weight` | How heavy is full replication likely to be (repo size as a rough proxy)? |

| Action | When | Meaning |
|---|---|---|
| `BUILD` | signals 1-3 present, light/medium | worth a hand-build |
| `PROBE` | 1-3 present but heavy | run a minimal repro first (autoarxiv's job) |
| `PARK` | code exists, env or entry missing | setup archaeology; only if it matters |
| `KILL` | no official code | do not hand-build from the prose alone |

It does **not** claim a paper reproduces. That needs execution, which is the next
stage, not this one. This gate only decides whether that next stage is worth it.

## Use

```bash
python3 repro_triage.py owner/repo   # live check via the GitHub API (anonymous, rate-limited)
python3 repro_triage.py --demo       # bundled fixtures, no network
```

Standard library only. No install.

## Why it is this small

Because the value is in the decision, not the cleverness. A gate that needs a
login, an API key, or a GPU is a gate nobody runs. This one is ten seconds and
zero dependencies, which is the only kind that survives contact with a real
backlog.

Built by [Workloft](https://workloft.ai/labs/). Companion to the Labs Note
[*We tried to hand our paper backlog to a robot*](https://workloft.ai/labs/notes/paper-to-code-triage-2026-06-25.html).
