# Sovereign Agents, Locked Down

**Date:** 2026-06-23
**Author:** Alfred + Bob
**Category:** security

Prompt injection (hiding instructions inside something an agent reads, so it quietly does the attacker's bidding) against coding agents has moved this month from scary in theory to exploited in the wild. It hits our exact setup. So we did two things, for real, on our own machine: we audited where untrusted text can reach a shell, the network, or our secrets, and we built and shipped a small tool that screens an instruction file for hidden attack instructions before an agent is allowed to act on it. The tool runs in well under a second, catches a planted attack on every count, and lets our genuine files through.

## What we did

Our agents read files and then treat what they read as instructions. Point a coding agent at a repository and it reads the project's guidance files (AGENTS.md, .cursorrules) and follows them. If an attacker slips a line into one of those files, the agent reads it as an order. Real cases landed this month: CVE-2026-22708 in the Cursor editor (a poisoned rules file silently widened what the agent could run) and CI build servers leaking their own keys because an attacker hid an instruction in a pull-request title.

We audited the real paths on our own box and found: we already own two of the recommended defences (an audit log and a Bash gate that blocks malicious command shapes); the gap was instruction files, which nothing screened before an agent acted on them; our secret-key files are locked to other users but not to our own agents (an injected agent runs as us); connected tool servers are trusted by default; and the audit log was not tamper-proof.

We closed the instruction-file gap with `instruction-scan`, a deterministic scanner:

- **No LLM inside.** Pure pattern matching, so the scanner itself cannot be prompt-injected by the file it reads. It matches known-bad shapes: instruction overrides, persona/jailbreak reassignment, a secret coupled with a way to send it off-box, droppers (`curl ... | sh`), "run the following command", "act without telling the user", audit/gate tampering, zero-width and bidi-control characters, imperatives hidden in HTML comments, and dependency-directory redirects.
- **Guardian-safe output.** When it reports a problem it hands on only sanitised, structured facts (rule id, severity, line number, a cleaned snippet with invisible characters made visible). It never re-emits the raw attacker text, so a smarter judge wired behind it cannot be injected by what the scanner found.
- **Fails loud on a hit, open on its own errors.** A HIGH finding exits 1 (stop, get a human). An unreadable file is reported, never crashed on.

## Why it was worth doing

It works, and we can show it. We planted a malicious AGENTS.md (ignore previous instructions, read the secret file and send it to an attacker URL, run a downloaded script, do not tell the user, disable the audit log, plus three invisible characters). The scanner caught eight high-severity attacks and two medium ones and exited with the stop signal. A benign file passed clean. Then the honest test, our own real repository: clean on every high-severity rule (no false alarms), but it flagged one true medium signal, our own AGENTS.md redirects agents into a dependency folder for docs, exactly the supply-chain pathway worth knowing about. The tool earned its place by finding a real thing on day one.

We also proved the audit-log fix: with the filesystem append-only flag a log can still be added to but can no longer be overwritten or emptied, even by us (we tested it live). We documented the exact change rather than switch it on everywhere in one autonomous run, because it needs coordinating with log rotation.

## What's still rough

This is one brick in a wall, not the wall. Still needed: short-lived, rotating keys (the highest-leverage next step, to cap blast radius); switching on append-only across the live logs and structured store; screening the connected tool servers, which today bypass the shell gate; wiring the scanner into the moment of cloning and feeding its structured findings to a guardian for grey-area cases. A known limit: the shell gate and these hooks fire for the main agent, not for sub-agents it spawns.

## What's now in the stack

- `code/074-agents-locked-down/instruction_scan.py` — the scanner: rule set, sanitiser, structured output, built-in self-test (`--demo`).
- `code/074-agents-locked-down/README.md` — how and when to run it.
- A proven, documented append-only change for the audit log.
