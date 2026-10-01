from replay import run_fixed, run_forecast
from tokencast_lite import Fixed, NaiveLinear, TokenCastLite

HIST = [[[1000 + 500 * i, 100] for i in range(n)] for n in (2, 3, 4, 5, 6, 8, 10)]


def test_forecast_never_below_spent():
    tc = TokenCastLite(HIST)
    seen = [[1000, 100], [1500, 100], [2000, 100]]
    assert tc.forecast(seen) >= sum(a + b for a, b in seen)


def test_forecast_counts_context_growth():
    tc = TokenCastLite(HIST)
    flat = [[1000, 100]] * 3
    grow = [[1000, 100], [3000, 100], [5000, 100]]
    assert tc.forecast(grow) > tc.forecast(flat)


def test_empty_task_uses_fixed_guess():
    assert TokenCastLite(HIST).forecast([]) == Fixed(HIST).forecast([[1, 1]])
    assert NaiveLinear(HIST).forecast([]) > 0


def test_fixed_cap_cuts_spend():
    done, spent = run_fixed(HIST, cap=5000)
    assert spent <= 5000 * len(HIST) and 0 < done < 1


def test_forecast_policy_stops_early_and_respects_cap():
    tc = TokenCastLite(HIST)
    done, spent = run_forecast(tc, HIST, cap=5000, margin=1.0)
    _, fixed_spent = run_fixed(HIST, cap=5000)
    assert spent <= fixed_spent
