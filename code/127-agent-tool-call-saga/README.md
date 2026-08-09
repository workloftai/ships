# saga — compensating transactions for agent tool calls

When an agent's multi-step run fails on step 4, the side effects of steps 1 to 3
are already live. There is no `ROLLBACK` for a sent email or a pushed commit. The
saga pattern is the old distributed-systems answer: for every forward action,
register an action that undoes it, and on failure run the undos in reverse. This
is that pattern for agent tool calls, in one file, no dependencies.

## Two modes

- **In-process rollback.** Wrap your steps in a `Saga` context manager. If any
  step raises, the steps that already ran are compensated last-in-first-out, then
  the original error propagates.
- **Crash-safe recovery.** If the process itself dies, in-memory closures are
  gone. So each step also journals a *named* compensation and its
  JSON-serialisable arguments. A separate `recover()` replays those from a
  registry of handlers. It is idempotent: recovering twice does not undo twice.

Compensation is best-effort. If one undo fails, the rest still run and the
failures are collected into a `CompensationError`. Undoing four of five and
telling you which one needs a hand beats stopping at the first failure.

## Run it

```bash
python3 demo.py             # a failed deploy that unwinds itself, plus crash recovery
python3 -m unittest -v      # 10 tests, no network
```

## Use it

```python
from saga import Saga

with Saga(journal_path="run.jsonl", registry=HANDLERS) as saga:
    rid = saga.step(
        "provision",
        action=lambda: provision(),
        compensate=lambda: deprovision(rid),          # fast, in-process
        comp_name="deprovision", comp_args={"rid": rid},  # durable, for recover()
    )
    saga.step("dns", action=lambda: add_dns(rid),
              compensate=lambda: del_dns(rid),
              comp_name="del_dns", comp_args={"rid": rid})
    # clean exit commits; any exception rolls back in reverse
```

After a crash, a separate process cleans up:

```python
from saga import recover
recover("run.jsonl", registry=HANDLERS)   # replays uncommitted compensations
```

## What it does not do

It does not make your individual tool calls atomic, and it does not retry. If a
forward action is itself half-done when it fails (a file partly written), the
compensation has to cope with that, the same as any saga. It gives you ordering,
reversal and a durable record of what was undone. The compensations are yours to
write correctly.

MIT. Steal what you need.
