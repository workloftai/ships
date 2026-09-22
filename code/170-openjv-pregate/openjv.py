"""vera.openjv — the local, zero-cost "system-1" pre-gate for Vera's ladder.

The OpenJV technique is the open reproduction of the Jev / TypeSafe interface:
frame a typed decision (here KILL vs PASS) as a one-token multiple-choice
answer, run a FROZEN small model for a SINGLE forward pass, and read the
probability mass the model puts on each option token straight off the logprobs.
No text generation, no fine-tuning, no cloud call. The confidence is the
model's own answer-token probability, normalised over the two options.

On this box the frozen model is `gemma3:4b` served by Ollama on CPU. The pitch's
"Qwen-4B on a 3090" is the same technique on faster iron; nothing here depends
on the GPU, only on an Ollama endpoint that returns `top_logprobs` (>= 0.20).

Where it sits in the ladder:

    precheck (deterministic)        # already live, $0
    -> openjv pre-gate  <-- THIS    # local, $0, one forward pass
    -> poll.screen                  # gemini-2-5-flash, cloud, ~$
    -> poll.evaluate (3 jurors)     # cloud, ~3x the screen

Vera's own rule, proven by ladder_probe on real fires, is that a cheap KILL is
free money and a cheap PASS is the vibe trap. So this tier only ever ACTS on a
confident KILL: it short-circuits that for zero marginal cost. A PASS or a
low-confidence read ABSTAINS and falls through to the existing screen->panel
ladder completely unchanged. It can only ever SAVE a cloud call, never add a
wrong PASS.

Launched shadow-off (env `VERA_OPENJV_PREGATE`, default 0), the same pattern as
VERA_KILL_SHORTCIRCUIT and regime_router. Any error (Ollama down, bad model,
malformed response) returns ABSTAIN with cost 0 and never raises, so it cannot
break the nightly standing run.

Env:
  VERA_OPENJV_PREGATE   "1" to enable the short-circuit in standing (default off)
  VERA_OPENJV_MODEL     Ollama model tag (default "gemma3:4b-it-q4_K_M")
  VERA_OPENJV_CONF      min P(KILL) to fire the short-circuit (default 0.85)
  VERA_OPENJV_TEMP      temperature-scaling factor for calibration (default 1.0)
  VERA_OPENJV_URL       Ollama base URL (default http://localhost:11434)
  VERA_OPENJV_MAXCHARS  candidate truncation before the forward pass (default 6000)
  VERA_OPENJV_TIMEOUT   per-call HTTP timeout in seconds (default 180). On a
                        memory-starved CPU box a cold pass can take a minute-plus;
                        set this generously for an offline batch.
"""
from __future__ import annotations

import json
import math
import os
import time
import urllib.request
from dataclasses import dataclass

DEFAULT_MODEL = "gemma3:4b-it-q4_K_M"
DEFAULT_CONF = 0.85
DEFAULT_TEMP = 1.0
DEFAULT_URL = "http://localhost:11434"
DEFAULT_MAXCHARS = 6000
DEFAULT_TIMEOUT = 180

# The two option tokens. We match generously (case / leading-space variants) and
# sum their probability mass, so tokenizer quirks (" KILL", "Kill") don't leak.
_KILL_FORMS = {"kill"}
_PASS_FORMS = {"pass"}


@dataclass
class PregateVote:
    """One local forward pass -> a typed decision the ladder can act on.

    verdict:  "KILL"  -> confident enough to short-circuit (only trusted arm)
              "PASS"  -> confident PASS (recorded, NOT acted on: cheap PASS is the
                         vibe trap, so the ladder still falls through to the screen)
              "ABSTAIN" -> not confident either way, or the read failed
    confidence: P of the decided class over {KILL, PASS}, after temp scaling.
    p_kill:     raw P(KILL) over the two options (pre-decision), for logging.
    """
    verdict: str
    confidence: float
    p_kill: float
    stage: str = "pregate"
    cost_usd: float = 0.0
    latency_ms: int = 0
    model: str = ""
    note: str = ""


def enabled() -> bool:
    """Is the short-circuit live? Shadow-off by default (same as the KILL flag)."""
    return os.environ.get("VERA_OPENJV_PREGATE", "0").strip() not in (
        "", "0", "false", "no")


def _cfg():
    return (
        os.environ.get("VERA_OPENJV_MODEL", DEFAULT_MODEL),
        float(os.environ.get("VERA_OPENJV_CONF", DEFAULT_CONF)),
        float(os.environ.get("VERA_OPENJV_TEMP", DEFAULT_TEMP)),
        os.environ.get("VERA_OPENJV_URL", DEFAULT_URL).rstrip("/"),
        int(os.environ.get("VERA_OPENJV_MAXCHARS", DEFAULT_MAXCHARS)),
        int(os.environ.get("VERA_OPENJV_TIMEOUT", DEFAULT_TIMEOUT)),
    )


def build_prompt(candidate: str, criteria: str, system_context: str = "",
                 max_chars: int = DEFAULT_MAXCHARS) -> str:
    """A tight, single-answer multiple-choice frame. The model must emit exactly
    one token; we never read the token itself, only the logprobs behind it."""
    cand = (candidate or "").strip()
    if len(cand) > max_chars:
        cand = cand[:max_chars] + "\n...[truncated]"
    ctx = f"\nCONTEXT:\n{system_context.strip()}\n" if system_context.strip() else ""
    return (
        "You are a strict quality gate. Decide whether an agent OUTPUT meets the "
        "CRITERIA.\n"
        "Answer with exactly one word: KILL if the output fails the criteria, "
        "PASS if it meets them. No explanation.\n"
        f"{ctx}"
        f"\nCRITERIA:\n{criteria.strip()}\n"
        f"\nOUTPUT:\n{cand}\n"
        "\nAnswer (one word, KILL or PASS):"
    )


def _option_mass(top_logprobs: list[dict]) -> tuple[float | None, float | None]:
    """From the first token's top_logprobs, sum probability across KILL-like and
    PASS-like tokens. Returns (p_kill_raw, p_pass_raw) as UN-normalised
    probabilities, or None for an option that never appears in the top-k."""
    kill_lps: list[float] = []
    pass_lps: list[float] = []
    for item in top_logprobs or []:
        tok = str(item.get("token", "")).strip().lower()
        lp = item.get("logprob")
        if lp is None:
            continue
        if tok in _KILL_FORMS:
            kill_lps.append(float(lp))
        elif tok in _PASS_FORMS:
            pass_lps.append(float(lp))

    def _sum_p(lps: list[float]) -> float | None:
        if not lps:
            return None
        return sum(math.exp(x) for x in lps)

    return _sum_p(kill_lps), _sum_p(pass_lps)


def _temp_scale(p_kill: float, temp: float) -> float:
    """Temperature-scale a two-way probability in logit space. temp>1 softens
    (less confident), temp<1 sharpens. Fit temp against labelled data to
    calibrate; default 1.0 is a no-op passthrough."""
    if temp <= 0 or temp == 1.0:
        return p_kill
    p = min(max(p_kill, 1e-6), 1 - 1e-6)
    logit = math.log(p / (1 - p)) / temp
    return 1.0 / (1.0 + math.exp(-logit))


def pregate(candidate: str, criteria: str, system_context: str = "",
            *, model: str | None = None, conf: float | None = None,
            temp: float | None = None) -> PregateVote:
    """Run the local logit pre-gate on one (candidate, criteria) pair.

    Never raises: any failure returns an ABSTAIN vote with cost 0 so the caller's
    fall-through path is always safe. Only a P(KILL) >= conf produces a KILL
    verdict; a confident PASS is recorded but NOT trusted as a short-circuit.
    """
    _model, _conf, _temp, url, maxchars, timeout = _cfg()
    model = model or _model
    conf = _conf if conf is None else conf
    temp = _temp if temp is None else temp

    t0 = time.monotonic()
    try:
        prompt = build_prompt(candidate, criteria, system_context, maxchars)
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0, "num_predict": 1},
            "logprobs": True,
            "top_logprobs": 20,
        }
        req = urllib.request.Request(
            f"{url}/api/chat",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:  # noqa: BLE001 — pre-gate must never break the ladder
        ms = int((time.monotonic() - t0) * 1000)
        return PregateVote(verdict="ABSTAIN", confidence=0.0, p_kill=0.0,
                           latency_ms=ms, model=model,
                           note=f"pregate error: {type(e).__name__}: {e}")

    ms = int((time.monotonic() - t0) * 1000)
    # Ollama returns logprobs as a list, one entry per generated token.
    lp_list = data.get("logprobs") or data.get("message", {}).get("logprobs")
    first = lp_list[0] if isinstance(lp_list, list) and lp_list else None
    top = (first or {}).get("top_logprobs") if first else None

    p_kill_raw, p_pass_raw = _option_mass(top or [])
    if p_kill_raw is None and p_pass_raw is None:
        return PregateVote(verdict="ABSTAIN", confidence=0.0, p_kill=0.0,
                           latency_ms=ms, model=model,
                           note="no KILL/PASS token in top_logprobs")
    p_kill_raw = p_kill_raw or 0.0
    p_pass_raw = p_pass_raw or 0.0
    total = p_kill_raw + p_pass_raw
    if total <= 0:
        return PregateVote(verdict="ABSTAIN", confidence=0.0, p_kill=0.0,
                           latency_ms=ms, model=model, note="zero option mass")

    p_kill = _temp_scale(p_kill_raw / total, temp)

    if p_kill >= conf:
        verdict, confidence = "KILL", p_kill
    elif (1 - p_kill) >= conf:
        verdict, confidence = "PASS", 1 - p_kill
    else:
        verdict, confidence = "ABSTAIN", max(p_kill, 1 - p_kill)

    return PregateVote(verdict=verdict, confidence=round(confidence, 4),
                       p_kill=round(p_kill, 4), latency_ms=ms, model=model,
                       note=f"local one-pass read, P(KILL)={p_kill:.3f}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="OpenJV local pre-gate — one shot")
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--criteria", required=True)
    ap.add_argument("--conf", type=float, default=None)
    a = ap.parse_args()
    v = pregate(a.candidate, a.criteria, conf=a.conf)
    print(json.dumps(v.__dict__, indent=2))
