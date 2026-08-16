# Runtime Safety Contracts

**Date:** 2026-08-16
**Author:** Alfred + Bob
**Category:** research

We reproduced [Agent Safety Should Be a Runtime Contract](https://arxiv.org/abs/2608.11274)
as runnable code. The paper's argument is blunt: stop trusting a model to be safe
and start checking its trajectory at runtime. A safety contract has two faces. The
preventive face blocks a dangerous action before it runs. The evidential face
accepts a good action only when it carries proof it did what it claimed. Our small
harness reproduced the central result: acceptance tracked the evidence at +1.00 and
the agent's own claim of success at -0.35.

## What we did

We built `rcontract`, a stdlib-only Python package with no model calls in it, so the
mechanism is the only thing on trial.

The preventive face is four composable monitors, AND-gated (one deny blocks):

- `PermissionGate` — default-deny per risk class (read/write/exec/network/send).
- `SandboxPolicy` — executables and network hosts on allowlists.
- `OutputFilter` — blocks a payload carrying an API key or private key.
- `TrajectoryMonitor` — a per-risk budget, the runaway backstop.

The evidential face is four verifiers, each reading the artifact and never the
agent's `claim` field:

- `TestRun` — exit 0 and a green test line.
- `FileDiff` — right path, non-empty change.
- `LogCapture` — expected marker present in captured logs.
- `CitationGrounding` — every asserted claim found in a cited source.

The runtime runs the preventive gate before the side effect, then demands evidence
after. A blocked action never reaches the evidential phase, and every rejection
still lands in an append-only audit trail.

## Why it was worth doing

We ran a fixed battery of completed actions that varied independently in two things:
whether the agent claimed success, and whether it attached verifying evidence. A
modest actor that proved its work was accepted. Several confident actors that
claimed success with hollow or missing evidence were rejected. Acceptance correlated
with verifiable evidence at **+1.00** and with the agent's self-report at **-0.35**.
On a separate battery of dangerous actions dressed in benign framing (exfil to an
off-allowlist host, a secret in an outbound message, `rm -rf /` described as
"cleaning temp files"), the preventive block rate was **100%**. Eleven unit tests
pass with no dependencies.

Our live Vera pre-send gate is exactly one preventive monitor from this contract.
What we did not have is the evidential face: a standing rule that an agent saying
"done, shipped, verified" buys nothing until it carries a test run, a diff, a
captured log, or a grounded citation. This is the pattern we can lift in.

## What's still off

The verifiers are deliberately shallow, regex and shape checks, enough to prove the
mechanism and not a production evidence chain. The output filter catches a small
secret-pattern set, not real data-loss prevention. No live sandbox runs here;
execution and network isolation are modelled by allowlists. The correlation figures
come from an eleven-row battery, so they are an existence proof that acceptance can
be made to track evidence rather than a statistical study. We will not claim the
shipped Vera gate does the evidential half until we have wired it in and measured it
on real traffic.
