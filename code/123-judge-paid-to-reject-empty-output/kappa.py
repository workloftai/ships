"""Cohen's kappa for LLM-judge calibration.

Raw agree-rate flatters a judge on imbalanced data: a judge that always says PASS
scores 90% on a 90%-PASS set while being useless. Cohen's kappa corrects for
chance agreement, so it is the real number to track when you ask "does this judge
agree with a human?"
"""
from __future__ import annotations


def cohen_kappa(pairs: list[tuple[str, str]]) -> dict:
    """pairs: (human_verdict, judge_verdict), each 'PASS' or 'KILL'."""
    n = len(pairs)
    if n == 0:
        return {"n": 0, "error": "no pairs"}
    labels = ("PASS", "KILL")
    agree = sum(1 for h, v in pairs if h == v)
    po = agree / n
    pe = 0.0
    for L in labels:
        ph = sum(1 for h, _ in pairs if h == L) / n
        pv = sum(1 for _, v in pairs if v == L) / n
        pe += ph * pv
    kappa = (po - pe) / (1 - pe) if (1 - pe) > 1e-9 else 1.0
    return {"n": n, "agreement": round(po, 3), "kappa": round(kappa, 3),
            "chance": round(pe, 3)}


def band(k: float) -> str:
    if k >= 0.8:  return "STRONG — treat as a reliable automated reviewer"
    if k >= 0.65: return "SUBSTANTIAL — production-ready for most gating"
    if k >= 0.60: return "WATCH — acceptable but improve the rubric"
    return "WEAK — HALT automation, retune the rubric/jurors before trusting"
