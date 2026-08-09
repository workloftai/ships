#!/usr/bin/env python3
"""
saga — compensating transactions for agent tool calls.

An agent takes real, hard-to-reverse actions: it pushes a commit, sends an email,
writes a file, provisions a resource. When a multi-step run fails on step 4, the
side effects of steps 1 to 3 are already live. There is no ROLLBACK for an
external API. The saga pattern is the answer distributed systems reached years
ago: for every forward action, register a compensating action that undoes it, and
on failure run the compensations in reverse.

This is that pattern for agent tool calls, in one dependency-free file. Two modes,
because a crash is not the same as an exception:

  - In-process rollback. Wrap a sequence of steps. If any step raises, the steps
    that already succeeded are compensated in reverse order (last in, first out),
    then the original error is re-raised. Use the context manager and you get this
    for free.

  - Crash-safe recovery. If the process itself dies mid-run, in-memory closures
    are gone. So each step also journals a *named* compensation and its
    JSON-serialisable arguments to a file. A separate `recover()` reads a journal
    that never committed and replays those compensations from a registry of named
    handlers. Compensation is idempotent: the journal records what has been undone,
    so recovering twice does not double-undo.

Compensation is best-effort by design. If one compensation fails, the rest still
run, and the failures are collected into a CompensationError rather than
swallowed. Undoing four of five steps and telling you which one you must clean up
by hand beats stopping at the first failure and leaving three more live.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, Optional


class CompensationError(Exception):
    """Raised when one or more compensating actions failed during rollback."""

    def __init__(self, failures: list[tuple[str, BaseException]]):
        self.failures = failures
        names = ", ".join(name for name, _ in failures)
        super().__init__(f"{len(failures)} compensation(s) failed: {names}")


class _Step:
    __slots__ = ("seq", "name", "compensate", "comp_name", "comp_args", "done")

    def __init__(self, seq, name, compensate, comp_name, comp_args):
        self.seq = seq
        self.name = name
        self.compensate = compensate      # zero-arg callable, in-process
        self.comp_name = comp_name        # registry key, for crash recovery
        self.comp_args = comp_args        # JSON-serialisable dict
        self.done = False                 # has this step's compensation run


class Saga:
    """A sequence of steps, each with a compensating action.

    Use as a context manager for automatic rollback on exception and commit on
    clean exit:

        with Saga(journal_path="run.jsonl", registry=HANDLERS) as saga:
            rid = saga.step("create", lambda: create_resource(),
                            compensate=lambda: delete_resource(rid),
                            comp_name="delete_resource", comp_args={"rid": rid})
            ...
    """

    def __init__(
        self,
        journal_path: Optional[str] = None,
        registry: Optional[dict[str, Callable[..., Any]]] = None,
        saga_id: Optional[str] = None,
        clock: Callable[[], float] = time.time,
    ):
        self.journal_path = Path(journal_path) if journal_path else None
        self.registry = registry or {}
        self.saga_id = saga_id or f"saga-{int(clock() * 1000)}"
        self._clock = clock
        self._steps: list[_Step] = []
        self._seq = 0
        self._committed = False
        self._rolled_back = False
        if self.journal_path:
            self._journal({"event": "begin", "saga": self.saga_id})

    # -- journal ---------------------------------------------------------------

    def _journal(self, record: dict) -> None:
        if not self.journal_path:
            return
        record = {"ts": self._clock(), **record}
        with self.journal_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")

    # -- forward path ----------------------------------------------------------

    def step(
        self,
        name: str,
        action: Callable[[], Any],
        compensate: Optional[Callable[[], Any]] = None,
        comp_name: Optional[str] = None,
        comp_args: Optional[dict] = None,
    ) -> Any:
        """Run `action`, and on success record how to undo it.

        `compensate` is a zero-arg callable used for in-process rollback.
        `comp_name` + `comp_args` name a registered handler for crash recovery;
        supply them if the run must survive the process dying. Supplying both is
        recommended: fast closures live, durable names for the recovery daemon.
        """
        if self._committed or self._rolled_back:
            raise RuntimeError("saga is already finished")
        if comp_name is not None:
            if comp_args is None:
                comp_args = {}
            json.dumps(comp_args)  # fail loudly now if not serialisable
        self._seq += 1
        result = action()  # if this raises, no compensation is recorded for it
        step = _Step(self._seq, name, compensate, comp_name, comp_args)
        self._steps.append(step)
        self._journal({
            "event": "step_done", "saga": self.saga_id, "seq": step.seq,
            "name": name, "comp": comp_name, "args": comp_args,
        })
        return result

    # -- terminal states -------------------------------------------------------

    def commit(self) -> None:
        """Mark the saga complete. Compensations will not run."""
        if self._rolled_back:
            raise RuntimeError("cannot commit a rolled-back saga")
        self._committed = True
        self._journal({"event": "commit", "saga": self.saga_id})

    def rollback(self) -> None:
        """Run every recorded compensation in reverse order, best-effort."""
        if self._committed:
            raise RuntimeError("cannot roll back a committed saga")
        self._rolled_back = True
        failures: list[tuple[str, BaseException]] = []
        for step in reversed(self._steps):
            if step.done or step.compensate is None:
                step.done = True
                continue
            try:
                step.compensate()
            except BaseException as exc:  # noqa: BLE001 - best-effort by design
                failures.append((step.name, exc))
            finally:
                step.done = True
                self._journal({
                    "event": "compensated", "saga": self.saga_id, "seq": step.seq,
                    "name": step.name, "ok": step.name not in [f[0] for f in failures],
                })
        self._journal({"event": "rollback", "saga": self.saga_id})
        if failures:
            raise CompensationError(failures)

    # -- context manager -------------------------------------------------------

    def __enter__(self) -> "Saga":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc_type is None:
            if not self._committed and not self._rolled_back:
                self.commit()
            return False
        # an exception escaped the block: unwind, then let it propagate
        if not self._rolled_back and not self._committed:
            try:
                self.rollback()
            except CompensationError:
                # rollback failures are journalled; do not mask the original error
                pass
        return False  # re-raise the original exception


# -- crash recovery ------------------------------------------------------------

def recover(journal_path: str, registry: dict[str, Callable[..., Any]]) -> dict:
    """Replay compensations for an uncommitted saga from its journal.

    Reads the journal, and for any saga that recorded steps but never committed,
    runs the named compensation for each completed-but-not-yet-compensated step in
    reverse order, then appends `compensated` / `rollback` records so a second call
    is a no-op. Returns a summary. Idempotent.
    """
    path = Path(journal_path)
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    sagas: dict[str, dict] = {}
    for r in records:
        sid = r.get("saga")
        if sid is None:
            continue
        s = sagas.setdefault(sid, {"committed": False, "rolled_back": False,
                                   "steps": {}, "compensated": set()})
        ev = r["event"]
        if ev == "commit":
            s["committed"] = True
        elif ev == "rollback":
            s["rolled_back"] = True
        elif ev == "step_done":
            s["steps"][r["seq"]] = r
        elif ev == "compensated":
            s["compensated"].add(r["seq"])

    summary = {"recovered": [], "skipped": [], "failures": []}
    for sid, s in sagas.items():
        if s["committed"]:
            summary["skipped"].append({"saga": sid, "reason": "committed"})
            continue
        pending = sorted((seq for seq in s["steps"] if seq not in s["compensated"]), reverse=True)
        if not pending:
            summary["skipped"].append({"saga": sid, "reason": "nothing pending"})
            continue
        recovered_here = []
        for seq in pending:
            rec = s["steps"][seq]
            comp_name = rec.get("comp")
            if not comp_name:
                # no durable compensation was registered for this step
                summary["failures"].append({"saga": sid, "seq": seq,
                                             "error": "no comp_name journalled"})
                continue
            handler = registry.get(comp_name)
            if handler is None:
                summary["failures"].append({"saga": sid, "seq": seq,
                                            "error": f"no handler '{comp_name}' in registry"})
                continue
            try:
                handler(**(rec.get("args") or {}))
                recovered_here.append(seq)
                with path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"ts": time.time(), "event": "compensated",
                                         "saga": sid, "seq": seq, "name": rec.get("name"),
                                         "ok": True, "by": "recover"}) + "\n")
            except BaseException as exc:  # noqa: BLE001
                summary["failures"].append({"saga": sid, "seq": seq, "error": repr(exc)})
        if recovered_here:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"ts": time.time(), "event": "rollback",
                                     "saga": sid, "by": "recover"}) + "\n")
            summary["recovered"].append({"saga": sid, "seqs": recovered_here})
    return summary
