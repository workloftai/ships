# code-graph token delta

How much does an AST code graph cut the token bill for one real question a
coding agent asks all the time: **"what breaks if I change this?"**

We put [`code-graph-mcp`](https://github.com/sdsrss/code-graph-mcp) (an
MCP server that parses a repo into a graph of symbols, calls and imports)
in front of a question and measured it against the default an agent reaches
for today: grep, then read the files that matched.

## The question

Pick the highest fan-in symbol in the repo (the worst case for grep), and ask
for its blast radius: every function that would break if the signature changed.

On our own Loop agent (`gary`, 16 Python files) the answer is `_req`, the
Supabase REST wrapper. 30 functions call it.

## The result

Same question, two ways. Tokens estimated as chars / 4, applied identically to
both sides so the ratio is fair.

| path | tokens | tool calls | answers the question? |
|---|--:|--:|---|
| `code-graph impact _req` | **627** | **1** | yes: 30 direct, 63 transitive callers, 11 files, 0 tests, risk HIGH |
| grep + read the caller files | 22,601 | 8 | partial: still misses the transitive closure, risk and tests |
| grep with 5 lines of context | ~5,038 | 2 | no: gives call sites, not the blast radius |

**About 36x fewer tokens, 8 tool calls down to 1**, and the cheap path is the
only one that actually answers the question. Even reading every caller file in
full (the expensive column) does not give the transitive closure, the risk
level or the tests affected without re-grepping each caller by hand.

It is also more accurate than grep: 37 raw `_req(` call-site lines collapse to
30 distinct caller functions. The graph counts callers; grep counts lines.

## Reproduce it

```bash
# 1. get the code-graph-mcp binary (prebuilt, no toolchain needed)
curl -sL -o code-graph-mcp \
  https://github.com/sdsrss/code-graph-mcp/releases/latest/download/code-graph-mcp-linux-x64
chmod +x code-graph-mcp

# 2. run the measurement against any Python repo
CODE_GRAPH_BIN=./code-graph-mcp ./measure.sh /path/to/your/repo
```

`measure.sh` copies the target's `.py` files to a temp dir (so it never writes
an index into your repo), indexes them, picks the highest fan-in symbol, and
prints the table above for your code.

## Honest limits

- **One question, one repo.** This is a representative worst-case lookup, not a
  benchmark suite. The absolute saving grows with repo size, and so does the
  cost of keeping the index fresh (here: 16 files, 165 nodes, indexed in 0.17s).
- **Structural only.** We ran the graph in FTS5 mode with the embedding model
  disabled, so vector semantic search is untested. The structural tools
  (`impact`, `callgraph`, `refs`, `map`) are the part that earned the win.
- **chars/4 is an estimate.** It is applied the same way to both paths, so the
  ratio holds even if the absolute token counts are approximate.
- The saving is real because grep hands the model text and code-graph hands it
  structure. On a small repo the win is already 8x to 36x; the gap widens as the
  codebase does.

Files here: `measure.sh` (the harness), `impact-_req.txt` (the actual one-call
answer on `gary`).
