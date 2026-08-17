#!/usr/bin/env bash
# wmerge — the WRITE-half of swarm-safe fan-out.
# Baseline = naive shared working tree (lost-update race).
# Isolated = one git worktree per writer + a conflict-resolving merge step.
set -euo pipefail
BASE="$(cd "$(dirname "$0")" && pwd)"
SRC="$BASE/demo-src"
count_ops() { python3 - "$1" <<'PY'
import sys, re
s=open(sys.argv[1]).read()
print(len(re.findall(r'"\w+": lambda', s)))
PY
}
verify() { # run tests in a dir, echo PASS/FAIL
  if (cd "$1" && python3 test_calc.py) >/dev/null 2>&1; then echo PASS; else echo FAIL; fi
}

# ---------- BASELINE: naive shared tree, agents race on one copy ----------
run_baseline() {
  local W="$BASE/run-naive"; rm -rf "$W"; cp -r "$SRC" "$W"
  # Each "agent" reads the ORIGINAL and writes the whole file back (classic lost update).
  local orig; orig="$(mktemp)"; cp "$W/calc.py" "$orig"
  while IFS='|' read -r op line; do
    cp "$orig" "$W/calc.py"                 # each agent starts from the same base it read
    python3 "$BASE/insert_op.py" "$W/calc.py" "$line"
  done < "$BASE/writers.txt"
  echo "$W|$(count_ops "$W/calc.py")|$(verify "$W")"
}

# ---------- ISOLATED: worktree per agent + merge step ----------
run_isolated() {
  local R="$BASE/repo"; rm -rf "$R"; mkdir -p "$R"; cp -r "$SRC/." "$R/"
  cd "$R"; git init -q; git config user.email b@w; git config user.name bob
  # Conflict-resolving merge step: union driver keeps BOTH sides' additive edits.
  echo 'calc.py merge=union' > .gitattributes
  git add -A; git commit -qm base; git branch -M main
  local i=0
  while IFS='|' read -r op line; do
    i=$((i+1)); local wt="$BASE/wt-$op"; rm -rf "$wt"
    git worktree add -q -b "w/$op" "$wt" main      # ISOLATION: own worktree + branch
    python3 "$BASE/insert_op.py" "$wt/calc.py" "$line"
    (cd "$wt" && git add -A && git commit -qm "add $op")
  done < "$BASE/writers.txt"
  # MERGE STEP: sequentially integrate each writer branch; union driver resolves the
  # overlapping hunks deterministically. This is the arbitration point — one place,
  # never two agents fighting over the same lines.
  while IFS='|' read -r op line; do
    git merge -q --no-edit "w/$op" || true
  done < "$BASE/writers.txt"
  git worktree prune
  echo "$R|$(count_ops "$R/calc.py")|$(verify "$R")"
}

case "${1:-both}" in
  baseline) run_baseline;;
  isolated) run_isolated;;
  both)     echo "MODE|dir|ops_landed|tests"; echo "naive|$(run_baseline)"; echo "isolated|$(run_isolated)";;
esac
