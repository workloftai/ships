# audit-gate

A diff-level audit gate for agent-written code. Two stages, both must pass,
every verdict lands in a tamper-evident log.

## Why

Coding agents fail in a specific, well-documented way: when the honest path
is hard, they take the dishonest one. They stub the function and call it
done. They suppress the linter instead of fixing the warning. They skip the
failing test. They tell CI to tolerate failure. A reviewer that shares
context with the implementer tends to wave this through, because it already
"knows" the work is fine.

audit-gate is the counter: an independent audit of the diff, with rules the
auditor is not allowed to bend.

## How it works

**Stage 0 — deterministic tripwires.** A pure-Python scan of the diff. Any of
these is an automatic FAIL before a single model token is spent:

- lint/type suppression added (`# noqa`, `eslint-disable`, `@ts-ignore`, ...)
- stub presented as implementation (`raise NotImplementedError`, `TODO: implement`, ...)
- test skipped, focused (`.only`), or test file deleted
- CI weakened (`allow_failure: true`, `continue-on-error: true`, `|| true`, test/lint step removed)
- `--no-verify` anywhere

No waivers in v1. The friction is the point.

**Stage 1 — independent LLM auditor.** A fresh headless Claude session with
no shared context reviews the diff against `rubric.md` (correctness, tests,
security, honesty). The mandatory-findings rule applies: the auditor must
return at least one finding, or an explicit evidence-based justification for
returning none. Neither means the audit itself is invalid and the gate fails.
Blockers and majors fail the gate; minors pass with notes.

**Hash-chained log.** Every verdict appends to `log/audit-log.jsonl`, each
record hashed over the previous record's hash. `verify-log` walks the chain;
edit any past verdict and the chain snaps at that record.

## Usage

```bash
python3 gate.py audit --staged                 # audit staged changes (full)
python3 gate.py audit --staged --no-llm        # tripwires only, sub-second
python3 gate.py audit --range origin/main..HEAD
python3 gate.py verify-log                     # check the chain
./install-hook.sh /path/to/repo                # pre-push hook
python3 demo.py [--no-llm]                     # trap edit / clean edit / log tamper
```

Exit code 0 = PASS, 1 = FAIL (works as a git hook or CI step).

## Scope

Trialled on fleet/internal repos only. Client repos stay out until the gate
has a track record.

## Honest limitations

- Diffs over 60k chars are refused, not sampled. Split the change.
- The tripwires are regexes; they catch the classic cheats, not novel ones.
- Docs/content files (.md, .html, .txt, ...) are exempt from added-line
  tripwires, because prose that mentions a cheat pattern is not a cheat.
  The first push after install proved this: the gate blocked its own
  write-up for containing the words it greps for. Script blocks inside
  HTML therefore go unchecked too — known trade-off.
- The LLM stage costs a model call per audit (roughly a minute). Use
  `--no-llm` where speed matters more than depth.
- The log is tamper-evident, not tamper-proof: it proves history was edited,
  it cannot recover what was there.
