"""Runnable demo — no network. `python3 demo.py`

Shows the three-layer eval end to end:
  Layer 1 kills the obvious for zero tokens, with a named reason.
  Layer 1 abstains on a good answer (falls through to your panel).
  Layer 3 runs the golden-set kappa gate over the seed set.
"""
from precheck import precheck
from golden import kappa_gate, load_golden, DEFAULT_SET

print("=== Layer 1: the cheap KILL ===\n")

cases = [
    ('{"success": false, "result": null}', "complete the action and return a result"),
    ("", "summarise the meeting"),
    ("Traceback (most recent call last):\n  KeyError: 'channel'", "route the item"),
    ("here you go: name Jane, amount 42", "return the fields as strict JSON"),
    ("The team agreed to ship Friday and cut the analytics tab.", "summarise the meeting"),
]
for candidate, criteria in cases:
    r = precheck(candidate, criteria)
    shown = (candidate[:48] + "…") if len(candidate) > 48 else candidate
    shown = shown.replace("\n", " ")
    if r.killed:
        print(f"KILL   [{r.hit.check}]  {shown!r}")
    else:
        print(f"ABSTAIN            {shown!r}  -> falls through to the panel")

print("\n=== Layer 3: certify the judge against the golden set ===\n")
# Standalone: score with Layer 1 alone (no LLM panel bundled). min_rows=1 so the
# demo actually reports a number on the 8-row seed set.
res = kappa_gate(load_golden(DEFAULT_SET),
                 scorer=lambda c, cr: "KILL" if precheck(c, cr).killed else "PASS",
                 min_rows=1)
print(res.summary_line())
print("\n(the real gate uses min_rows=30 and your LLM panel as the scorer; on a")
print(" 30+ row human-labelled set it certifies the judge only above kappa 0.65.)")
