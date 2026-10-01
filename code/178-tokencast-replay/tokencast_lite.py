"""tokencast_lite: forecast an agent task's total token bill while it runs.

A from-the-abstract re-implementation of the idea in TokenCast
(arXiv 2609.35760). Their code is not released yet, so this is ours, not theirs.

The idea: every model call is a segment with two numbers. What it cost
(input + output), and how much it grew the context. Growth matters because
every later call re-reads it. Compose the segments and you get the bill so far
plus a bill for the calls still to come, which grows quadratically, not
linearly. After each call the forecast refreshes with what was just observed.
No extra model calls, just arithmetic.

What we learn from history: how many more calls a task tends to make, given how
many it has made already. That is the only fitted part.
"""
from bisect import bisect_left
from statistics import median


def segment_costs(calls):
    """calls: [[input_tokens, output_tokens, ...], ...] -> per-call totals."""
    return [c[0] + c[1] for c in calls]


class TokenCastLite:
    def __init__(self, history, max_k=40, prior_weight=3):
        """history: list of past tasks, each a list of calls."""
        self.max_k = max_k
        self.prior_weight = prior_weight
        lengths = sorted(len(t) for t in history)
        # remaining-calls samples, conditioned on having already made k calls
        self.remaining = {}
        for k in range(1, max_k + 1):
            i = bisect_left(lengths, k)
            self.remaining[k] = [n - k for n in lengths[i:]] or [0]
        growths = [b[0] - a[0] for t in history for a, b in zip(t, t[1:])]
        outs = [c[1] for t in history for c in t]
        self.prior_growth = median(growths) if growths else 0
        self.prior_out = median(outs) if outs else 0
        totals = [sum(segment_costs(t)) for t in history]
        self.fixed_guess = median(totals) if totals else 0

    def _future(self, ctx, growth, out, r):
        # r more calls: each re-reads today's context, plus everything added since
        return r * (ctx + out) + growth * r * (r + 1) / 2

    def forecast(self, seen):
        """seen: the calls observed so far in this task. Returns total tokens."""
        if not seen:
            return self.fixed_guess
        k = len(seen)
        spent = sum(segment_costs(seen))
        ctx = seen[-1][0] + seen[-1][1]
        obs = [b[0] - a[0] for a, b in zip(seen, seen[1:])]
        w = self.prior_weight
        growth = (sum(obs) + w * self.prior_growth) / (len(obs) + w)
        growth = max(growth, 0)
        out = (sum(c[1] for c in seen) + w * self.prior_out) / (k + w)
        rs = self.remaining[min(k, self.max_k)]
        # median over plausible futures: minimises absolute error
        return spent + median(self._future(ctx, growth, out, r) for r in rs)


class NaiveLinear:
    """Baseline: average cost per call so far, times expected length."""

    def __init__(self, history, max_k=40):
        self.tc = TokenCastLite(history, max_k)

    def forecast(self, seen):
        if not seen:
            return self.tc.fixed_guess
        k = len(seen)
        spent = sum(segment_costs(seen))
        r = median(self.tc.remaining[min(k, self.tc.max_k)])
        return spent * (k + r) / k


class Fixed:
    """Baseline: one number per task, decided before it starts (a fixed budget)."""

    def __init__(self, history):
        self.tc = TokenCastLite(history)

    def forecast(self, seen):
        return self.tc.fixed_guess
