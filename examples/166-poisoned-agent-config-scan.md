# A daily scan for poisoned agent-config files

**Date:** 2026-10-31
**Author:** Alfred + Bob
**Category:** infra

Bob runs headless, on a schedule, with real credentials. If a repo he pulls carries a planted AGENTS.md or a malicious hook, that is a direct path to our keys. Three separate campaigns landed that exact shape in the week of 27 October, so we built the defence: a read-only scan, bolted onto the daily security run, that flags new or changed instruction files carrying injection or exfil markers. It caught 10 of 10 synthetic plants at a 2.6% false-positive rate.

## What we did

Coding agents read instruction files automatically: AGENTS.md, CLAUDE.md, the hooks in .claude/settings.json, .vscode/tasks.json, .cursor rules. That is the whole point, and it is also the attack surface. A line of text in one of those files is an instruction the agent will follow before a human sees it.

The scanner walks every repo under the fleet home (43 git roots on the first run), computes a SHA-256 of each instruction and hook file, and keeps a hash baseline of our own known-good tree. On each run it only inspects files that are new or whose hash has changed. Those get run through a set of indicator-of-compromise checks:

- oversized decoy files (the JFrog campaign used ~13MB padding)
- long base64 or base32 blobs
- download-to-shell droppers (curl or wget piped into bash, base64 -d into sh)
- a /dev/tcp reverse shell
- credential bait sitting next to a network verb
- prompt-injection or role-spoof markers such as "ignore all previous instructions" or a fake `<system>` block

It also ships as a pre-clone and pre-pull gate: `agent-config-scan.py --scan-dir <path>` returns a non-zero exit code if a freshly cloned or pulled tree trips any check, so we can refuse to trust a repo before an agent ever reads it. A hit on the daily run raises a Telegram alert for review; a human blesses the change with `--approve`.

## Why it was worth doing

This is not theoretical. In the week of 27 October: JFrog reported 42 repositories seeded with malicious AGENTS.md prompt injections; a paper (arXiv 2610.40396) documented role-spoofing injection through CLAUDE.md and AGENTS.md; and GhostAction showed the same idea through .vscode/tasks.json and CI tasks. All three target coding agents specifically, and the payoff for the attacker is the credential an agent like Bob holds.

We measured it before adopting. Against the live tree the scan inventoried 116 instruction and hook files across 43 repos. We then wrote 10 synthetic plants covering all three campaigns (injection, exfil hook, base64 dropper, /dev/tcp shell, GhostAction task, oversized decoy). The scan caught all 10. Run cold over our real files, it flagged just 3 of 116, a 2.6% false-positive rate, under our 5% ceiling. Those 3 are our own security hooks that legitimately mention curl and env; the hash baseline suppresses them in normal running, so the day-to-day noise is zero.

## What's still off

The checks are heuristic, not a sandbox. A payload written to dodge every pattern (no base64, no obvious verb, pure natural-language injection) could slip the net, so this is one layer, not the whole wall. The baseline is trust-on-first-sight: it blesses the current tree as good, so a file already poisoned at install time would be baselined. And the gate flags; it does not quarantine. We would rather over-alert on a key-exfil path than auto-delete an agent's instructions.
