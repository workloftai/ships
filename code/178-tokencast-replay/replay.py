"""Replay real agent tasks through three forecasters and a budget policy.

Usage: python3 replay.py traces.json [results.json]

Split by time: fit on the oldest 70% of tasks, test on the newest 30%.
Two questions:
  1. Forecast error: k calls in, how close is each forecaster to the final bill?
  2. Budget control: a fixed cap versus a cap that stops a task early once the
     forecast says it will blow the cap anyway. Tokens spent at matched
     completion rate.
"""
import json
import sys
from statistics import mean, median

from tokencast_lite import Fixed, NaiveLinear, TokenCastLite, segment_costs

CHECKPOINTS = [1, 2, 3, 5, 10]


def forecast_error(models, test):
    rows = []
    for k in CHECKPOINTS:
        live = [t for t in test if len(t) > k]  # still running after k calls
        if len(live) < 10:
            continue
        row = {"k": k, "n": len(live)}
        for name, m in models.items():
            errs = [abs(m.forecast(t[:k]) - sum(segment_costs(t))) for t in live]
            rel = [e / sum(segment_costs(t)) for e, t in zip(errs, live)]
            row[name] = {"mae": mean(errs), "median_rel": median(rel)}
        rows.append(row)
    return rows


def run_fixed(test, cap):
    spent, done = 0, 0
    for t in test:
        total = sum(segment_costs(t))
        spent += min(total, cap)
        done += total <= cap
    return done / len(test), spent


def run_forecast(model, test, cap, margin, min_k=2):
    """Stop a task as soon as forecast > margin * cap. Hard cap still applies."""
    spent, done = 0, 0
    for t in test:
        so_far, stopped = 0, False
        for k, c in enumerate(segment_costs(t), 1):
            so_far += c
            if so_far > cap:
                so_far, stopped = cap, True
                break
            if k >= min_k and k < len(t) and model.forecast(t[:k]) > margin * cap:
                stopped = True
                break
        spent += so_far
        done += not stopped
    return done / len(test), spent


def budget_replay(model, test, caps, margins):
    out = []
    for cap in caps:
        fc, fs = run_fixed(test, cap)
        best = None
        for m in margins:
            for c2 in caps:
                if c2 < cap * 0.5:
                    continue
                pc, ps = run_forecast(model, test, c2, m)
                if pc >= fc and (best is None or ps < best[1]):
                    best = (pc, ps, c2, m)
        if best:
            out.append({"cap": cap, "fixed_completion": fc, "fixed_tokens": fs,
                        "forecast_completion": best[0], "forecast_tokens": best[1],
                        "forecast_cap": best[2], "margin": best[3],
                        "saving": 1 - best[1] / fs})
    return out


def main(path, out_path=None):
    tasks = [r["calls"] for r in json.load(open(path))]
    cut = int(len(tasks) * 0.7)
    train, test = tasks[:cut], tasks[cut:]
    models = {"fixed": Fixed(train), "naive": NaiveLinear(train),
              "tokencast_lite": TokenCastLite(train)}
    totals = sorted(sum(segment_costs(t)) for t in test)
    q = lambda p: totals[int(p * (len(totals) - 1))]
    caps = sorted({round(q(p), -3) for p in (0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95)})
    margins = [1.0, 1.5, 2.0, 3.0, 5.0]
    res = {"train_tasks": len(train), "test_tasks": len(test),
           "test_calls": sum(len(t) for t in test),
           "spread_p99_over_p10": q(0.99) / q(0.10),
           "forecast_error": forecast_error(models, test),
           "budget_tokencast": budget_replay(models["tokencast_lite"], test, caps, margins),
           "budget_naive": budget_replay(models["naive"], test, caps, margins)}
    print(f"train {len(train)} / test {len(test)} tasks, {res['test_calls']} calls")
    print(f"cost spread across test tasks, p99/p10: {res['spread_p99_over_p10']:.0f}x\n")
    print("forecast error after k calls (median % off the final bill)")
    for r in res["forecast_error"]:
        print(f"  k={r['k']:>2} n={r['n']:>3}  " + "  ".join(
            f"{n}: {r[n]['median_rel']:.0%}" for n in models))
    for name in ("tokencast", "naive"):
        print(f"\nbudget replay ({name}): tokens saved vs a fixed cap at same or better completion")
        for r in res[f"budget_{name}"]:
            print(f"  cap {r['cap']/1e6:5.2f}M  completion {r['fixed_completion']:.0%}"
                  f" -> {r['forecast_completion']:.0%}  saved {r['saving']:.1%}")
    if out_path:
        json.dump(res, open(out_path, "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
