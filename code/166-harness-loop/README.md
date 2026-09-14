# harness-loop

A self-improving loop that reads an agent's own failure log, finds the
instruction most tied to the failures, and proposes a rewrite grounded in the
failing traces. It never edits a live instruction. It writes a gated proposal
for a human to accept.

Three research results converged on the same point in one week: the wrapper
around the model (the instruction, the retrieval, the output contract) is a
bigger lever on reliability than the model itself. The obvious next move is to
close the loop: let the agent read its own failures and rewrite the instruction
that caused them. The non-obvious part is where to stop.

## The result

The demo runs a real, deliberately weak actor (Claude Haiku) on a UK postcode
extraction task. The starting instruction is vague. The model is not.

```
model unchanged (claude-haiku-4-5).
harness only: 0/15 -> 15/15 passed.
```

Same model, same 15 inputs. The only thing that changed was one rewritten
instruction, and the loop proposed the rewrite from the failing traces.

The failures are the interesting part. Haiku had the right postcode every single
time. The vague instruction just let it wrap the answer in prose ("The postcode
in the text is **SW1A 2AA**.") so an exact-match check threw it away. That is the
ordinary shape of a harness failure: the model knows, the wrapper loses it. Feed
those traces back and the fix writes itself.

## The design decision that matters

The loop can read your instructions. It can only write to `proposals/`. It
refuses any path outside that directory.

An instruction the agent can silently rewrite is not an instruction, it is a
suggestion. If a self-improving loop could edit its own live guardrails, the
first bad rewrite is permanent and the loop has no floor. Worse, a persistent
memory an agent writes to is a live attack surface: context poisoning is exactly
the trick of planting a bad instruction for later execution. So the third step of
this loop is a human, on purpose. The agent proposes; a person applies.

This is the same principle as ship 165 (self-tamper-guard): a control that lives
somewhere the agent can write to is not a control.

## Run it

Localise the culprit and propose a rewrite from a bundled failure log (no API
key needed, deterministic fallback):

```bash
python3 harness_loop.py --log example_failures.jsonl \
    --instructions instructions --out proposals
```

Full end-to-end demo (needs `ANTHROPIC_API_KEY`): scores the weak instruction
live, runs the loop, re-scores with the proposed instruction, prints before and
after:

```bash
python3 demo.py
```

Tests (stdlib, no API):

```bash
python3 -m unittest test_harness_loop -v
```

## How it works

1. **Read** the failure log (JSONL, one run per line: `instruction`, `input`,
   `expected`, `got`, `passed`).
2. **Localise.** Rank instructions by failure concentration. An instruction is
   only eligible to be the culprit once it has run enough times (`--min-runs`,
   default 5), so one unlucky call can't top the ranking.
3. **Propose.** Send the current instruction plus the actual failing traces (not
   just a score) to Claude, and get back a revised instruction with a rationale.
   Without a key, it writes a skeleton with the traces attached for a human.
4. **Gate.** Write the proposal to `proposals/`, and nowhere else. Nothing live
   is touched.

## Log format

```json
{"instruction": "extract-postcode", "input": "...", "expected": "SW1A 2AA", "got": "sw1a1aa", "passed": false}
```

One stdlib file (`harness_loop.py`); the proposer step uses `urllib` to call
Claude when a key is present. No dependencies.
