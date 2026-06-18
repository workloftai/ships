"""harness_gate — put an independent reviewer back into a self-improving agent loop.

Background
----------
Self-Harness (arXiv:2606.09498) lets an LLM agent improve its own harness:
it mines its own failures, proposes edits to its own scaffolding, and
"accepts candidate edits only after regression testing". Read as a control,
that last step is a producer grading its own work — the proposer, the test,
and the regression set are one system with one objective: pass the bench.

This module is the governed version. It keeps the self-improvement loop but
enforces three properties the paper leaves out, each as a structural fact of
the code rather than a promise:

  1. Separation of duties. The Proposer cannot see the Gate's evaluation set,
     and the Gate never trusts the Proposer's self-reported score — it
     recomputes on its own held-out set. Enforced by construction: neither
     object holds a reference to the other's data.

  2. Independent acceptance. An edit is accepted only if the Gate's held-out
     score does not regress and clears an absolute floor. The edit that
     overfits the proposer's visible "dev" set is exactly the one this catches.

  3. Tamper-evident record. Every proposal — accepted or rejected — is appended
     to a hash-chained log pinned to the harness version live for it. Altering
     any past entry breaks the chain, so "the harness changed itself" becomes
     something you can evidence rather than screenshot.

A "harness" here is a plain config dict and the eval is a deterministic toy, so
the demo proves the *control structure*, not a model. Swapping in a real LLM
proposer and a real task suite is a drop-in: implement Proposer.propose() and
hand the Gate a held-out slice the proposer never receives.
"""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from typing import Callable, Mapping, Sequence

# A harness is just a config the scaffolding reads. Edits mutate this.
Harness = dict
# A task scorer: given a harness, return True if the task passes under it.
Task = Callable[[Harness], bool]


@dataclass(frozen=True)
class HarnessEdit:
    """A proposed change to the harness, plus the proposer's own claim.

    `claimed_delta` is what the proposer measured on the data it can see. The
    Gate treats it as a claim to be checked, never as evidence.
    """
    description: str
    patch: Mapping[str, object]
    claimed_delta: float


def score(harness: Harness, tasks: Sequence[Task]) -> float:
    """Fraction of tasks that pass under this harness."""
    if not tasks:
        return 0.0
    return sum(1 for t in tasks if t(harness)) / len(tasks)


def apply_patch(harness: Harness, patch: Mapping[str, object]) -> Harness:
    new = copy.deepcopy(harness)
    new.update(patch)
    return new


class Proposer:
    """Mines weaknesses and proposes edits using ONLY its visible dev set.

    It deliberately does not receive, and cannot reach, the Gate's held-out
    set. That gap is the point: the proposer optimises towards the edge of what
    it can see, which is where overfitting lives.
    """

    def __init__(self, dev_tasks: Sequence[Task], candidates: Sequence[HarnessEdit]):
        self._dev = dev_tasks
        self._candidates = candidates

    def propose(self, harness: Harness) -> list[HarnessEdit]:
        """Return candidate edits, each tagged with the proposer's own dev delta.

        The proposer self-reports improvement on the set it controls. This is
        exactly the "accepts after regression testing" signal Self-Harness
        trusts — and the signal the Gate refuses to take on faith.
        """
        base = score(harness, self._dev)
        out: list[HarnessEdit] = []
        for cand in self._candidates:
            dev_after = score(apply_patch(harness, cand.patch), self._dev)
            out.append(HarnessEdit(cand.description, cand.patch, dev_after - base))
        # Proposer ranks by its own visible gain — overfit edits float to the top.
        return sorted(out, key=lambda e: e.claimed_delta, reverse=True)


@dataclass
class Verdict:
    edit: HarnessEdit
    accepted: bool
    held_out_before: float
    held_out_after: float
    reason: str


class ReviewGate:
    """Independent acceptance. Holds a private held-out set; recomputes scores.

    The proposer's claimed_delta is recorded for the audit trail but plays no
    part in the decision. Acceptance requires (a) no regression on the held-out
    set and (b) clearing an absolute floor.
    """

    def __init__(self, held_out_tasks: Sequence[Task], floor: float = 0.0,
                 min_gain: float = 1e-9):
        self._held_out = held_out_tasks
        self._floor = floor
        self._min_gain = min_gain

    def review(self, harness: Harness, edit: HarnessEdit) -> Verdict:
        before = score(harness, self._held_out)
        after = score(apply_patch(harness, edit.patch), self._held_out)
        if after + 1e-12 < before:
            return Verdict(edit, False, before, after,
                           f"held-out regressed {before:.2f} -> {after:.2f}")
        if after < self._floor:
            return Verdict(edit, False, before, after,
                           f"held-out {after:.2f} below floor {self._floor:.2f}")
        if after - before < self._min_gain:
            return Verdict(edit, False, before, after,
                           "no held-out gain (proposer's dev gain did not generalise)")
        return Verdict(edit, True, before, after,
                       f"held-out improved {before:.2f} -> {after:.2f}")


@dataclass
class LogEntry:
    index: int
    harness_version: int
    edit_description: str
    patch: dict
    claimed_delta: float
    held_out_before: float
    held_out_after: float
    accepted: bool
    reason: str
    prev_hash: str
    entry_hash: str = ""

    def _digest(self) -> str:
        body = {k: v for k, v in self.__dict__.items() if k != "entry_hash"}
        blob = json.dumps(body, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode()).hexdigest()


class ChangeLog:
    """Append-only, hash-chained record of every proposal seen by the loop.

    Each entry's hash covers the previous hash, so any retroactive edit to a
    past entry breaks every hash after it. verify() walks the chain.
    """
    GENESIS = "0" * 64

    def __init__(self) -> None:
        self.entries: list[LogEntry] = []

    def append(self, *, harness_version: int, verdict: Verdict) -> LogEntry:
        prev = self.entries[-1].entry_hash if self.entries else self.GENESIS
        entry = LogEntry(
            index=len(self.entries),
            harness_version=harness_version,
            edit_description=verdict.edit.description,
            patch=dict(verdict.edit.patch),
            claimed_delta=round(verdict.edit.claimed_delta, 6),
            held_out_before=round(verdict.held_out_before, 6),
            held_out_after=round(verdict.held_out_after, 6),
            accepted=verdict.accepted,
            reason=verdict.reason,
            prev_hash=prev,
        )
        entry.entry_hash = entry._digest()
        self.entries.append(entry)
        return entry

    def verify(self) -> bool:
        prev = self.GENESIS
        for e in self.entries:
            if e.prev_hash != prev or e.entry_hash != e._digest():
                return False
            prev = e.entry_hash
        return True


@dataclass
class GovernedLoop:
    """The Self-Harness loop with the reviewer put back in.

    propose -> gate.review -> (accept mutates harness) -> log every outcome.
    The harness version increments only on an accepted edit, so each log entry
    is pinned to the exact scaffolding that was live when the edit was judged.
    """
    harness: Harness
    proposer: Proposer
    gate: ReviewGate
    log: ChangeLog = field(default_factory=ChangeLog)
    version: int = 0

    def step(self) -> list[Verdict]:
        verdicts: list[Verdict] = []
        for edit in self.proposer.propose(self.harness):
            verdict = self.gate.review(self.harness, edit)
            self.log.append(harness_version=self.version, verdict=verdict)
            if verdict.accepted:
                self.harness = apply_patch(self.harness, edit.patch)
                self.version += 1
            verdicts.append(verdict)
        return verdicts
