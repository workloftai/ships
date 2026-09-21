# 168 · SoL-Pi harness spike: measuring what an unmanaged agent loop wastes

A small, runnable reimplementation of the four harness mechanisms from **SoL-Pi**
([arXiv:2609.20519](https://arxiv.org/abs/2609.20519)), plus a deterministic loop
simulator that counts the exact input tokens a coding agent re-sends to the model
across a real trajectory.

The point is not to reproduce the paper's headline. It is to measure **our**
number, on a real trajectory over real files, with a real tokenizer, and to prove
no evidence is lost.

## What it measures

A chat-style agent re-sends its whole transcript on every turn, so the bill is
**cumulative input tokens** (sum over requests of the context size). The demo
replays one fixed trajectory (reproduce a failing test, search the codebase, read
a large module, re-check the log, fix and verify, answer) over the real files in
`sample_repo/`, and counts tokens two ways:

- **naive**: every tool result stays in context verbatim, forever.
- **solpi**: the four mechanisms apply.

## The four mechanisms (`solpi.py`)

| Mechanism | What it does | Cache-safe? |
|---|---|---|
| **ObservationPack** | outputs over 10 KiB go full for two requests, then collapse to a handle + head/tail excerpt | yes |
| **Evidence-Preserving Reducer** | build/test logs over 4 KiB collapse to a verified receipt (exit status, error lines, head/tail); falls back to the full log if it fails to shrink | yes |
| **Online Context Compact** | at a subtask boundary, consumed observations collapse to one line, but only when the projected saving beats the rewrite cost | no (rewrites the prefix) |
| **Action Fusion** | fuse an edit and its verify command into one observation, removing a model round trip | n/a |

Every archived output is kept byte-exact behind a stable handle, so any step can
retrieve the exact bytes on demand. Nothing is destroyed, only deferred.

Deterministic note: the paper's reducer calls a cheap model to extract the
receipt. We extract deterministically (no model, no cost, no flake) and verify by
size.

## Run it

```
pip install tiktoken
python3 demo.py            # prints the token delta and the build-up
python3 -m unittest -v test_solpi
```

## Our result (one trajectory, real files)

```
naive  : 182,490 tokens over 12 requests
SoL-Pi :  24,614 tokens over 11 requests   (86.5% fewer, 7.4x less)

cumulative build-up:
  + ObservationPack           21.5% of naive   (the big one)
  + Evidence Reducer          17.0%
  + Online Context Compact    13.7%
  + Action Fusion (=SoL-Pi)   13.5%

all evidence retrievable byte-exact behind a handle.
```

The lesson: bounding large tool outputs (ObservationPack + the reducer) does the
overwhelming majority of the work, and both are cache-safe. Compaction, which
fights the prompt cache, adds only a few points. Do the cheap, cache-safe thing
first.

## Honest caveats

- **Baseline matters.** Our `naive` re-sends everything with zero management, so
  86.5% is the ceiling against an unmanaged loop. The paper's 44.7 to 49.0% is
  against Pi, an already-tuned harness. Different baseline, not a contradiction.
- **Prompt caching changes the money.** Raw tokens fall 86.5%, but with prompt
  caching the *dollar* saving is smaller, and compaction can cost more than it
  saves by breaking the cache. That is exactly why the real mechanism (and this
  reimplementation) gates compaction on rewrite cost.
- One short trajectory, not a benchmark suite. Your mileage will differ.
- No model is called; the measured quantity is input tokens, not task accuracy.
  The retrievability check proves the evidence survives; it does not prove a live
  model would reach the same answer.

MIT. Steal what you want.
