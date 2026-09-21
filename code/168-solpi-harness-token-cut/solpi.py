"""solpi.py — token-efficient agent-harness mechanisms, measured honestly.

A small, dependency-light reimplementation of the four harness mechanisms from
SoL-Pi (arXiv:2609.20519), plus a deterministic loop simulator that counts the
exact tokens a coding agent would re-send to the model across a trajectory.

The point is not to reproduce the paper's number. It is to measure OUR number,
on a real trajectory over real files, with a real tokenizer (tiktoken o200k),
and to prove no evidence is lost in the process.

Why input tokens: a chat-style agent re-sends its whole transcript on every
turn, so cumulative input tokens (sum over requests of the context size) is
where the money goes. Every mechanism here shrinks what gets re-sent, never the
underlying evidence, which stays byte-exact behind a retrievable handle.

The four mechanisms (paper name -> what it does here):
  * Action Fusion            fuse an edit and its verify command into one
                             observation, removing a whole model round trip.
  * ObservationPack          large generic outputs (>10 KiB) go full for two
                             requests, then collapse to handle + head/tail.
  * Evidence-Preserving      build/test logs (>=4 KiB) collapse to a verified
    Reducer                  receipt (exit status, error lines, head/tail),
                             with fallback to the full log if it fails to shrink.
  * Online Context Compact   at a subtask boundary, consumed observations
                             collapse to one line, but only when the projected
                             saving beats the rewrite cost.

Deterministic note: the paper's reducer calls a cheap model to extract the
receipt. We extract deterministically (no model, no cost, no flake) and verify
by size. Same mechanism, stricter guarantee.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

import tiktoken

ENC = tiktoken.get_encoding("o200k_base")

# --- mechanism parameters (paper values where the paper gives them) -----------
PACK_THRESHOLD = 10 * 1024      # ObservationPack: archive outputs over 10 KiB
PACK_FULL_REQUESTS = 2          # ...but keep them full for the first two requests
REDUCE_THRESHOLD = 4 * 1024     # Evidence reducer: logs at/above 4 KiB
HEAD_LINES = 8                  # excerpt sizes for pack / receipt
TAIL_LINES = 8
MAX_EVIDENCE_LINES = 40         # cap on error lines carried in a receipt
# Commands whose output the reducer is allowed to touch (build/test only).
LOG_COMMANDS = ("pytest", "unittest", "make", "npm test", "npm run build",
                "pip download", "pip install", "cargo", "go test", "gradle")
_EVIDENCE_RE = re.compile(
    r"(FAIL|FAILED|ERROR|ERR!|Traceback|AssertionError|Exception|"
    r"\bWARN(ING)?\b|panic:|error\[)", re.IGNORECASE)


def ntok(s: str) -> int:
    """Exact token count under the o200k_base tokenizer (GPT-4o / 5 family)."""
    return len(ENC.encode(s))


def _human(n: int) -> str:
    for unit in ("B", "KiB", "MiB"):
        if n < 1024 or unit == "MiB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n/1024:.1f} {unit}"
        n /= 1024
    return f"{n} B"


@dataclass
class Observation:
    """One tool result in the transcript. Renders differently as it ages."""
    kind: str                    # 'file' | 'grep' | 'log' | 'edit_verify' | 'note'
    command: str                 # the tool call that produced it
    full_text: str               # byte-exact result, archived forever
    subtask: int                 # which plan step produced it
    added_at: int = 0            # request index when it entered the transcript
    handle: str = ""             # stable retrieval handle

    def __post_init__(self):
        self.size = len(self.full_text.encode("utf-8"))
        self.sha = hashlib.sha256(self.full_text.encode("utf-8")).hexdigest()
        if not self.handle:
            self.handle = f"obs://{self.sha[:8]}"

    # -- mechanism selection --------------------------------------------------
    @property
    def mechanism(self) -> str:
        cmd = self.command.lower()
        if self.kind == "log" and self.size >= REDUCE_THRESHOLD \
                and any(c in cmd for c in LOG_COMMANDS):
            return "reduce"
        if self.size >= PACK_THRESHOLD:
            return "pack"
        return "plain"

    # -- renderers ------------------------------------------------------------
    def _excerpt(self) -> str:
        lines = self.full_text.splitlines()
        head = "\n".join(lines[:HEAD_LINES])
        tail = "\n".join(lines[-TAIL_LINES:])
        return (f"[archived {self.kind} from `{self.command}`: {_human(self.size)}, "
                f"sha256:{self.sha[:8]}, {len(lines)} lines, retrieve via {self.handle}]\n"
                f"{head}\n...\n{tail}")

    def _receipt(self) -> str:
        lines = self.full_text.splitlines()
        exit_status = "unknown"
        if re.search(r"\bFAILED\b|Traceback", self.full_text):
            exit_status = "failure"
        elif re.search(r"\bOK\b|passed|SUCCESS", self.full_text):
            exit_status = "ok"
        evidence = [ln for ln in lines if _EVIDENCE_RE.search(ln)][:MAX_EVIDENCE_LINES]
        head = "\n".join(lines[:HEAD_LINES])
        tail = "\n".join(lines[-TAIL_LINES:])
        parts = [f"[log receipt for `{self.command}` | exit={exit_status} | "
                 f"{_human(self.size)} archived, sha256:{self.sha[:8]}, retrieve via {self.handle}]"]
        if evidence:
            parts.append("signals:\n" + "\n".join(evidence))
        parts.append("--- head ---\n" + head)
        parts.append("--- tail ---\n" + tail)
        return "\n".join(parts)

    def _summary_line(self) -> str:
        return (f"[compacted {self.kind} from `{self.command}`: {_human(self.size)}, "
                f"sha256:{self.sha[:8]}, retrieve via {self.handle}]")

    def render(self, req_idx: int, open_handles: set[str],
               compacted: set[str]) -> str:
        """How this observation appears in the context at request `req_idx`."""
        # An explicit re-open always wins: exact bytes come back.
        if self.handle in open_handles:
            return self.full_text
        # A finished subtask collapses to a single line (Online Context Compact).
        if self.handle in compacted:
            return self._summary_line()
        mech = self.mechanism
        if mech == "reduce":
            receipt = self._receipt()
            # verify: only keep the receipt if it actually shrinks the log
            return receipt if ntok(receipt) < ntok(self.full_text) else self.full_text
        if mech == "pack":
            if req_idx - self.added_at < PACK_FULL_REQUESTS:
                return self.full_text
            return self._excerpt()
        return self.full_text
