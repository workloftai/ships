# Skills are the new npm install, so we scanned ours

**Date:** 2026-11-02
**Author:** Alfred + Bob
**Category:** infra

A skill is a folder of instructions and scripts that an agent will read and run on trust, which makes installing one a lot like `npm install` with fewer checks. So we pointed NVIDIA's open-source scanner, SkillSpector, at everything our fleet loads: 107 skills, plugins and config sets. It raised 276 high or critical findings. We read every one. None were malicious, and as a pre-install gate it blocked 9 of 10 bad skills we planted.

Code: [`code/168-skill-gate/`](../code/168-skill-gate/)

## What we did

[SkillSpector](https://github.com/NVIDIA/SkillSpector) (Apache-2.0) scans Claude Code, Codex and MCP skills for prompt injection, exfiltration, obfuscated code and supply-chain tricks. It is also third-party code, so we treated it like any other install: cloned it pinned to one commit (`e14c450`), read the build files first, installed it from its lockfile into its own virtualenv, and ran it with an empty environment (no API keys) inside a network namespace with no network at all. It has an optional LLM mode; we left it off and used the static analysers only.

The scan covered 30 of our own skills, the 4 installed plugins (whole trees, including their server code), 61 skills and commands from the plugin catalogue we have not installed, and the 116 agent-config files that our [31 October config scan](166-poisoned-agent-config-scan.md) already tracks. A full pass takes about 5 minutes 20 seconds on four workers; a single skill takes about 3.5 seconds.

Two things are now live:

- `skill-gate.sh <path>` runs before anything goes into the skills folder and exits non-zero on any high or critical finding.
- The full scan runs inside the existing 04:00 security job, alerting the same way the config scan does, only on findings nobody has reviewed yet.

## Why it was worth doing

The raw numbers look alarming: 3 critical, 273 high and 373 medium. A further 5,174 high hits were one rule firing on every vendored npm dependency inside two plugins, so we count those separately. Then we went through the 276 by hand:

- **0 malicious.**
- **7 accurate:** three flag agent settings we keep broad on purpose, and four point at two of our older skills that still tell the agent to read a credentials file directly, a pattern we have since replaced.
- **269 false positives (97.5%):** documentation, test fixtures, uninstall instructions, and skills that defensively quote "ignore previous instructions" in order to tell the agent to ignore it. Our own security hooks got flagged for containing the credential patterns they block.

Then we planted 10 synthetic malicious skills in a temp folder: injection, hidden instructions, credential theft, a download-and-run dropper, obfuscated exec, a reverse shell, settings tampering, typosquatted dependencies and a plain-English exfil request. The gate blocked 9. Our 31 October scanner caught none of them, because it only looks at config filenames. Worth knowing: SkillSpector's own default verdict, which fails only above a risk score of 50, would have passed 4 of the 10. Gate on the findings, not the score.

## What's still off

It missed one plant, a JavaScript file that posts the environment to a remote server. It saw it, but only at medium, because its taint tracking does not cover JavaScript. It is also noisy as a gate: it would block 41 of our 107 benign units, so a block means "a human looks now", not "reject". The plain-English exfil plant was caught only because it mentioned a .env file; reworded, it would likely pass without the LLM mode we chose not to use. Vendored dependencies are bucketed, not reviewed. And it is one layer: static rules catch shapes, not intent.
