"""coeval — disagreement-weighted A/B eval: judge only where two versions differ.

Standalone, dependency-free distillation of the harness we run inside Workloft's
eval stack (Vera). The idea is from Task-CoEvolve (variance-weighted sampling
near the capability frontier): when you A/B two versions of an agent by scoring
both over a set of scenarios with an expensive judge, you do not need to judge
the scenarios where the two versions already agree.

Why: an A/B eval produces one number that matters, the net change in pass rate.
That number is built ENTIRELY from scenarios where the two versions disagree
(one passes, one fails). A scenario both pass is a tie; one both fail is a tie;
each nets to zero. Paying the full panel to confirm a tie buys no signal about
which version won. So: screen every scenario with one cheap judge, spend the
expensive panel only on the disagreements (plus the ties the screen was unsure
about), and settle the confident ties on the cheap screen.

This file has no third-party dependencies and no network calls. You inject your
own judges as two callables:

    screen_fn(candidate, criteria, label) -> (verdict, confidence, cost_usd)   # 1 cheap judge
    panel_fn(candidate, criteria, label)  -> (verdict, confidence, cost_usd)   # full panel

verdict is "PASS" | "KILL" | "ERROR". See demo.py for a runnable example with
fake judges, and test_coeval.py for the deterministic proof of the selection and
cost arithmetic (no models, no tokens).

    from coeval import coeval_compare
    res = coeval_compare(
        scenarios,                       # list of objects with .scenario_id / .prompt
        respond_before=lambda s: "...",  # produce version A's response for a scenario
        respond_after=lambda s: "...",   # produce version B's response
        criteria_for=lambda s: "...",    # the rubric text the judge scores against
        screen_fn=my_cheap_judge,
        panel_fn=my_full_panel,
    )
    print(res.summary_line())            # before -> after  pass 60% -> 80%  net +2
    print(res.savings_line())            # panelled 5/20 … (72% saved)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Sequence


# --- frontier scoring (pure) -------------------------------------------------

def frontier_weight(verdict_b: str, conf_b: float,
                    verdict_a: str, conf_a: float) -> float:
    """How much a scenario can separate the two versions, from the cheap screens
    alone. 1.0 when the screens disagree (only these move the net delta);
    otherwise 1 - min(confidence), so a shaky tie outranks a settled one. An
    ERROR screen is treated as maximally uncertain so it is never trusted as a
    settled tie."""
    if verdict_b == "ERROR" or verdict_a == "ERROR":
        return 1.0
    if verdict_b != verdict_a:
        return 1.0
    return round(1.0 - min(conf_b, conf_a), 4)


def select_for_panel(weights: Sequence[float], *,
                     escalate_conf_floor: float,
                     panel_budget_frac: float) -> list[bool]:
    """Decide which scenarios get the full panel.

    A scenario is escalated if its frontier weight clears the floor
    (weight >= 1 - escalate_conf_floor covers both hard disagreements at 1.0 and
    shaky ties). panel_budget_frac caps the panelled fraction: if more scenarios
    clear the floor than the budget allows, the highest-weight ones win, but a
    hard disagreement (weight 1.0) is never dropped, because dropping it would
    silently discard a scenario that moves the net delta."""
    floor_weight = 1.0 - escalate_conf_floor
    order = sorted(range(len(weights)), key=lambda i: weights[i], reverse=True)
    cap = len(weights) if panel_budget_frac >= 1.0 else int(
        round(len(weights) * panel_budget_frac))
    chosen = [False] * len(weights)
    n = 0
    for i in order:
        w = weights[i]
        if w >= 1.0:                      # disagreement: never dropped
            chosen[i] = True
            n += 1
        elif w >= floor_weight and n < cap:
            chosen[i] = True
            n += 1
    return chosen


# --- per-scenario + aggregate results ---------------------------------------

@dataclass
class CoScenario:
    scenario_id: str
    verdict_before: str
    confidence_before: float
    verdict_after: str
    confidence_after: float
    frontier_weight: float
    panel_confirmed: bool

    @property
    def transition(self) -> str:
        b, a = self.verdict_before, self.verdict_after
        if b not in ("PASS", "KILL") or a not in ("PASS", "KILL"):
            return "inconclusive"
        if b == "KILL" and a == "PASS":
            return "fixed"
        if b == "PASS" and a == "KILL":
            return "regressed"
        return "stable-pass" if a == "PASS" else "stable-kill"


@dataclass
class CoEvalResult:
    before_label: str
    after_label: str
    scenarios: list[CoScenario] = field(default_factory=list)
    screen_cost_usd: float = 0.0
    panel_cost_usd: float = 0.0
    full_panel_cost_estimate_usd: float = 0.0
    n_scored: int = 0
    n_panelled: int = 0
    pass_rate_before: float = 0.0
    pass_rate_after: float = 0.0
    fixed: int = 0
    regressed: int = 0
    stable_pass: int = 0
    stable_kill: int = 0
    inconclusive: int = 0

    @property
    def total_cost_usd(self) -> float:
        return self.screen_cost_usd + self.panel_cost_usd

    @property
    def net_delta(self) -> int:
        return self.fixed - self.regressed

    @property
    def savings_frac(self) -> float:
        base = self.full_panel_cost_estimate_usd
        return 0.0 if base <= 0 else max(0.0, 1.0 - self.total_cost_usd / base)

    def summary_line(self) -> str:
        arrow = "up" if self.net_delta > 0 else ("down" if self.net_delta < 0 else "=")
        return (f"{self.before_label} -> {self.after_label}  "
                f"pass {self.pass_rate_before:.0%} -> {self.pass_rate_after:.0%}  "
                f"{arrow} net {self.net_delta:+d}  "
                f"(fixed {self.fixed}, regressed {self.regressed}, "
                f"stable {self.stable_pass + self.stable_kill}, "
                f"inconclusive {self.inconclusive})")

    def savings_line(self) -> str:
        return (f"panelled {self.n_panelled}/{self.n_scored} scenarios  "
                f"spent ${self.total_cost_usd:.4f} vs "
                f"${self.full_panel_cost_estimate_usd:.4f} full-panel  "
                f"({self.savings_frac:.0%} saved)")


def aggregate(result: CoEvalResult) -> CoEvalResult:
    """Fill the aggregate counters from result.scenarios. Pure; deterministic."""
    decided_before = decided_after = 0
    pass_before = pass_after = 0
    fixed = regressed = stable_pass = stable_kill = inconclusive = 0
    for s in result.scenarios:
        if s.verdict_before in ("PASS", "KILL"):
            decided_before += 1
            pass_before += (s.verdict_before == "PASS")
        if s.verdict_after in ("PASS", "KILL"):
            decided_after += 1
            pass_after += (s.verdict_after == "PASS")
        t = s.transition
        fixed += (t == "fixed")
        regressed += (t == "regressed")
        stable_pass += (t == "stable-pass")
        stable_kill += (t == "stable-kill")
        inconclusive += (t == "inconclusive")
    result.n_scored = len(result.scenarios)
    result.n_panelled = sum(1 for s in result.scenarios if s.panel_confirmed)
    result.pass_rate_before = pass_before / decided_before if decided_before else 0.0
    result.pass_rate_after = pass_after / decided_after if decided_after else 0.0
    result.fixed, result.regressed = fixed, regressed
    result.stable_pass, result.stable_kill = stable_pass, stable_kill
    result.inconclusive = inconclusive
    return result


# --- the harness -------------------------------------------------------------

Judge = Callable[[str, str, str], tuple[str, float, float]]


def coeval_compare(scenarios, *,
                   respond_before: Callable[[object], str],
                   respond_after: Callable[[object], str],
                   criteria_for: Callable[[object], str],
                   screen_fn: Judge,
                   panel_fn: Judge,
                   before_label: str = "before",
                   after_label: str = "after",
                   escalate_conf_floor: float = 0.75,
                   panel_budget_frac: float = 1.0) -> CoEvalResult:
    """Screen every scenario cheaply, panel only the frontier, report the same
    net-delta summary as a full A/B plus the cost saving.

    Each scenario object needs a `.scenario_id`. respond_* produce the two
    versions' responses; criteria_for gives the rubric text to judge against.
    """
    result = CoEvalResult(before_label=before_label, after_label=after_label)
    cost = {"screen": 0.0, "panel": 0.0, "panel_calls": 0}

    # pass 1: generate + cheap screen both sides
    screened = []
    for sc in scenarios:
        criteria = criteria_for(sc)
        rb, ra = respond_before(sc), respond_after(sc)
        vb, cb, cost_b = screen_fn(rb, criteria, f"{before_label}:{sc.scenario_id}")
        va, ca, cost_a = screen_fn(ra, criteria, f"{after_label}:{sc.scenario_id}")
        cost["screen"] += cost_b + cost_a
        screened.append((sc, criteria, rb, ra, vb, cb, va, ca))

    weights = [frontier_weight(x[4], x[5], x[6], x[7]) for x in screened]
    chosen = select_for_panel(weights, escalate_conf_floor=escalate_conf_floor,
                              panel_budget_frac=panel_budget_frac)

    # pass 2: panel only the chosen scenarios (both sides)
    rows: list[CoScenario] = []
    for i, x in enumerate(screened):
        sc, criteria, rb, ra, vb, cb, va, ca = x
        panelled = chosen[i]
        if panelled:
            vb, cb, cost_b = panel_fn(rb, criteria, f"{before_label}:{sc.scenario_id}")
            va, ca, cost_a = panel_fn(ra, criteria, f"{after_label}:{sc.scenario_id}")
            cost["panel"] += cost_b + cost_a
            cost["panel_calls"] += 2
        rows.append(CoScenario(
            scenario_id=sc.scenario_id,
            verdict_before=vb, confidence_before=cb,
            verdict_after=va, confidence_after=ca,
            frontier_weight=weights[i], panel_confirmed=panelled))

    result.scenarios = rows
    result.screen_cost_usd = cost["screen"]
    result.panel_cost_usd = cost["panel"]
    # Estimate the full-A/B bill from THIS run's own measured panel cost-per-call,
    # so the saving is grounded in real prices rather than a guess.
    if cost["panel_calls"] > 0:
        per_call = cost["panel"] / cost["panel_calls"]
        result.full_panel_cost_estimate_usd = per_call * 2 * len(rows)
    return aggregate(result)
