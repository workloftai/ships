# A cheap KILL before the LLM judge

The two layers most LLM-judge setups skip, ported from Airbnb's three-layer eval
model (programmatic checks → LLM judge → human calibration).

- **Layer 1 `precheck.py`** — deterministic checks that run *before* any model is
  asked. Kills empty output, a call reporting `success=false` with no sign the
  failure was expected, a leaked traceback, or output that should be JSON and
  isn't. Each check names itself, so a rejection is explainable, not a vibe.
  **It never returns PASS** — a cheap PASS is how slop gets waved through. It can
  only KILL or ABSTAIN. A real PASS still has to earn the panel.
- **Layer 3 `golden.py`** — a golden set of human-labelled examples plus a
  `kappa_gate` that runs your judge over them and computes Cohen's kappa (the
  agreement number corrected for luck). Below the bar (default 0.65) or below 30
  rows, it refuses to certify the judge for automated gating, and says why.
- **`layers.py`** — ties them together. `three_layer_evaluate` runs Layer 1, and
  only if it abstains does it call your Layer-2 panel (injectable — this drop
  ships no LLM judge).

## Run it

```bash
python3 demo.py          # end-to-end, no network
python3 test_layers.py   # 19 tests, no network
python3 golden.py        # kappa gate over the seed golden set
```

## Wire in your own judge

`precheck` and the gate are self-contained. For Layer 2, pass your panel:

```python
from layers import three_layer_evaluate
res = three_layer_evaluate(candidate, criteria, panel=my_evaluate_fn)
# res.layer == "precheck" when a cheap check killed it (cost 0), else "panel".
```

To gate the judge itself, give `kappa_gate` a scorer that calls your real panel
and a golden set of your own human-labelled rows:

```python
from golden import kappa_gate
gate = kappa_gate("my_golden.jsonl", scorer=lambda c, cr: my_panel(c, cr).verdict)
if not gate.certified:
    ...  # don't trust the judge's live verdicts until it's retuned
```

## The point

Kill the obvious for free, judge the rest with a panel, and never let the judge
grade its own homework without a human answer key to check it against. Most eval
"platforms" are a lot of dashboard around those three ideas. The ideas are what
matter.
