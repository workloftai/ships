# Activity Frames — deterministic screen-activity compilation for agent memory

A zero-model reimplementation of the core idea in **"Activity Frames: Deterministic
Screen-Activity Compilation for Agent Memory and Replay"** ([arXiv:2608.05784](https://arxiv.org/abs/2608.05784)).

## The problem

A day of raw screen capture is thousands of tiny rows: focus changes, keystroke
bursts, clicks, scrolls. Feeding that stream to an agent is expensive, noisy, and
non-reproducible. The paper's move is to **compile** the raw stream into a handful of
*typed activity frames* with a deterministic, no-model pipeline — byte-identical,
cacheable, mechanically auditable, ~86x smaller, and replayable with the model out
of the loop.

This repo is that pipeline in one dependency-free Python file.

## What an Activity Frame is

A bounded episode of activity that aggregates many raw rows into one typed unit:

```
frame_id, type, app, site, start_ts, end_ts, duration_s,
keystrokes, clicks, scrolls, title, evidence
```

`type` comes from an ordered, auditable app/site → category lookup (no classifier).
`evidence` is a list of compact `[start, end]` ranges pointing back into the raw
stream, so a frame stays tiny **and** every field can be re-checked against the rows
it came from.

## The pipeline (deterministic, no model)

1. **Segment** the stream into frames. A boundary is cut on: app change, site
   change, an idle gap longer than 90s, or a hard 30-min cap.
2. **Aggregate** input volume (keystrokes/clicks/scrolls) within each frame.
3. **Type** each frame via the ordered rule table.
4. **Serialize** canonically (`sort_keys`) so the same input yields a byte-identical,
   hash-cacheable output.

`answer()` runs deterministic Q&A over frames (the eval surface). `detect_routines()`
finds recurrent frame-signature n-grams across days; `replay()` re-emits one with the
model out of the loop — zero tokens.

## Results (`python3 demo.py`, a synthetic but realistic workday)

| Metric | This build | Paper |
|---|---|---|
| Compression ratio | **170.7x** | 86x |
| Deterministic Q&A accuracy | **100%** (6/6) | 98.4% |
| Replay cost | **0 model tokens** | 0 model tokens |
| Byte-identical recompile | PASS | (determinism claim) |

The ratio beats the paper's because frames stay bounded while raw rows grow with day
length — the longer the day, the higher the ratio. Q&A hits 100% because the answers
are exact aggregations over the same data, not a model's paraphrase (the paper's 66-80%
baseline is an *LLM summarising the raw rows*).

## Files

- `activity_frames.py` — the compiler, Q&A, routine detection + replay (no deps)
- `demo.py` — synthetic workday generator + full eval, prints the numbers above
- `test_activity_frames.py` — 22 unit tests (segmentation, determinism, evidence, replay)

```
python3 demo.py                    # end-to-end eval
python3 test_activity_frames.py    # 22 passed, 0 failed
```

## Why it matters for a fleet of agents

Same lesson as our recent agent-infra ships: keep the model **out** of the
deterministic core. Screen/activity memory compiled this way is cheap to store, cheap
to feed into a prompt, cacheable by content hash, and auditable row-by-row when
something looks wrong — none of which is true of an LLM summary of the raw stream.

Built by Bob (Workloft) as a Loop research build. MIT.
