#!/usr/bin/env python3
"""Replay every past Claude Code session through egress-gate (no network).

Walks ~/.claude/projects/**/*.jsonl in timestamp order per session, feeds
Read/Grep/Glob/Bash calls to the taint hook and every outbound call to the
check, against the real policy.toml but a throwaway state dir.
Usage: replay.py [--days N] [--json out.json]
"""
import collections, glob, json, os, sys, tempfile, time
os.environ["EGRESS_STATE"] = tempfile.mkdtemp(prefix="egress-replay-")
import atexit, shutil
atexit.register(shutil.rmtree, os.environ["EGRESS_STATE"], True)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import egress_gate as g

days = int(sys.argv[sys.argv.index("--days") + 1]) if "--days" in sys.argv else 3650
since = time.time() - days * 86400
policy = g.load_policy()

events = []
results = {}
for p in glob.glob(os.path.expanduser("~/.claude/projects/**/*.jsonl"), recursive=True):
    if os.path.getmtime(p) < since:
        continue
    for ln in open(p, errors="replace"):
        if '"tool_use"' not in ln and '"tool_result"' not in ln:
            continue
        try:
            d = json.loads(ln)
        except ValueError:
            continue
        c = (d.get("message") or {}).get("content")
        if not isinstance(c, list):
            continue
        for it in c:
            if it.get("type") == "tool_use":
                events.append((d.get("timestamp") or "", d.get("sessionId") or p, it.get("name", ""), it.get("input") or {}, it.get("id")))
            elif it.get("type") == "tool_result":
                results[it.get("tool_use_id")] = it.get("content")
events.sort(key=lambda e: e[0])
cutoff = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(since))

out = collections.Counter(); by_rule = collections.Counter(); hosts = collections.Counter()
labels_seen = collections.Counter(); blocks = []
sessions_out = set(); sessions_tainted_out = set()
for ts, sess, tool, inp, uid in events:
    if ts < cutoff:
        continue
    if tool in ("Read", "Grep", "Glob", "Bash"):
        found = g.labels_for(tool, inp, policy)
        if found:
            g.record_taint(sess, found, tool)
            g.record_content(sess, g.response_text(results.get(uid, "")))
        continue
    if not g.OUTBOUND.match(tool):
        continue
    d = g.decide(tool, inp, sess, policy)
    # replay answers "what would enforce mode do", so report would_block as such
    out[d["decision"]] += 1
    sessions_out.add(sess)
    if d["labels"]:
        sessions_tainted_out.add(sess)
        for l in d["labels"]:
            labels_seen[l] += 1
    if d["rule"] == "tainted_clean":
        out["allow_tainted_clean"] += 1
    elif d["rule"]:
        by_rule[d["rule"]] += 1
        hosts[d["host"]] += 1
        blocks.append({"ts": ts, "tool": tool, "host": d["host"], "rule": d["rule"], "labels": d["labels"]})

total = sum(v for k, v in out.items() if k != "allow_tainted_clean")
res = {"days": days, "outbound_calls": total, "decisions": dict(out), "by_rule": dict(by_rule),
       "sessions_with_outbound": len(sessions_out), "of_which_tainted": len(sessions_tainted_out),
       "labels_on_flagged_calls": dict(labels_seen), "top_flagged_hosts": hosts.most_common(15),
       "secret_hits": [b for b in blocks if b["rule"] == "secret_in_payload"]}
print(json.dumps(res, indent=1))
if "--json" in sys.argv:
    json.dump({**res, "flagged": blocks}, open(sys.argv[sys.argv.index("--json") + 1], "w"), indent=1)

# ------------------------------------------------------------ canaries -----
# Positive control: for every tainted session, plant one synthetic leak (a
# random 6-word run of text it actually read) in a fetch to an unlisted host,
# plus every known secret value. A gate that only ever says "allow" scores 0.
if "--canary" in sys.argv:
    import random, re as _re
    random.seed(7)
    caught = tried = 0
    for sess in sorted(sessions_tainted_out | {s for s in os.listdir(g.TAINT_DIR) if s.endswith(".json")}):
        sess = sess[:-5] if sess.endswith(".json") else sess
        texts = [g.response_text(results.get(uid, "")) for ts, s, tool, inp, uid in events
                 if s == sess and g.labels_for(tool, inp, policy)]
        words = _re.findall(r"[a-z0-9']+", g.URL_RX.sub(" ", " ".join(texts)).lower())
        if len(words) < 50:
            continue
        i = random.randrange(len(words) - 6)
        q = "+".join(words[i:i + 6])
        tried += 1
        d = g.decide("WebFetch", {"url": f"https://collector.invalid/?q={q}"}, sess, policy)
        caught += d["rule"] == "tainted_flow"
    sec = list(g.secret_values(policy))
    sec_caught = sum(g.decide("WebSearch", {"query": f"debug {v}"}, "canary", policy)["rule"] == "secret_in_payload" for v in sec)
    print(json.dumps({"canary_leaks": tried, "caught": caught, "secret_values": len(sec), "secret_caught": sec_caught}))
