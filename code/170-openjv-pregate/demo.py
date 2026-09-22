"""demo_openjv — see the local, $0 pre-gate decide in one forward pass.

No cloud call. A frozen small model (gemma3:4b via Ollama) reads the probability
it puts on KILL vs PASS straight off the logprobs and returns a typed decision
with a confidence. The pre-gate only ACTS on a confident KILL; a PASS or a
low-confidence read abstains and falls through to Vera's cloud screen->panel
ladder.

    python3 -m vera.demo_openjv

Requires an Ollama endpoint with a small model pulled (VERA_OPENJV_MODEL).
"""
from __future__ import annotations

import openjv

# (criteria, output, what a human would say)
CASES = [
    ("Return the extracted fields as strict JSON.",
     "here are the fields you asked for: name Jane, amount 42", "KILL"),
    ("Return the extracted fields as strict JSON.",
     '{"name": "Jane", "amount": 42}', "PASS"),
    ("Route the item to the correct channel and confirm.",
     'Traceback (most recent call last):\n  File "route.py", line 40\n'
     "ConnectionError: refused", "KILL"),
    ("Route the item to the correct channel and confirm.",
     "Routed to #research and confirmed the card was created (id 7f21).", "PASS"),
    ("Draft a two-sentence summary of the meeting.",
     "", "KILL"),
]


def main():
    conf = openjv._cfg()[1]
    print(f"model={openjv._cfg()[0]}  fire-threshold P(KILL)>={conf}\n")
    print(f"{'human':>5}  {'pregate':>7}  {'P(KILL)':>7}  {'acts?':>6}  {'ms':>6}  criteria")
    print("-" * 84)
    for criteria, output, human in CASES:
        v = openjv.pregate(output, criteria)
        acts = "SHORT-CIRCUIT" if v.verdict == "KILL" else "fall through"
        print(f"{human:>5}  {v.verdict:>7}  {v.p_kill:>7.3f}  "
              f"{acts:>13}  {v.latency_ms:>6}  {criteria[:34]}")
    print("\nOnly a confident KILL short-circuits (at $0). Everything else falls "
          "through to the cloud screen unchanged.")


if __name__ == "__main__":
    main()
