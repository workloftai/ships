# skillscan

A supply-chain scanner for agent skills. One file, no dependencies, Python 3.8+.

An agent skill (a `SKILL.md` plus whatever scripts sit beside it) is unreviewed
third-party code that runs with your agent's full credentials: its SSH keys, its
cloud tokens, its shell. Installing one from a public registry is the same trust
decision as `curl | bash`, except the payload can also be plain-English
instructions aimed at your model.

skillscan treats every skill as hostile until proven otherwise. It walks a
folder, finds each skill, and scans the `SKILL.md` and its sibling scripts for
the patterns a credential-stealer actually uses.

## Use

```bash
python3 skillscan.py scan ~/.claude/skills          # scan a folder of skills
python3 skillscan.py scan ./some-skill --min review # only print REVIEW+ skills
python3 skillscan.py scan ./some-skill --json        # machine-readable
```

Exit code is `2` if any skill scores **BLOCK**, so it drops into a pre-install
gate or a CI step:

```bash
python3 skillscan.py scan ./downloaded-skill || { echo "refusing to install"; exit 1; }
```

## What it looks for

Each hit carries a severity. Any single **HIGH** finding blocks the skill.

- **Credential access** — reads an SSH private key, a `.env`, cloud credentials
  (`~/.aws`, `~/.config/gcloud`), a secret from the environment, or system stores
  (`/etc/shadow`, browser cookie jars).
- **Exfiltration** — posts data to an external host, pipes output straight to
  the network, or looks like DNS-tunnel exfil.
- **Self-modification / persistence** — edits its own skill files, claims to
  "survive deletion", writes to a shell startup file, or installs a
  cron / systemd / launchd job.
- **Obfuscation** — a large base64 or hex blob, or evaluating code from a string
  (`eval`, `exec`, `atob`, `base64.b64decode(...)` into `exec`).
- **Destructive** — `rm -rf /`, `mkfs`, `dd`, a force-push, `chmod 777`.
- **Instruction override** — prose that tells the agent to ignore its previous
  instructions, or to do something without telling the user.

Prose in a `SKILL.md` is scanned for the payloads that live in prose (the
instruction-override and self-modification patterns). Script rules (the ones
about running commands) fire in real script files **and** inside fenced
` ```bash ` / ` ```python ` code blocks in a `SKILL.md`, because that is where a
malicious skill hides its "just run this" payload.

## False positives and the allowlist

The scanner is deliberately blunt: a rule fires on a pattern, not on intent. Some
of your own tooling will legitimately do things on this list (our release skill
reads a `GITHUB_TOKEN` from a `.env` to push, which is a real credential read).

Drop a `.skillscan-allow` file in the skill's own directory, one rule id per line,
to waive a rule for that skill only:

```
# .skillscan-allow
cred.dotenv   # sanctioned: this skill reads our own GITHUB_TOKEN to push
```

Waive per-skill, never globally. The point is that each waiver is a decision
someone wrote down, not a blanket off switch.

## Try it

```bash
python3 demo.py            # builds a poisoned skill in a temp dir and flags it
python3 test_skillscan.py  # 10 tests, no network
```

## What it is not

Static pattern-matching, not a sandbox. It catches the classic and the careless,
not a determined attacker who obfuscates around the rules or fetches the payload
at runtime. Treat a CLEAN result as "no obvious tripwire", not "safe to trust".
The real defence is still: read the skill before you install it, and give your
agent the narrowest credentials it can do its job with.

MIT. Steal what you like.
