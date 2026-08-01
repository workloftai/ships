#!/usr/bin/env python3
"""
fleet_guard - a hard budget floor for autonomous agent loops.

An autonomous agent on a retry loop can spend without bound. It never errors;
it just keeps calling the model. Amazon ran an internal Claude deployment 860%
over budget for five months on a misconfigured retry loop before anyone noticed
(a ~$1.8M bill). The failure mode is not a bug in the model, it is the absence
of a floor under the loop.

Most in-process guards share one weakness: they live in memory, so a loop that
restarts the process each iteration (a cron every minute, a supervisor that
respawns on crash) resets its own counter and the cap never bites. fleet_guard
persists the count to disk and measures spend over a rolling time window, so the
floor holds across restarts and expires on its own.

Design:
  - Caps are token count, cost in USD, and iteration count, any combination.
  - A rolling window (window_s) makes them "per hour" / "per minute" budgets that
    survive process restarts and decay automatically. Omit it for a lifetime cap.
  - A kill-switch file halts every guard sharing the ledger dir at once, no deploy.
  - Zero dependencies (stdlib only). The ledger is one JSON file per guard name.

This is a standalone generalisation of the per-session token cap that already
lived in our model router (it was in-memory and Anthropic-only). Here it is
fleet-wide, cost-aware, disk-persisted and kill-switchable.

Usage:
    from fleet_guard import BudgetGuard, BudgetExceeded

    guard = BudgetGuard(
        "nightly-summariser",
        max_cost_usd=5.0,        # no more than $5 ...
        max_iterations=500,      # ... or 500 calls ...
        window_s=3600,           # ... per rolling hour
    )
    while work_remaining():
        guard.tick(tokens=resp_tokens, cost_usd=resp_cost)  # raises when a cap is hit
        do_one_iteration()

CLI:
    python3 fleet_guard.py status <name>   # show current window spend vs caps
    python3 fleet_guard.py reset  <name>   # clear a guard's ledger
    python3 fleet_guard.py stop            # drop the fleet-wide kill-switch
    python3 fleet_guard.py resume          # remove the kill-switch
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

DEFAULT_LEDGER_DIR = Path(os.environ.get("FLEET_GUARD_DIR", "~/.fleet-guard")).expanduser()
KILLSWITCH_NAME = "STOP"


class BudgetExceeded(RuntimeError):
    """Raised by tick()/check() when a cap is hit or the kill-switch is present.

    Not a subclass of any provider error, so it propagates cleanly out of a
    retry loop that only catches transport errors, and actually halts it."""

    def __init__(self, reason: str, guard: str, stats: dict):
        self.reason = reason
        self.guard = guard
        self.stats = stats
        super().__init__(f"[fleet_guard:{guard}] halted: {reason} | {stats}")


def _now() -> float:
    return time.time()


class BudgetGuard:
    def __init__(
        self,
        name: str,
        *,
        max_tokens: int | None = None,
        max_cost_usd: float | None = None,
        max_iterations: int | None = None,
        window_s: float | None = None,
        ledger_dir: str | os.PathLike | None = None,
        killswitch: bool = True,
    ):
        if max_tokens is None and max_cost_usd is None and max_iterations is None:
            raise ValueError("set at least one of max_tokens / max_cost_usd / max_iterations")
        if not name or "/" in name or os.sep in name:
            raise ValueError(f"guard name must be a plain slug, got {name!r}")
        self.name = name
        self.max_tokens = max_tokens
        self.max_cost_usd = max_cost_usd
        self.max_iterations = max_iterations
        self.window_s = window_s
        self.killswitch = killswitch
        self.dir = Path(ledger_dir).expanduser() if ledger_dir else DEFAULT_LEDGER_DIR
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / f"{name}.json"
        self._events: list[list[float]] = self._load()

    # ---- persistence -------------------------------------------------------
    def _load(self) -> list[list[float]]:
        try:
            data = json.loads(self.path.read_text())
            return [list(e) for e in data.get("events", [])]
        except (FileNotFoundError, json.JSONDecodeError, ValueError):
            return []

    def _save(self) -> None:
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps({"name": self.name, "events": self._events}))
        os.replace(tmp, self.path)  # atomic on POSIX

    # ---- window bookkeeping ------------------------------------------------
    def _prune(self) -> None:
        if self.window_s is None:
            return
        cutoff = _now() - self.window_s
        self._events = [e for e in self._events if e[0] >= cutoff]

    def _sums(self) -> tuple[int, float, int]:
        toks = int(sum(e[1] for e in self._events))
        cost = float(sum(e[2] for e in self._events))
        return toks, cost, len(self._events)

    def _killswitch_present(self) -> bool:
        if not self.killswitch:
            return False
        return (self.dir / KILLSWITCH_NAME).exists() or (self.dir / f"{KILLSWITCH_NAME}.{self.name}").exists()

    def _breach(self, toks: int, cost: float, iters: int) -> str | None:
        if self._killswitch_present():
            return "kill-switch present"
        if self.max_tokens is not None and toks > self.max_tokens:
            return f"tokens {toks} > cap {self.max_tokens}"
        if self.max_cost_usd is not None and cost > self.max_cost_usd:
            return f"cost ${cost:.4f} > cap ${self.max_cost_usd:.4f}"
        if self.max_iterations is not None and iters > self.max_iterations:
            return f"iterations {iters} > cap {self.max_iterations}"
        return None

    # ---- public API --------------------------------------------------------
    def status(self) -> dict:
        self._prune()
        toks, cost, iters = self._sums()
        return {
            "guard": self.name,
            "window_s": self.window_s,
            "tokens": toks, "max_tokens": self.max_tokens,
            "cost_usd": round(cost, 6), "max_cost_usd": self.max_cost_usd,
            "iterations": iters, "max_iterations": self.max_iterations,
            "killswitch": self._killswitch_present(),
        }

    def check(self) -> None:
        """Pre-flight: raise if a cap is already breached, without recording spend."""
        self._prune()
        toks, cost, iters = self._sums()
        reason = self._breach(toks, cost, iters)
        if reason:
            raise BudgetExceeded(reason, self.name, self.status())

    def tick(self, *, tokens: int = 0, cost_usd: float = 0.0) -> None:
        """Record one iteration's spend, then raise if any cap is now breached.

        Persists before raising, so the ledger reflects the spend that tripped
        the cap and a restart cannot 'forget' it."""
        self._prune()
        self._events.append([_now(), int(tokens), float(cost_usd)])
        self._save()
        toks, cost, iters = self._sums()
        reason = self._breach(toks, cost, iters)
        if reason:
            raise BudgetExceeded(reason, self.name, self.status())

    def reset(self) -> None:
        self._events = []
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass

    def __enter__(self) -> "BudgetGuard":
        return self

    def __exit__(self, *exc) -> None:
        self._save()


# --------------------------------------------------------------- CLI --------
def _cli(argv: list[str]) -> int:
    if not argv:
        print(__doc__.strip().split("\n\n")[0])
        print("\ncommands: status <name> | reset <name> | stop | resume")
        return 2
    cmd = argv[0]
    d = DEFAULT_LEDGER_DIR
    d.mkdir(parents=True, exist_ok=True)
    if cmd == "stop":
        (d / KILLSWITCH_NAME).write_text(f"stopped {time.ctime()}\n")
        print(f"kill-switch DOWN: {d / KILLSWITCH_NAME} (every guard in {d} halts)")
        return 0
    if cmd == "resume":
        try:
            (d / KILLSWITCH_NAME).unlink()
            print("kill-switch cleared")
        except FileNotFoundError:
            print("no kill-switch was set")
        return 0
    if cmd in ("status", "reset") and len(argv) >= 2:
        name = argv[1]
        # A read-only view needs a cap to construct; use a permissive dummy.
        g = BudgetGuard(name, max_iterations=1 << 62)
        if cmd == "status":
            print(json.dumps(g.status(), indent=2))
        else:
            g.reset()
            print(f"reset {name}")
        return 0
    print("bad usage; commands: status <name> | reset <name> | stop | resume")
    return 2


if __name__ == "__main__":
    raise SystemExit(_cli(sys.argv[1:]))
