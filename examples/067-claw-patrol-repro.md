# Reproducing Claw Patrol's agent firewall

**Date:** 2026-06-21
**Author:** Alfred + Bob
**Category:** research

Deno open-sourced [Claw Patrol](https://clawpatrol.dev/), a firewall that sits between an agent and production and gates each action at the wire: block a `DROP TABLE`, pause a `kubectl delete` until a human signs off. We rebuilt its core in an afternoon to find out what actually does the security work. The credential trick is the gem. The parser is the part that will bite you.

## What we did

We reproduced the three load-bearing mechanisms deterministically, with no network and no model calls:

- **Wire-level fact extraction.** Parse the bytes an agent puts on the wire into protocol-native facts: a Postgres verb plus table plus has-where, a kubectl verb plus resource plus namespace, an HTTP method plus host plus path. Rules bind to what the agent is actually doing, not to a self-reported tool name.
- **An HCL-style rule engine.** Operators write allow/deny/approve rules against those facts. First matching rule wins; anything unmatched is default-denied.
- **Credential injection on the wire.** The agent holds only a placeholder like `{{github_pat}}`. The gateway swaps in the real secret as bytes leave for the destination, so a compromised agent process never holds a key it could leak.

We then wrote 16 functional cases and a separate parser-evasion probe, and attacked our own parser. All 16 functional cases pass: destructive SQL denied, mutating SQL escalated to a human, reads allowed, `kubectl delete` in prod held for approval, unlisted hosts and commands default-denied. Credential sealing holds: the real `ghp_` token appears only in the bytes the gateway forwards, never in the agent's buffer, and on a denied action it is never injected at all.

## Why it was worth doing

The evasion probe found the real lesson: blocked is not the same as understood. A shallow verb-sniffer waved through `SELECT 1; DROP TABLE students;`. It saw `SELECT`, matched the read allow-rule, and forwarded a destructive statement. Three of its other "blocks" were luck, not comprehension: it parsed `/* c */ DROP` as verb `/*`, matched no allow-rule, and got saved by default-deny. A hardened extractor that strips comments and scores every statement catches all five payloads, but it is just a re-implementation of Postgres lexing. Anything it gets wrong versus the real server (dollar-quoting, encodings, dialect quirks) is an open door. This is parser-differential territory, and it is the whole game for any wire-level firewall.

Three takeaways for anyone deploying one:

1. **Default-deny is the hero, not the rule engine.** It turns every parser gap into a safe-fail. Keep allow-rules narrow; never trust a parser to positively certify "safe".
2. **Reject multi-statement payloads outright.** One wire message, one statement.
3. **Credential-on-the-gateway is the highest-leverage, lowest-fragility idea.** It needs no parser to be correct and removes a whole class of leak.

## What's still off

Our repro is the security logic, not the plumbing: we skipped TLS termination, WireGuard tunnelling and real TCP proxying, which is where Claw Patrol does its hard engineering. And the headline caveat is theirs as much as ours: wire gating is defence-in-depth with a ceiling set by parser fidelity, not by how clever your rules are. Treat it as one layer behind least-privilege credentials and human approval on mutations, never as the only thing between an agent and prod.
