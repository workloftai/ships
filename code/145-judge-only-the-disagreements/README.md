# judge-only-the-disagreements (coeval)

A/B two versions of an agent by scoring both over a set of scenarios with an
expensive LLM judge, but only pay the full judge where the two versions
disagree. Settle the ties with one cheap call.

The number an A/B eval produces that matters is the net change in pass rate.
That number is built entirely from scenarios where the two versions disagree
(one passes, one fails). A scenario both pass is a tie; one both fail is a tie;
each nets to zero. Paying the full panel to confirm a tie buys no signal about
which version won. So screen every scenario with one cheap judge, spend the full
panel only on the disagreements (plus the ties the screen was unsure about), and
settle the confident ties cheaply.

The method is from Task-CoEvolve (variance-weighted sampling near the capability
frontier). This is a standalone, dependency-free distillation of the harness we
run inside Workloft's eval stack.

## Run it

```bash
python3 demo.py           # runnable example with fake judges (no API keys)
python3 test_coeval.py    # deterministic proof of the selection + cost math
```

`demo.py` output: two disagreements get PANELLED, four confident ties are settled
on the cheap screen, ~38% saved on that set.

## Use it with your own judges

`coeval.py` has no third-party dependencies and makes no network calls. You
inject your own judges as two callables:

```python
from coeval import coeval_compare

# each judge returns (verdict, confidence, cost_usd); verdict in PASS|KILL|ERROR
def screen_fn(candidate, criteria, label): ...   # ONE cheap judge
def panel_fn(candidate, criteria, label):  ...   # the full, expensive panel

res = coeval_compare(
    scenarios,                          # objects with a .scenario_id
    respond_before=lambda s: run_old(s),
    respond_after=lambda s: run_new(s),
    criteria_for=lambda s: rubric_for(s),
    screen_fn=screen_fn, panel_fn=panel_fn,
    escalate_conf_floor=0.75,           # ties below this screen confidence escalate
    panel_budget_frac=1.0,              # hard cap on panelled fraction (disagreements exempt)
)
print(res.summary_line())   # before -> after  pass 60% -> 80%  up net +2 …
print(res.savings_line())   # panelled 5/20 scenarios … (72% saved)
```

## How it decides where to spend

1. **Screen** each side with one cheap judge.
2. **Frontier weight** per scenario: `1.0` if the two screens disagree (only these
   move the net delta); else `1 - min(confidence)`, so a shaky tie outranks a
   settled one.
3. **Escalate** every disagreement, plus every tie below `escalate_conf_floor`, to
   the full panel. `panel_budget_frac` caps the panelled fraction if you want a
   hard ceiling, but a disagreement is never dropped.
4. Confident ties keep the cheap screen verdict. Report the same net-delta summary
   as a full A/B, plus the panel cost spent vs. panelling everything.

## Honest limits

- The saving comes from the ties you skip. An escalated scenario costs *more* than
  a plain A/B (it pays the screen and the panel). The more your two versions agree,
  the more you save; the more they diverge, the less.
- The cheap screen is a single judge, so a scenario it rates a confident tie can
  hide a flip the panel would have caught (a "missed frontier"). `escalate_conf_floor`
  trades saving against that risk. A disagreement the screen sees is always
  panelled, and an ERROR screen is always escalated, never trusted as a tie.
- Need the exhaustive ground truth? Set `panel_budget_frac` aside and panel
  everything, which is just the old harness. The point is that you rarely need to.

MIT-licensed. Part of [Workloft Ships](https://workloft.ai/ships/).
