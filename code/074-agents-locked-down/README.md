# instruction-scan

A deterministic scanner that screens agent-instruction files (AGENTS.md,
CLAUDE.md, .cursorrules, .clinerules, .windsurfrules, copilot-instructions.md and
friends) for prompt-injection **before** a coding agent reads and acts on them.

The Bash/command layer catches a malicious *command*. This catches the
*instruction* that would talk an agent into running it, one step earlier, at the
supply-chain / runtime-injection boundary (a cloned repo, a dependency that ships
its own rules file).

## Run it

```
python3 instruction_scan.py <path> [<path> ...]   # scan dirs and/or files
python3 instruction_scan.py --json <path>         # structured (guardian-safe) output
python3 instruction_scan.py --demo                # self-test: planted attack vs benign
```

Exit codes: `0` clean / only-medium · `1` HIGH finding (stop, get a human) · `2` usage error.
Standard library only. No install, no network, no model calls.

## Why it is built this way

- **No LLM inside.** Pure pattern matching, so the scanner cannot itself be
  prompt-injected by the file it reads.
- **Guardian-safe output.** It emits only sanitised structured facts (rule id,
  severity, line, cleaned snippet with invisible characters made visible), never
  the raw attacker text, so a smarter judge wired behind it stays uninjectable.
- **Fails loud on a hit, open on its own errors.** A HIGH finding blocks; an
  unreadable file is reported, not crashed on.

## What it flags

HIGH: instruction override, persona/jailbreak reassignment, credential+exfil
coupling, droppers (`curl ... | sh`), "run the following command", "act without
telling the user", audit/gate tampering, zero-width and bidi-control characters.

MEDIUM: dependency-directory redirects, imperatives hidden in HTML comments,
external URL fetches, long base64 blobs.

MIT. Steal what you want.
