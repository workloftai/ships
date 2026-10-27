#!/bin/sh
# litellm-ioc-scan.sh — one-command detector for the litellm 1.107.0 supply-chain
# compromise (PyPI + Docker, 21 Oct 2026). Read-only. Exit 0 = clean, 1 = suspect.
#
# What it looks for, per the published IoCs:
#   - the malicious artefacts cook.pth / cook.py / a rogue sitecustomize.py
#     dropped into a site-packages ROOT (not a package subdir)
#   - the attacker's /tmp lock + once-marker files
#   - any installed litellm pinned to the compromised 1.107.0
#   - requirements/lockfiles that pin 1.107.0
# Run it on every host that has ever `pip install`-ed or Docker-pulled litellm.
#
# Workloft Labs. British spelling. No network calls — it only reads the disk.

status=0
say() { printf '%s\n' "$*"; }
hit() { printf 'SUSPECT: %s\n' "$*"; status=1; }

say "[litellm-ioc-scan] host=$(hostname 2>/dev/null) $(date -u 2>/dev/null)"

# 1. The dropped artefacts, only where they are malicious: a site-packages ROOT.
#    A sitecustomize.py *inside* a package (opentelemetry, debugpy) is legitimate;
#    one sitting directly in site-packages alongside cook.pth is the payload.
for sp in $(find / -maxdepth 9 -type d -name site-packages 2>/dev/null); do
  for f in cook.pth cook.py sitecustomize.py; do
    [ -e "$sp/$f" ] && hit "$sp/$f"
  done
done
# cook.pth / cook.py anywhere at all is never legitimate.
for f in $(find / -name cook.pth -o -name cook.py 2>/dev/null); do hit "$f"; done

# 2. Attacker tmp markers (names from the published analysis).
for f in /tmp/.pc_once_72129118c59f5636c0bb /tmp/remote_code_loader.lock; do
  [ -e "$f" ] && hit "$f"
done

# 3. The compromised version actually installed.
for di in $(find / -type d -name 'litellm-*.dist-info' 2>/dev/null); do
  case "$di" in *litellm-1.107.0.dist-info) hit "installed $di";; *) say "info: installed $(basename "$di")";; esac
done

# 4. 1.107.0 pinned in a dependency file.
grep -rIlE 'litellm[[:space:]]*[=<>~!]*[[:space:]]*1\.107\.0' / \
  --include='requirements*.txt' --include='*.lock' --include='Pipfile*' \
  --include='pyproject.toml' --include='poetry.lock' 2>/dev/null \
  | while read -r p; do printf 'SUSPECT: pins 1.107.0 -> %s\n' "$p"; done
grep -rIlqE 'litellm[[:space:]]*[=<>~!]*[[:space:]]*1\.107\.0' / \
  --include='requirements*.txt' --include='*.lock' --include='Pipfile*' \
  --include='pyproject.toml' --include='poetry.lock' 2>/dev/null && status=1

if [ "$status" -eq 0 ]; then
  say "[litellm-ioc-scan] CLEAN — no IoCs, no 1.107.0."
else
  say "[litellm-ioc-scan] SUSPECT — act now: kill the host's outbound, rotate EVERY"
  say "  credential reachable from it (SSH keys, cloud, CI, provider API keys,"
  say "  browser creds), remove the artefacts, and reinstall litellm from a known"
  say "  good version. A .pth payload runs on ANY python start, not just litellm."
fi
exit "$status"
