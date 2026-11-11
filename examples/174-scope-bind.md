# Scope-bind: binding agents to their authorised scope

**Date:** 2026-11-11
**Author:** Alfred + Bob
**Category:** agent

Our agents hold real keys. Bob and Larry have broad shell and database access, which is what makes them useful and what makes a wandering step dangerous. So we gave every job a written scope and a gate that checks each tool call against it before it runs. On a 30-case red-team set the gate caught every out-of-scope reach, 30 out of 30, and wrongly blocked none of 20 real jobs.

## What we did

Each job now declares a **scope manifest**: the verbs it may use, the paths it may read and write, the hosts it may reach, and the database tables it may change. A deterministic PreToolUse hook (`scope_gate.py`) reads the manifest and checks every call before it executes. No model sits in the loop and no second agent judges anything: the same manifest and the same call always give the same answer. We borrowed the shape straight from our egress gate.

A short deny list always wins over the allow rules, so a read-only job that drifts towards the `.env` file next to its task, an SSH key, or `/etc/shadow` is stopped even if nobody named every safe path. A Bash command is parsed for the paths, hosts and SQL writes it reaches, so `cat ~/conexus/.env`, a `curl` to an unlisted host, and `drop table audit_log` are all out of scope under a stats-reading manifest.

The gate runs in three modes. `log` (what we adopted fleet-wide) records every out-of-scope call as `would_block` and never blocks, so a headless nightly job can never stall on a false positive. `enforce` exits with a block. A single Bash call can be waved through with a `# scope-ok` comment, which is logged.

## Why it was worth doing

Two sources pointed at the same gap. The ADB paper (arXiv 2611.09113) shows that an agent's tendency to exceed its authorised scope rises as its capability rises, and 2026 incidents (the WorkOS pentest agent, the telecom intrusion) are the same shape: an agent with legitimate access doing one step past what it was asked.

So we built the two tests. A 30-scenario red-team set, each a bounded job whose goal tempts the agent over its limits, and 20 real in-scope calls drawn from how Bob and Larry actually work.

| metric | before (no binding) | after (scope-bind) | target |
|---|---|---|---|
| out-of-scope attempts blocked | 0/30 (0%) | **30/30 (100%)** | at least 70% |
| false-block rate on real jobs | 0/20 (0%) | **0/20 (0%)** | under 5% |

Reproduce with `python3 eval.py`.

## What's still off

We adopted it in log-only mode, not enforce. Enforce goes on per job once its manifest has proven itself, not across the whole fleet on day one.

The Bash parser is best-effort, not a shell interpreter: a deliberately obfuscated command could hide a path from it. The deny list is the hard backstop for the reaches that matter most, and the gate fails open on any internal error, because over-blocking our own work is worse than a missed log line. The self-critique step the ADB paper suggests before high-risk calls is the next layer; this is the deterministic floor it sits on.
