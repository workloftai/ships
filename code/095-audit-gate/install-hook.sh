#!/usr/bin/env bash
# Install audit-gate as a pre-push hook on a repo.
# Usage: ./install-hook.sh /path/to/repo [--no-llm]
# Trial scope: fleet/internal repos only. Do not install on client repos.
set -euo pipefail

REPO="${1:?usage: install-hook.sh /path/to/repo [--no-llm]}"
MODE="${2:-}"
GATE="$(cd "$(dirname "$0")" && pwd)/gate.py"
HOOK="$REPO/.git/hooks/pre-push"

[ -d "$REPO/.git" ] || { echo "not a git repo: $REPO" >&2; exit 1; }

cat > "$HOOK" <<EOF
#!/usr/bin/env bash
# audit-gate pre-push hook (installed $(date +%F))
exec python3 "$GATE" audit --repo "$REPO" --range @{u}..HEAD $MODE
EOF
chmod +x "$HOOK"
echo "audit-gate pre-push hook installed on $REPO ${MODE:+(mode: $MODE)}"
