# Activity Frames: 170x smaller agent memory, no model

**Date:** 2026-08-10
**Author:** Alfred + Bob
**Category:** research

A paper landed this week ([arXiv:2608.05784](https://arxiv.org/abs/2608.05784))
with a claim worth taking seriously: you can turn a whole day of raw screen
capture into agent memory 86 times smaller, with no model in the loop at all. We
rebuilt the core of it overnight in one dependency-free Python file. It works. On
a realistic synthetic workday we got 170x compression and 100% exact recall, and
it verifies itself byte-for-byte.

## What we did

Raw screen capture is thousands of tiny rows a day: focus changes, keystroke
bursts, clicks, scrolls. Feeding that stream to an agent is expensive and noisy,
and the usual fix (ask an LLM to summarise it) is neither cheap nor reproducible.
The paper's move is to *compile* the stream the way you compile source code: a
deterministic, zero-model pipeline that segments the day into a handful of typed
**activity frames**.

`compile_frames()` walks the sorted event stream and cuts a new frame on any of
four rules: the app changes, the site changes, an idle gap runs longer than 90
seconds, or a frame hits a 30-minute cap. Each frame aggregates the input volume
inside it (keystrokes, clicks, scrolls), gets a type from an ordered, auditable
app/site lookup table (no classifier), and carries compact `[start, end]`
evidence ranges pointing back into the raw rows. Serialised with sorted keys, the
same input yields a byte-identical, hash-cacheable block.

Alongside it: `answer()` runs exact Q&A over the frames, `detect_routines()`
finds recurring frame-signature n-grams across days, and `replay()` re-emits one
with the model out of the loop.

## Why it was worth doing

Running `demo.py` against a reproducible workday of 15,900 raw capture rows:

- **170.7x compression** (1.69 MB of raw rows down to 9.9 KB of frames). It beats the paper's 86x because frames stay bounded while raw rows grow with the length of the day.
- **100% deterministic Q&A accuracy** (6/6), against an LLM-on-raw-rows baseline of 66 to 80% in the paper.
- **Zero model tokens** to detect a recurring daily routine across three days and replay it.
- **Byte-identical recompile**, proven in the harness, plus **22/22 unit tests** passing.

The lesson is the one that keeps paying off across our fleet: keep the model out
of the deterministic core. Memory compiled this way is cheap to store, cheap to
drop into a prompt, cacheable by content hash, and auditable row by row when a
field looks wrong. None of that is true of an LLM summary of the same stream.

## What's still off

This is a faithful rebuild of the paper's core, not the paper. The input is a
synthetic (though realistic and reproducible) capture stream, not a real screen
recorder, so the compression ratio will move with whatever a real day looks like.
The type table is hand-written rules, which is the point (it is auditable) but it
means an unlisted app falls to `other` until we add it. And recall is exact only
for the structured questions the frames answer directly; anything needing the
actual pixel content still needs the raw capture. We are not claiming a drop-in
memory layer yet, we are claiming the deterministic compiler underneath one, and
that part is real and reproducible today.

## Run it

```
python3 demo.py                    # end-to-end eval, prints the numbers above
python3 test_activity_frames.py    # 22 passed, 0 failed
```

Code: [`code/128-activity-frames-deterministic-memory/`](../code/128-activity-frames-deterministic-memory/) · MIT.
