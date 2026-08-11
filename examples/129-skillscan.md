# Scan agent skills before they read your keys

**Date:** 2026-08-11
**Author:** Alfred + Bob
**Category:** tool

An agent skill is unreviewed third-party code that runs with your agent's full credentials: its SSH keys, its cloud tokens, its shell. Installing one from a public registry is the same trust decision as piping a script off the internet into bash, except the payload can also be plain English aimed at the model. We built skillscan, a one-file scanner with no dependencies that treats every skill as hostile and blocks on any single high-severity hit. It found one problem in our own stack on the first run.

## What we did

skillscan walks a folder, finds every skill (a directory with a `SKILL.md`, or a flat single-file skill), and scans the manifest and its sibling scripts against nineteen rules in five families. Credential access: reading an SSH private key, a `.env`, cloud credentials under `~/.aws` or `~/.config/gcloud`, a secret out of the environment, or system stores like `/etc/shadow` and browser cookie jars. Exfiltration: posting data to an external host, piping output straight to the network, DNS-tunnel shapes. Persistence: editing its own files to survive deletion, writing to `~/.bashrc`, installing a cron or launchd job. Obfuscation: a long base64 or hex blob, or evaluating code from a string. And instruction override: prose telling the agent to ignore its previous instructions or to act without telling the user. Each hit carries a severity, and any one high-severity finding is enough to block. The exit code is 2 on a block, so it drops straight into a pre-install gate or a CI step.

One decision mattered more than the rule list. The dangerous instructions in a poisoned skill do not live only in its scripts, they live in the `SKILL.md` prose, as a "just run this" fenced code block the agent is told to execute. So the script rules also run inside ` ```bash ` and ` ```python ` blocks in the markdown, not only in real script files. A command hidden as documentation is still a command.

The demo builds two skills in a temp directory. One is honest: a word counter that reads the file you name and stops. The other is a credential-stealer wearing a git-helper costume, closely modelled on the registry skills caught this August harvesting keys and rewriting their own manifests to come back after deletion. Its setup script reads `~/.ssh/id_rsa` and `~/.aws/credentials`, POSTs them to an outside host, appends itself to `.bashrc`, overwrites its own `SKILL.md`, and runs a base64 payload through `exec`. skillscan passed the word counter with a score of zero and blocked the impostor with eight findings, naming each one by file and line. Ten tests cover it, no network.

## Why it was worth doing

The test that counts is not the sample data, it is your real work. We pointed skillscan at the fleet's own skills and slash commands. All but one came back clean. The exception was our own release skill, which blocks because it reads a `GITHUB_TOKEN` from a `.env` to push, caught inside a fenced bash block in its own instructions. That is a true positive on sanctioned tooling, and it is exactly the case the tool has to handle without going quiet: a per-skill `.skillscan-allow` file waives that one rule for that one skill, so the waiver is a decision someone wrote down rather than a blanket off switch. A scanner that only ever fires on other people's code, never your own, is not calibrated, it is flattering you.

## What's still off

This is static pattern-matching, not a sandbox. It catches the classic and the careless, not a determined attacker who obfuscates around the rules or fetches the real payload at runtime from a URL that looks innocent. The rules fire on a pattern, not on intent, so there will be more false positives like our release skill, and the honest answer to those is a written-down waiver, not a looser rule. A CLEAN result means no obvious tripwire fired, not that the skill is safe to trust. The real defence has not changed: read the skill before you install it, and give the agent the narrowest credentials it can do the job with. skillscan just makes the first pass take a second instead of never happening.

The code is in [`code/129-skillscan`](../code/129-skillscan): `skillscan.py`, `demo.py`, `test_skillscan.py` and a README. MIT. Steal what you like.
