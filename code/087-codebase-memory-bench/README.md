# 087 · cbm-bench

An honest token benchmark for [codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp),
the code-intelligence MCP server that indexes a repo into a knowledge graph so a
coding agent can ask structural questions instead of reading files.

The project's headline is **"120x fewer tokens"** (its own arXiv preprint says
**10x**; a newsletter that flagged it to us said **99% fewer**). Three different
numbers for the same claim is a good reason to measure it yourself before you
wire it into your stack.

`cbm-bench` does that. It points the real binary at a real repo and counts the
tokens two ways:

- **graph mode** — ask the MCP tools, count the tokens of what they return
  (that is what actually lands in the agent's context window).
- **file mode** — the file-by-file baseline: the cheap `grep` to locate, plus
  reading the full content of the files that hold the answer (how a
  Read-the-file agent like Claude Code actually works).

Tokens are counted with `tiktoken` (`cl100k_base`). No estimation.

## The honest finding

The big ratio is real, but it is a headline, not an average. The win is
concentrated in **structural enumeration and impact queries**, and some queries
are net-negative because the tool's JSON is verbose.

Measured against the Conexus repo (34 source files, ~51k tokens read whole):

| Task | graph | file | result |
|---|---:|---:|---|
| List every server action | 21 | 6,241 | **297x** |
| Impact: what calls X? | 101 | 1,967 | **19.5x** |
| Find the status-update surface | 696 | 4,076 | **5.9x** |
| Orient in the codebase | 3,575 | 677 | 0.2x (loses) |
| Locate the Supabase client | 3,434 | 1,260 | 0.4x (loses) |
| **Total (5 tasks)** | **7,827** | **14,221** | **1.8x** |

So on a small repo with a grep-first baseline the average is **1.8x (45% fewer
tokens)**, not 120x. "Enumerate every X" and "what calls Y" win big. Broad
concept search and first-look orientation can cost *more* than just reading,
because the ranked-result JSON is heavier than the file.

The 85x / 99% numbers reappear only when you compare against reading the **whole
repo** every time, which no competent agent does. We report that row too,
clearly labelled, so you can see exactly where the marketing denominator comes
from.

### The baseline is deliberately mean to the tool

The file-mode baseline greps first and reads the minimum number of files. That
is the *hardest* baseline for a graph to beat, and we still see 1.8x. A real
agent orienting in an unknown repo reads far more than three files, so the
real-world win sits above 1.8x for that workload. We kept the baseline lean on
purpose, so nobody can say we juiced the tool's numbers.

## What it confirmed, no asterisk

- **Indexing is genuinely fast.** Conexus indexed in **185 ms** (756 nodes,
  1,029 edges, 109 functions, 68 files), peak ~40 MB RAM. The "milliseconds for
  an average repo" claim holds.
- **Single static binary, checksum verified.** No runtime, no API key, all
  local. The supply-chain surface is one signed download you can hash.

## Run it yourself

```bash
pip install tiktoken
# download the binary from the project's releases, then index your repo once:
codebase-memory-mcp cli index_repository '{"repo_path":"/path/to/repo"}'
python3 cbm_bench.py \
  --bin /path/to/codebase-memory-mcp \
  --repo /path/to/repo \
  --project <indexed-project-name>
```

The task set in `cbm_bench.py` is written for the Conexus repo. Swap the `TASKS`
list for questions and files that match your own codebase. The point is not our
five numbers; it is that you can get your own in two minutes.

## The takeaway for builders

Don't install a graph index because a badge says 120x. Install it for the
queries where a graph genuinely beats a file read: enumerate-everything,
who-calls-this, trace-this-path, on a repo too big to hold in context. For those
it is a real step-change. For "what does this one file do", just read the file.

MIT, like everything here. The tool itself is MIT and not ours.
