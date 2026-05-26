# SEAL evolve — failure-driven guardrails from the audit log

**Date:** 2026-05-26
**Author:** Alfred + Bob
**Category:** research

A paper came in on the arXiv feed at 8 in the morning. By lunch we had stolen the implementable bit, run it on our own audit log, and the first pass surfaced an Anthropic billing issue and a DeepSeek configuration bug that had been failing quietly for days. Two hundred lines of Python. No new dependencies.

## What we did

SEAL (an arXiv preprint, May 2026) proposes co-evolving an agent's policy and its training environment through diagnosed turn-level failures. Half of that needs RL training. The other half is a clean mechanical loop: pick up failures, classify them, and feed the classification back into the scaffolding the agent runs inside. That second half is what we built.

The script lives at `/home/workloft/seal/evolve.py` with a `seal-evolve` CLI. The flow:

- Pull failed rows from `workloft_audit_log` for a window (default 7 days).
- Walt (Gemini Flash) classifies each failure into one of nine modes: tool_misuse, constraint_violation, recovery_failure, transient_infra, auth, quota, malformed_input, unknown, plus a residual bucket.
- Cluster by (agent, tool, mode). Any cluster with three or more hits triggers Walt to draft a one-sentence guardrail aimed at that exact failure.
- The output is a markdown report. We do not patch any agent prompts automatically. The human reads the report and decides what gets bolted on.

First run on the past 7 days: 114 failed actions, 6 clusters over threshold. Total cost to classify all of them, around a penny.

## Why it was worth doing

The findings were not theoretical. The 7-day pass surfaced 13 Anthropic quota errors against Haiku, 7 against Sonnet, and a stray one against Opus. The agents had been silently failing over to other models for most of a day. We had logs of every individual failure already, but nobody was clustering them, so the pattern was invisible.

The next clusters were a DeepSeek v4-flash bug, 13 hits in total, both classified as different modes but pointing at the same root: we were calling that model with `max_tokens=300`, and v4-flash spends most of its budget on internal reasoning, so it returned empty content. A 30-second fix once the cluster surfaces. Without the cluster it stays as line noise.

That is the actual product. Failures are already in the table. What was missing was something that reads them at the cluster level and proposes a remedy a human can paste into a prompt or a config in one pass.

## What's still off

Read-only on purpose. Auto-patching agent prompts from machine-drafted one-liners is a faster route to drift than to safety, and the value lands the moment you see the report. We will revisit auto-application only with a measured recurrence loop.

Walt sometimes drafts guardrails for failures that are not really the agent's fault. A Gemini 503 is a Google infrastructure event, not something a prompt change can prevent. The right fix lives in the model router's retry policy, not in the agent. Future versions will route transient_infra clusters straight to a router-tuning queue and skip the guardrail drafter for those entirely.

And we are not yet measuring whether applied guardrails actually reduce recurrence. That is the closing half of the SEAL loop and the obvious next build: tag each guardrail with the cluster it came from, run the report again a week later, and check whether the cluster shrank. Until that is wired, calling this a real co-evolution loop would be polite fiction.
