# artifact-chain

A ~130-line, zero-dependency checker that makes the AI-native SDLC artifact chain tamper-evident.

## The gap it fills

Anthropic's [AI-Native SDLC Playbook](https://claude.com/blog/the-ai-native-sdlc-playbook) rebuilds the software lifecycle around a chain of committed artifacts:

```
intent.md  ->  spec.md  ->  plan.md  ->  diff + tests  ->  PR + review
```

The playbook's own line: *"Together, the intent, the spec, the plan, the diff and the review findings are the audit trail."*

The catch is that nothing in the playbook checks the chain is intact. The artifacts are just files in git. Nothing stops someone editing `intent.md` after the spec was signed off, or reshaping `spec.md` after the engineer accepted the plan. The audit trail then quietly lies about what was actually approved. Hooks are deterministic, skills are advisory, and here there was neither.

## What this does

Each downstream artifact records, in its front matter, the SHA-256 of its parent's body **as it stood when the artifact was signed off**:

```yaml
---
stage: spec
parent: intent.md
parent_sha256: 8f3a...c1
---
```

`chain_check.py` recomputes those hashes and fails loudly if any link no longer matches. Sealing (stamping the hashes) is the sign-off action a human runs. Editing an approved upstream artifact afterwards makes the chain visibly snap.

## Use it

```bash
# 1. Start the chain from the templates
mkdir intent && cp templates/*.md intent/

# 2. Write intent.md, then spec.md, then plan.md as you go.

# 3. Sign off: stamp each artifact with its parent's current hash
python3 chain_check.py --dir intent --seal

# 4. Verify (put this in CI and in a pre-commit hook)
python3 chain_check.py --dir intent
```

Intact:

```
[ok  ] intent.md
[ok  ] spec.md  (parent: intent.md)
[ok  ] plan.md  (parent: spec.md)

chain intact
```

Someone edits the signed-off intent, then tries to commit:

```
[ok  ] intent.md
[SNAP] spec.md  (parent: intent.md)  <- parent 'intent.md' changed since sign-off (sealed 8f3a...c1, now 2b90...7e)
[ok  ] plan.md  (parent: spec.md)

CHAIN BROKEN: an approved artifact changed after sign-off
```

Exit code is non-zero, so CI and the pre-commit hook block it. Review the change, then `--seal` again to re-sign. That reseal is the human-in-the-loop gate the playbook asks for, made enforceable.

## Wiring it as a blocking hook

`.claude/settings.json` in this folder shows a Claude Code `PreToolUse` hook that runs the check before any `git commit`/`git push` and blocks on a broken chain. Any CI runner does the same job with `python3 chain_check.py --dir intent`.

## Notes

- The hash covers the **body** only, so editing front matter (adding a reviewer, resealing) never counts as tampering. Trailing newlines are normalised.
- The chain order is `intent.md -> spec.md -> plan.md` by default. Put a `.chain` file (one filename per line) in the artifact dir to change it.
- A later stage that does not exist yet is reported `--`, not a failure: the chain can be mid-flight.

## Tests

```bash
python3 test_chain_check.py
```

Six cases: unsealed is broken, sealed is intact, a tampered upstream snaps, a missing parent fails, re-sealing after a reviewed change restores the chain, and front-matter/newline edits are ignored.

## What's still off

This proves an artifact was not changed after sign-off. It does not prove *who* signed off or that the reviewer was human. For that, seal inside a commit signed by the reviewer, and the git history plus these hashes together give you the full trail. This is the deterministic half; the identity half is your VCS's job.

MIT. Steal what you want.
