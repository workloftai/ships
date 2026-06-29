#!/usr/bin/env python3
"""
cbm-bench — an honest token benchmark for codebase-memory-mcp.

Compares, for a set of realistic "agent questions" about a real repo:

  graph mode    — ask codebase-memory-mcp's MCP tools, count the tokens of
                  what the tool returns (that is what lands in the agent's context).

  file mode     — the file-by-file baseline: the cheap grep to locate, plus
                  reading the full content of the files that actually hold the
                  answer (which is how a Read-the-file agent works).

It also reports the "read the whole repo" number, because that is the baseline
the headline marketing ratios are computed against, and it flatters the tool.

Tokens are counted with tiktoken (cl100k_base). No estimation.

Usage:
  python3 bench.py --bin /path/to/codebase-memory-mcp \
                   --repo /path/to/repo \
                   --project <indexed-project-name>
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import tiktoken

ENC = tiktoken.get_encoding("cl100k_base")


def toks(s: str) -> int:
    return len(ENC.encode(s))


def run_cbm(binary: str, tool: str, args: dict) -> str:
    """Run one cbm tool via its CLI and return raw stdout (the tool result)."""
    out = subprocess.run(
        [binary, "cli", tool, json.dumps(args)],
        capture_output=True, text=True,
    )
    # cbm logs to stderr; the JSON tool result is the last non-empty stdout line.
    lines = [l for l in out.stdout.splitlines() if l.strip()]
    return lines[-1] if lines else ""


def read_files(repo: Path, paths: list[str]) -> str:
    blob = []
    for p in paths:
        fp = repo / p
        if fp.exists():
            blob.append(f"// {p}\n" + fp.read_text(errors="ignore"))
    return "\n".join(blob)


def run_grep(repo: Path, term: str) -> str:
    out = subprocess.run(
        ["grep", "-rn", term, "src"],
        cwd=repo, capture_output=True, text=True,
    )
    return out.stdout


# Each task: a question an agent would actually ask, the graph calls that
# answer it, and the file-by-file work that answers the same question.
TASKS = [
    {
        "name": "Orient in the codebase",
        "q": "What is this project: languages, modules, routes, entry-point actions?",
        "graph": [("get_architecture", {"aspects": ["all"]})],
        "grep": None,
        "files": ["package.json", "next.config.ts", "src/app/layout.tsx"],
    },
    {
        "name": "Find the status-update surface",
        "q": "Where is a referral's status updated and what are the moving parts?",
        "graph": [("search_graph", {"query": "status"})],
        "grep": "status",
        "files": ["src/app/actions/update-status.ts",
                  "src/app/students/[id]/status-update.tsx"],
    },
    {
        "name": "Impact analysis before a change",
        "q": "What calls updateReferralStatus? (safe to change the signature?)",
        "graph": [("search_graph", {"query": "updateReferralStatus"}),
                  ("query_graph", {"query": "MATCH (a)-[:CALLS]->(b) WHERE b.name = 'updateReferralStatus' RETURN a"})],
        "grep": "updateReferralStatus",
        "files": ["src/app/actions/update-status.ts",
                  "src/app/students/[id]/status-update.tsx"],
    },
    {
        "name": "List every server action",
        "q": "List all server actions (entry points) and the files they live in.",
        "graph": [("get_architecture", {"aspects": ["entrypoints"]})],
        "grep": "use server",
        "files": ["src/app/admin/actions.ts",
                  "src/app/actions/upload-document.ts",
                  "src/app/actions/summarise-document.ts",
                  "src/app/referrals/new/actions.ts",
                  "src/app/actions/update-status.ts",
                  "src/app/auth/actions.ts"],
    },
    {
        "name": "Locate the Supabase client",
        "q": "Where is the Supabase client created and who uses it?",
        "graph": [("search_graph", {"query": "supabase client createClient"})],
        "grep": "createClient",
        "files": ["src/lib/supabase/server.ts",
                  "src/lib/supabase/client.ts",
                  "src/lib/supabase/admin.ts",
                  "src/lib/supabase/middleware.ts"],
    },
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--project", required=True)
    args = ap.parse_args()
    repo = Path(args.repo)

    rows = []
    g_total = f_total = 0
    for t in TASKS:
        g_tokens = 0
        for tool, a in t["graph"]:
            a = {**a, "project": args.project}
            g_tokens += toks(run_cbm(args.bin, tool, a))

        f_tokens = 0
        if t["grep"]:
            f_tokens += toks(run_grep(repo, t["grep"]))
        f_tokens += toks(read_files(repo, t["files"]))

        g_total += g_tokens
        f_total += f_tokens
        rows.append((t["name"], g_tokens, f_tokens, f_tokens / g_tokens if g_tokens else 0))

    # whole-repo baseline (the marketing denominator)
    all_src = []
    for ext in ("*.ts", "*.tsx", "*.sql", "*.css", "*.js"):
        for fp in repo.glob(f"src/**/{ext}"):
            all_src.append(fp.read_text(errors="ignore"))
    whole = toks("\n".join(all_src))

    print(f"\n{'TASK':<34}{'graph':>9}{'file':>9}{'saving':>9}")
    print("-" * 61)
    for name, g, f, r in rows:
        print(f"{name:<34}{g:>9}{f:>9}{r:>8.1f}x")
    print("-" * 61)
    print(f"{'TOTAL (5 realistic tasks)':<34}{g_total:>9}{f_total:>9}{f_total/g_total:>8.1f}x")
    print()
    print(f"Realistic file-by-file baseline : {f_total:>8} tokens")
    print(f"Graph-query total               : {g_total:>8} tokens")
    print(f"Token reduction (realistic)     : {100*(1-g_total/f_total):>7.0f}%  ({f_total/g_total:.1f}x)")
    print()
    print(f"Whole-repo read (marketing base): {whole:>8} tokens")
    print(f"Reduction vs whole-repo read    : {100*(1-g_total/whole):>7.0f}%  ({whole/g_total:.1f}x)")


if __name__ == "__main__":
    main()
