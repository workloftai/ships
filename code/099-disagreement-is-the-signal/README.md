# disagreement-is-the-signal

**Two model bloodlines review the same diff. Trust where they agree. Look where they split.**

A panel of AI reviewers that all agree can be confidently, identically wrong,
because same-lineage models share blind spots: three near-identical jurors vote a
bug through and the confidence reads as signal when it is really one mistake
counted three times. The fix is not more jurors. It is a juror that fails
differently.

`disagree.py` runs two reviews over the same change:

- **Claude** (the author's lineage) via the Anthropic API.
- **Codex** (a GPT-family model) blind, read-only, with none of the reasoning.

Both are forced through the same strict schema, then reconciled into three
buckets:

```
CLAUDE + CODEX agree   -> trust it, act
CLAUDE only            -> Codex missed it, or Claude is over-flagging
CODEX only             -> Claude's blind spot, or Codex is over-flagging
```

The agreement is the part you can stop thinking about. The disagreement is the
only thing that needs a human's eyes: either a real bug the other lineage was
blind to, or a false alarm you dismiss in seconds.

## The one idea

A normal panel exists to collapse opinions into a verdict, usually by vote. Do
that for bug-finding and majority rule buries every finding only one reviewer
raised, which is exactly the wrong thing to drop: a defect one competent reviewer
sees and another misses is still a defect. Disagreement between two capable,
independent reviewers is not noise to average away. It is a map of where each one
is blind. So this tool refuses to average. It keeps the split and hands it over.

## Run it

```bash
# review a diff
git diff origin/main... | python3 disagree.py --stdin

# review specific paths (each lineage reads them itself, read-only)
python3 disagree.py --path src/api/handler.py --min-severity HIGH

# machine-readable
git diff | python3 disagree.py --stdin --json
```

Exit code is `2` when the two lineages disagree on anything at or above the gate
(the case worth a human glance), `0` when they fully agree.

## What a real run looked like

See [`evidence.txt`](evidence.txt). Both lineages caught a SQL injection and an
integer overflow; Claude alone caught a leaked DB connection, a stock race and
PII in the logs; Codex flagged nothing extra on that pass. The three CLAUDE-ONLY
findings are the review. The two AGREED are settled.

## Honest boundaries

- **Agreement is strong, not proof.** Two bloodlines can still share a blind
  spot, just far less often than one lineage consulted twice.
- **Non-deterministic.** A finding can move between buckets run to run. A single
  pass is a floor on what is wrong, never a ceiling.
- **The matcher is a heuristic.** "Same bug" is decided by file plus overlapping
  keywords (`same_bug`), not deep understanding, so it can occasionally split one
  bug or pair two that differ. Useful, and honest about being a heuristic.
- **It costs real money and minutes.** A cross-lineage run is tokens and about
  half a minute. Put it on diffs where being wrong is expensive (money, auth,
  data loss), not on formatting changes.

## Setup

Needs the `codex` CLI authenticated, and `ANTHROPIC_API_KEY` (env or a `.env`).
`codex_review.py` is included: `disagree.py` reuses its blind Codex path, schema
and `validate_finding`, and adds the Claude reviewer plus the reconcile step. On
a headless box, Codex's read-only sandbox needs user namespaces enabled
(`kernel.apparmor_restrict_unprivileged_userns=0` on Ubuntu 24.04).

## Companion

Pairs with the previous ship,
[reviewer-never-saw-the-reasoning](../098-reviewer-never-saw-the-reasoning),
which is the blind cross-lineage reviewer this one runs twice and reconciles.

Built by [Workloft](https://workloft.ai). Run by Alfred Churchill.
