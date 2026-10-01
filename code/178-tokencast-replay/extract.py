"""Turn Claude Code session logs into per-task token traces.

A task is one turn: every model call the agent makes between being handed
something and finishing. Each call records what it cost (all input incl. cache, plus output) and
how big the context was. Only numbers leave this script, never content.
"""
import glob, json, os, sys

def tasks_in(path):
    """Yield (start_ts, calls). A task ends at the log's turn_duration marker."""
    seen, cur, start = set(), [], None
    for line in open(path, errors="ignore"):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("isSidechain"):
            continue
        if d.get("type") == "system" and d.get("subtype") == "turn_duration":
            if cur:
                yield start, cur
            cur, start = [], None
        elif d.get("type") == "assistant":
            m = d.get("message", {})
            if m.get("model") == "<synthetic>" or m.get("id") in seen:
                continue
            seen.add(m.get("id"))
            u = m.get("usage") or {}
            cached = u.get("cache_read_input_tokens", 0)
            inp = u.get("input_tokens", 0) + cached + u.get("cache_creation_input_tokens", 0)
            out = u.get("output_tokens", 0)
            if inp + out:
                start = start or d.get("timestamp")
                cur.append([inp, out, cached])
    if cur:
        yield start, cur

if __name__ == "__main__":
    root = os.path.expanduser(sys.argv[1] if len(sys.argv) > 1 else "~/.claude/projects")
    out = []
    for p in glob.glob(f"{root}/*/*.jsonl"):
        for ts, calls in tasks_in(p):
            if calls and ts:
                out.append({"ts": ts, "calls": calls})
    out.sort(key=lambda r: r["ts"])
    json.dump(out, open(sys.argv[2] if len(sys.argv) > 2 else "traces.json", "w"))
    n = sum(len(r["calls"]) for r in out)
    print(f"{len(out)} tasks, {n} model calls, {out[0]['ts'][:10]} to {out[-1]['ts'][:10]}")
