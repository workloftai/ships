#!/usr/bin/env bash
# measure.sh — how much does an AST code graph cut the token bill for one
# real "what breaks if I change this?" question, versus grep + read?
#
# It indexes a target repo with code-graph-mcp, picks the highest fan-in
# symbol (the worst case for grep), then compares two ways of answering
# "what is the blast radius of changing this symbol":
#
#   A. code-graph:  one `impact <symbol>` call
#   B. baseline:    grep for the symbol, then read the files that contain
#                   callers (what a coding agent does today)
#
# Tokens are estimated as chars / 4 (the usual rule of thumb), applied the
# same way to both sides so the ratio is fair. This is one representative
# question on one repo, not a benchmark suite. Run it on your own code.
#
# Usage:  ./measure.sh /path/to/repo
# Needs:  a `code-graph-mcp` binary on PATH (or set CODE_GRAPH_BIN), ripgrep
#         optional, plain grep is fine.
set -euo pipefail

REPO="${1:?usage: ./measure.sh /path/to/repo}"
BIN="${CODE_GRAPH_BIN:-code-graph-mcp}"
export CODE_GRAPH_NO_AUTO_UPDATE=1 CODE_GRAPH_DISABLE_MODEL_DOWNLOAD=1

# Work on a copy so we never write an index into the target repo.
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
find "$REPO" -name '*.py' -not -path '*/__pycache__/*' -exec cp {} "$WORK"/ \; 2>/dev/null || true
n_files=$(find "$WORK" -name '*.py' | wc -l)
[ "$n_files" -gt 0 ] || { echo "no .py files under $REPO"; exit 1; }

cd "$WORK"
echo "indexing $n_files files from $REPO ..."
"$BIN" rebuild-index --confirm >/dev/null 2>&1

# Pick the highest fan-in function (worst case for grep+read).
SYM=$("$BIN" map 2>/dev/null | awk '/Hot Functions:/{f=1;next} f&&/caller/{gsub(/[^a-zA-Z0-9_].*/,"",$1);print $1;exit}')
[ -n "${SYM:-}" ] || { echo "could not find a hot symbol"; exit 1; }
echo "target symbol (highest fan-in): $SYM"
echo

# ---- A. code-graph path: one impact call ----
"$BIN" impact "$SYM" > cg.txt 2>/dev/null
cg_chars=$(wc -c < cg.txt)
cg_tok=$((cg_chars/4))

# ---- B. baseline: grep, then read every file that contains a caller ----
grep -rn "$SYM" . --include='*.py' > grep.txt || true
grep_chars=$(wc -c < grep.txt)
read_chars=0
for f in $(grep -rl "$SYM" . --include='*.py' | sort -u); do
  read_chars=$((read_chars + $(wc -c < "$f")))
done
base_chars=$((grep_chars + read_chars))
base_tok=$((base_chars/4))
base_calls=$(( 1 + $(grep -rl "$SYM" . --include='*.py' | sort -u | wc -l) ))

# ---- report ----
printf '%-34s %10s %12s %12s\n' "path" "tokens" "tool_calls" "complete?"
printf '%-34s %10s %12s %12s\n' "code-graph  impact $SYM" "$cg_tok" "1" "yes"
printf '%-34s %10s %12s %12s\n' "grep + read caller files" "$base_tok" "$base_calls" "partial*"
echo
awk -v b="$base_tok" -v c="$cg_tok" 'BEGIN{printf "token ratio: %.1fx fewer with code-graph (%d vs %d)\n", b/c, b, c}'
echo "* partial: whole-file reads still miss the transitive closure, risk level and"
echo "  tests-affected that impact returns in one shot; grep cannot give those at all."
