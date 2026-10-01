"""Run with no data and no keys: python3 demo.py

Two synthetic fleets, same task lengths, different shape:
  heavy-start:  a big fixed starting context, each call adds a little (our fleet)
  growing:      a small start, each call adds a lot (a coding agent reading files)
The forecaster only earns its keep on the second shape.
"""
import random
from statistics import median

from replay import budget_replay, forecast_error
from tokencast_lite import Fixed, NaiveLinear, TokenCastLite, segment_costs


def fleet(start, growth, n=700, seed=7):
    rnd = random.Random(seed)
    tasks = []
    for _ in range(n):
        length = max(1, int(rnd.lognormvariate(1.6, 0.9)))
        g = growth * rnd.lognormvariate(0, 0.6)
        ctx, calls = start * rnd.uniform(0.9, 1.1), []
        for _ in range(length):
            calls.append([int(ctx), 400])
            ctx += g * rnd.uniform(0.5, 1.5)
        tasks.append(calls)
    return tasks


def show(name, tasks):
    train, test = tasks[:490], tasks[490:]
    models = {"fixed": Fixed(train), "naive": NaiveLinear(train), "tokencast_lite": TokenCastLite(train)}
    print(f"\n== {name} ==")
    for r in forecast_error(models, test):
        if r["k"] in (3, 5):
            print(f"  error after {r['k']} calls: " + ", ".join(f"{n} {r[n]['median_rel']:.0%}" for n in models))
    totals = sorted(sum(segment_costs(t)) for t in test)
    caps = sorted({totals[int(p * (len(totals) - 1))] for p in (0.6, 0.75, 0.9)})
    for label, m in (("tokencast_lite", models["tokencast_lite"]), ("naive", models["naive"])):
        rows = budget_replay(m, test, caps, [1.0, 1.5, 2.0, 3.0])
        print(f"  budget saving vs fixed cap ({label}): " + ", ".join(f"{r['saving']:.0%}" for r in rows))


if __name__ == "__main__":
    show("heavy-start: 150k start, ~1k per call (our fleet's shape)", fleet(150_000, 1_000))
    show("growing: 10k start, ~15k per call (file-reading coding agent)", fleet(10_000, 15_000))
