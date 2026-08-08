"""Layer 3 — golden sets and the kappa gate (standalone).

The LLM panel answers "ship or kill this candidate?". Layer 3 answers the
question the panel cannot answer about itself: is the judge trustworthy right
now? Run the judge over a set of human-labelled examples, compare its verdicts to
the human labels, compute kappa, and certify (or refuse to certify) it against a
bar.

Standalone note: this drop has no bundled LLM panel, so the default scorer is
Layer 1 alone (`precheck`). Inject your own `scorer=(candidate, criteria) ->
"PASS"|"KILL"` that calls your real panel to gate the real judge.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from kappa import band, cohen_kappa

DEFAULT_SET = Path(__file__).resolve().parent / "golden.jsonl"

# 0.65 = "substantial" agreement (the production-ready band). The chance-corrected
# version of Airbnb's "80-90% human agreement" framing, and the honest number.
DEFAULT_BAR = 0.65


@dataclass
class GoldenRow:
    candidate: str
    criteria: str
    human: str                 # "PASS" | "KILL"
    agent: str = ""
    action: str = ""
    note: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "GoldenRow":
        return cls(
            candidate=str(d["candidate"]),
            criteria=str(d.get("criteria", "")),
            human=str(d["human"]).upper(),
            agent=str(d.get("agent", "")),
            action=str(d.get("action", "")),
            note=str(d.get("note", "")),
        )


@dataclass
class Disagreement:
    candidate: str
    human: str
    vera: str
    agent: str = ""
    action: str = ""


@dataclass
class GateResult:
    n: int
    kappa: float
    agreement: float
    band: str
    certified: bool
    bar: float
    disagreements: list[Disagreement] = field(default_factory=list)
    warning: str = ""

    def summary_line(self) -> str:
        mark = "CERTIFIED" if self.certified else "NOT CERTIFIED"
        return (f"{mark}  n={self.n}  kappa={self.kappa:.3f} (bar {self.bar})  "
                f"agree={self.agreement:.0%}  — {self.band}")


def load_golden(path=DEFAULT_SET) -> list[GoldenRow]:
    p = Path(path)
    if not p.exists():
        return []
    txt = p.read_text(encoding="utf-8").strip()
    if not txt:
        return []
    rows = json.loads(txt) if txt.startswith("[") else [
        json.loads(line) for line in txt.splitlines() if line.strip()]
    return [GoldenRow.from_dict(r) for r in rows]


def append_golden(row: GoldenRow, path=DEFAULT_SET) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {"agent": row.agent, "action": row.action,
               "candidate": row.candidate, "criteria": row.criteria,
               "human": row.human.upper(), "note": row.note}
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _layer1_scorer(candidate: str, criteria: str) -> str:
    """Default standalone scorer: Layer 1 only. A KILL from the pre-check, else
    PASS. Replace with your real panel to actually gate the LLM judge."""
    from precheck import precheck
    return "KILL" if precheck(candidate, criteria).killed else "PASS"


def kappa_gate(rows=None, *, scorer: Callable[[str, str], str] | None = None,
               bar: float = DEFAULT_BAR, min_rows: int = 30) -> GateResult:
    if rows is None or isinstance(rows, (str, Path)):
        rows = load_golden(rows or DEFAULT_SET)
    scorer = scorer or _layer1_scorer

    pairs: list[tuple[str, str]] = []
    disagreements: list[Disagreement] = []
    for r in rows:
        vera = "PASS" if str(scorer(r.candidate, r.criteria)).upper() == "PASS" else "KILL"
        pairs.append((r.human, vera))
        if vera != r.human:
            disagreements.append(Disagreement(r.candidate, r.human, vera, r.agent, r.action))

    stats = cohen_kappa(pairs)
    n = stats.get("n", 0)
    kappa = float(stats.get("kappa", 0.0)) if n else 0.0
    agreement = float(stats.get("agreement", 0.0)) if n else 0.0

    warning = ""
    certified = kappa >= bar
    if n < min_rows:
        warning = (f"n={n} < {min_rows}: first signal only, not a stable estimate. "
                   f"Certification withheld until the golden set grows.")
        certified = False

    return GateResult(n=n, kappa=round(kappa, 3), agreement=round(agreement, 3),
                      band=band(kappa) if n else "no data",
                      certified=certified, bar=bar,
                      disagreements=disagreements, warning=warning)


if __name__ == "__main__":
    res = kappa_gate()
    print(res.summary_line())
    if res.warning:
        print(f"  ! {res.warning}")
    for d in res.disagreements:
        tag = f"{d.agent}/{d.action}" if d.agent else "row"
        print(f"  x {tag}: human={d.human} judge={d.vera} — {d.candidate[:80]}")
