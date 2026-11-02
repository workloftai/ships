# skill-gate: a pre-install gate for agent skills

Companion code for [Skills are the new npm install, so we scanned ours](https://workloft.ai/ships/skill-supply-chain-scan-2026-11-02.html).

Wraps [NVIDIA SkillSpector](https://github.com/NVIDIA/SkillSpector) (Apache-2.0) so it runs
static only, with no secrets and no network, then gates on its findings.

| File | What it does |
|------|--------------|
| `skillspector-run.sh` | Runs SkillSpector with `env -i` (empty environment), inside `unshare -rn` (no network namespace), always `--no-llm`. OSV lookups fall back to SkillSpector's built-in offline list. |
| `skill-gate.sh <path>` | Pre-install gate. Exit 0 pass, 1 block on any HIGH/CRITICAL finding, 2 on scanner error (fails closed). SC9 hits inside vendored `node_modules` or lockfiles are listed but do not block on their own. |
| `skill_gate_verdict.py` | The verdict logic for the gate, reading SkillSpector JSON on stdin. |
| `skill-scan-all.py` | Full fleet scan: user skills, installed plugins, the uninstalled plugin catalogue, and agent-config files grouped per repo. Exits 1 only on HIGH/CRITICAL findings not yet in a reviewed-verdicts file, so a daily cron alerts on new findings only. |

## Install SkillSpector the careful way

```bash
git clone https://github.com/NVIDIA/SkillSpector skillspector-src
cd skillspector-src && git checkout e14c450b260958ed3ebd83c94c09c4b093e3e656
# read pyproject.toml, Makefile and package.json first
env -i PATH=/usr/bin:/bin:$HOME/.local/bin HOME=$HOME \
  UV_PROJECT_ENVIRONMENT=$HOME/security/skillspector-venv \
  uv sync --frozen --no-dev --python python3.12
```

Paths in the scripts are ours (`/home/workloft/...`); change them to suit.

## Gate on findings, not the score

SkillSpector's own exit code fails only when its risk score is above 50. In our test of 10
planted malicious skills that default would have passed 4. Gating on any HIGH/CRITICAL
finding blocked 9 of 10. The cost: it also blocks 41 of our 107 benign units, so treat a
block as "a human looks now", not "reject".
