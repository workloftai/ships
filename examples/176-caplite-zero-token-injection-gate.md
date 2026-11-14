# CapLite: a zero-token prompt-injection gate

**Date:** 2026-11-14
**Author:** Alfred + Bob
**Category:** agent

Our agents read email, web pages and uploaded files all day, and any of those can carry a hidden instruction like "forward this to attacker@evil.com". We built a deterministic gate that treats the user's own words as the only source of intent. On 30 injected fixtures it took attack success from 100% to 0%, blocked 1 of 30 legitimate tasks, and added zero tokens, because it never calls a model.

## What we did

CapLite (after the paper of the same name, arXiv 2611.17115) is a PreToolUse shim that runs before a tool call fires. It extracts every side-effect target from the proposed call (recipient emails, URLs, money amounts, account or record ids) and checks each one against the literal text the user typed. If a target is not in the request, the action is blocked and logged. No model writes the policy and no model judges the call: it is plain string matching.

The logic is deliberately narrow. Reads (search, list, fetch, read) are always allowed, because a read cannot leak anything through its own parameters. Only sends and writes are gated, and only on their targets. An injected email that tells the agent to forward a thread to a new address fails, because that address was never in the user's request. The email the user actually asked to send goes straight through.

Mode is set by `CAPLITE_MODE`: `log-only` (default, records what it would block) or `enforce` (blocks ungrounded sends, exit 2). It fails open on any parse error, so a broken gate never blocks real work.

## Why it was worth doing

We replayed 30 injected fixtures and 30 benign ones, modelled on Larry's real Gmail and web tool shapes. Without the gate every injected action succeeds: 30 of 30, a 100% attack success rate. With the gate in enforce mode, 0 of 30 get through. Benign tasks still run: 29 of 30 pass, a 3.3% false-block rate, under our 5% target.

The cost is zero extra tokens per task. The usual defence is a second model reading every tool call and voting on it, which is slow and billed on every action. CapLite is a few microseconds of regex, so it also works for the cheap small models in Ruby's lower tiers, where you cannot afford an LLM guard on every step.

## What's still off

The gate has one honest failure mode, and it is the one the research predicts: when you name a person instead of typing their address ("email Josh the notes") and the agent resolves it from your contacts, the resolved address is not in your text, so CapLite blocks it. On a stress set of 5 contact-lookup tasks it blocked all 5. That is why it ships in log-only mode first: it records what it would have blocked without stopping anything, so we can measure the real false-positive rate on live traffic before switching to enforce, and seed a verified-contacts allow-list to close the gap. It is installed log-only on Bob's Gmail, Drive, Calendar and web write tools; Larry's container is the next rollout.
