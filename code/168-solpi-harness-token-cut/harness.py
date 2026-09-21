"""harness.py — a deterministic coding-agent loop simulator.

Replays a fixed trajectory of tool calls over real files and counts the exact
input tokens a chat-style agent would re-send to the model on every turn. Two
modes: `naive` (every observation stays verbatim forever) and `solpi` (the four
mechanisms in solpi.py apply). Same trajectory, same evidence, different bytes
on the wire.

No model is called. The measured quantity is cumulative input tokens, summed
over every model request, which is exactly what a real loop pays for.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from solpi import Observation, ntok

SYSTEM = (
    "You are a coding agent. You investigate failing tests, read source, and "
    "propose a fix. Use tools; reason briefly between them. Keep going until the "
    "root cause is identified and the fix is verified.")

ASSISTANT_STUB = (
    "Thought: I will take the next step towards the root cause.\n"
    "Action: (tool call)")


@dataclass
class Step:
    type: str                       # 'tool' | 'edit_verify' | 'boundary' | 'reopen' | 'answer'
    kind: str = ""                  # observation kind
    command: str = ""
    text: str = ""
    subtask: int = 0
    ref: int = -1                   # for 'reopen': index of the earlier tool step
    subtask_done: int = -1          # for 'boundary'


def _render_naive(o: Observation) -> str:
    return f"[{o.kind} from `{o.command}`]\n{o.full_text}"


def run(trajectory: list[Step], mode: str, fuse: bool = True,
        compact_on: bool = True) -> dict:
    assert mode in ("naive", "solpi")
    fuse = fuse and mode == "solpi"
    compact_on = compact_on and mode == "solpi"
    obs: list[Observation] = []
    step_obs: dict[int, Observation] = {}     # tool-step index -> its observation
    compacted: set[str] = set()
    cum = 0
    req = 0
    per_request: list[int] = []
    pending_open: str | None = None

    def do_request(extra_open: str | None = None) -> None:
        nonlocal cum, req
        req += 1
        open_h: set[str] = {extra_open} if extra_open else set()
        parts = [SYSTEM, "TASK: " + TASK]
        for o in obs:
            if mode == "naive":
                parts.append(_render_naive(o))
            else:
                parts.append(o.render(req, open_h, compacted))
        parts.append(ASSISTANT_STUB)
        t = ntok("\n\n".join(parts))
        cum += t
        per_request.append(t)

    def compact(subtask_done: int) -> None:
        for o in obs:
            if o.subtask == subtask_done and o.handle not in compacted:
                current = ntok(o.render(req + 1, set(), compacted))
                summary = ntok(o._summary_line())
                # economic gate: only compact if the saving beats the rewrite cost
                if current - summary > summary:
                    compacted.add(o.handle)

    for i, step in enumerate(trajectory):
        if step.type == "tool":
            do_request(extra_open=pending_open)
            pending_open = None
            o = Observation(step.kind, step.command, step.text, step.subtask,
                            added_at=req)
            obs.append(o)
            step_obs[i] = o
        elif step.type == "edit_verify":
            if not fuse:
                # two round trips: make the edit, then run the verify command
                do_request()
                obs.append(Observation("edit", step.command.split("&&")[0].strip(),
                                       "applied edit to big_module.py\n", step.subtask,
                                       added_at=req))
                do_request()
                obs.append(Observation("log", step.command.split("&&")[-1].strip(),
                                       step.text, step.subtask, added_at=req))
            else:
                # Action Fusion: edit and verify in one observation, one round trip
                do_request()
                obs.append(Observation("edit_verify", step.command, step.text,
                                       step.subtask, added_at=req))
        elif step.type == "boundary":
            if compact_on:
                compact(step.subtask_done)
        elif step.type == "reopen":
            pending_open = step_obs[step.ref].handle
        elif step.type == "answer":
            do_request(extra_open=pending_open)
            pending_open = None

    return {
        "mode": mode,
        "cum_input_tokens": cum,
        "requests": req,
        "per_request": per_request,
        "observations": obs,
    }


# The task string is set by the caller (demo) before run(); default kept generic.
TASK = ("A regression test is failing after a refactor. Find the root cause in "
        "the codebase and identify the fix.")
