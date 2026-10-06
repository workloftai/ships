#!/usr/bin/env python3
"""Replay the same real sessions through egress-gate AND OpenAPPA, side by side.

1. Translates policy.toml into an OpenAPPA policy (appa.toml): reading a taint
   source narrows the session audience to "alfred"; a web call to an allow-listed
   host needs nothing; any other web call needs audience "public".
2. Walks ~/.claude/projects/**/*.jsonl like replay.py, and for every session
   that made an outbound call writes a .appa trace: the taint-source reads plus
   every outbound call, in order.
3. Runs `appa replay -v` on the traces and compares each outbound decision with
   egress-gate's decide() on the same call.
4. Plants the same canary leaks replay.py does and asks both engines.

No network, no model: the OpenAPPA policy here uses only exact contracts (no
annotators), so both sides are deterministic.
Usage: compare.py --appa /path/to/appa [--days N] [--out DIR]
"""
import collections, glob, json, os, random, re, subprocess, sys, tempfile, time, tomllib
os.environ["EGRESS_STATE"] = tempfile.mkdtemp(prefix="egress-cmp-")
import atexit, shutil
atexit.register(shutil.rmtree, os.environ["EGRESS_STATE"], True)
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))                         # ~/egress-gate/openappa
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "179-egress-gate"))  # ships repo layout
import egress_gate as g

arg = lambda k, d=None: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
APPA = arg("--appa", "appa")
DAYS = int(arg("--days", "3650"))
OUT = arg("--out", os.path.join(HERE, "run"))
since = time.time() - DAYS * 86400
policy = g.load_policy()

# ---------------------------------------------------------------- policy ----
def sel(pattern):
    core = pattern.replace("**/", "/").strip("*")
    return f"*{core}*"

def tool_name(tool):
    if tool.startswith("mcp__"):
        server, _, name = tool[5:].partition("__")
        return f"mcp/{server}/{name}"
    return f"host/claude-code/{tool}"

TAINT_ARG = {"Read": "file_path", "Grep": "path", "Glob": "pattern", "Bash": "command"}
OUT_TOOLS = ["WebFetch", "WebSearch", "mcp__exa__web_search_exa", "mcp__exa__web_fetch_exa"]

def build_policy():
    L = ["# Generated from egress-gate/policy.toml by compare.py. Do not edit.",
         "[policy]", "version = 2", ""]
    pats = sorted({sel(p) for src in policy["taint_sources"] for p in src["patterns"]})
    for tool, a in TAINT_ARG.items():
        for p in pats:
            L += ["[[policy.tool]]", f'name = {json.dumps(f"{tool_name(tool)}({a}:{p})")}',
                  'delta = { audience = ["alfred"] }', ""]
        L += ["[[policy.tool]]", f'name = "{tool_name(tool)}"', "delta = {}", ""]
    for tool in ("WebFetch", "mcp__exa__web_fetch_exa"):
        a = "url" if tool == "WebFetch" else "urls"
        if tool == "WebFetch":
            for h in policy["allow_hosts"]:
                for pre in (f"https://{h}/*", f"https://*.{h}/*", f"http://{h}/*"):
                    L += ["[[policy.tool]]", f'name = {json.dumps(f"{tool_name(tool)}({a}:{pre})")}', "delta = {}", ""]
    for tool in OUT_TOOLS:
        L += ["[[policy.tool]]", f'name = "{tool_name(tool)}"',
              'requires = { audience = { contains = ["public"] } }', "delta = {}", ""]
    L += ["[externals]", "timeout_ms = 2000", "max_body_bytes = 65536", ""]
    return "\n".join(L)

# ------------------------------------------------------------- sessions ----
events, results = [], {}
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

def step(tool, inp, keys):
    body = []
    for k in keys:
        v = inp.get(k)
        if v is None:
            continue
        if isinstance(v, list):
            v = " ".join(map(str, v))
        body.append(f"  {k}: {json.dumps(str(v)[:4000])}")
    return f"{tool_name(tool)} {{\n" + "\n".join(body) + "\n}\nexpect allow\n"

ARGS = {"Read": ["file_path"], "Grep": ["path", "pattern"], "Glob": ["pattern", "path"], "Bash": ["command"],
        "WebFetch": ["url"], "WebSearch": ["query"], "mcp__exa__web_search_exa": ["query"],
        "mcp__exa__web_fetch_exa": ["urls"]}

traces = collections.defaultdict(list)   # sess -> [(tool, inp, gate_decision|None)]
for ts, sess, tool, inp, uid in events:
    if ts < cutoff:
        continue
    if tool in TAINT_ARG:
        found = g.labels_for(tool, inp, policy)
        if found:
            g.record_taint(sess, found, tool)
            g.record_content(sess, g.response_text(results.get(uid, "")))
            traces[sess].append((tool, inp, None))
        continue
    if tool in OUT_TOOLS:
        d = g.decide(tool, inp, sess, policy)
        traces[sess].append((tool, inp, d))

os.makedirs(os.path.join(OUT, "traces"), exist_ok=True)
pol = os.path.join(OUT, "appa.toml")
open(pol, "w").write(build_policy())
keep = {s: t for s, t in traces.items() if any(d for _, _, d in t)}
for s, t in keep.items():
    with open(os.path.join(OUT, "traces", f"{re.sub(r'[^A-Za-z0-9-]', '_', s)[-60:]}.appa"), "w") as f:
        f.write(f"# session {s}\n")
        for tool, inp, d in t:
            f.write(step(tool, inp, ARGS.get(tool, [])) + "\n")

# ---------------------------------------------------------------- compare ---
def appa_decisions(path):
    # appa replay stops at the first step whose expectation fails, so flip that
    # step's expectation to what OpenAPPA decided and replay again until the
    # whole trace passes. A denied call then behaves as in enforcement: it never
    # ran, so it adds nothing to the session label.
    for _ in range(200):
        r = subprocess.run([APPA, "replay", "--config", pol, "-v", path], capture_output=True, text=True)
        m = re.search(r"^\S+?:(\d+): \S+: got (allow|deny)", r.stdout + r.stderr, re.M)
        if not m:
            break
        lines = open(path).read().split("\n")
        i = int(m.group(1)) - 1
        while not lines[i].startswith("expect "):
            i += 1
        lines[i] = "expect " + m.group(2)
        open(path, "w").write("\n".join(lines))
    out = {}
    for ln in (r.stdout + r.stderr).splitlines():
        m = re.match(r"^(ok|FAIL|fail)\S*\s+(\S+?):(\d+)\s+(\S+)\s+(allow|deny)", ln)
        if m:
            out[(os.path.basename(m.group(2)), int(m.group(3)))] = m.group(5)
            continue
        m = re.match(r"^(\S+?):(\d+): \S+: got (allow|deny)", ln)
        if m:
            out[(os.path.basename(m.group(1)), int(m.group(2)))] = m.group(3)
    return out, r

grid = collections.Counter(); examples = collections.defaultdict(list); unparsed = 0
for s, t in keep.items():
    fn = f"{re.sub(r'[^A-Za-z0-9-]', '_', s)[-60:]}.appa"
    dec, r = appa_decisions(os.path.join(OUT, "traces", fn))
    line = 2
    for tool, inp, d in t:
        n_lines = step(tool, inp, ARGS.get(tool, [])).count("\n") + 1
        if d is not None:
            a = dec.get((fn, line))
            if a is None:
                unparsed += 1
            else:
                gate = "deny" if d["decision"] != "allow" else "allow"
                k = f"gate:{gate} appa:{a}"
                grid[k] += 1
                if gate != a and len(examples[k]) < 8:
                    examples[k].append({"tool": tool, "host": d["host"], "labels": d["labels"], "rule": d["rule"]})
        line += n_lines

# ---------------------------------------------------------------- canaries --
random.seed(7)
c_tried = c_gate = c_appa = 0
tainted = [s for s, t in keep.items() if any(d is None for _, _, d in t)]
cdir = os.path.join(OUT, "canaries"); os.makedirs(cdir, exist_ok=True)
for s in tainted:
    texts = [g.response_text(results.get(uid, "")) for ts, ss, tool, inp, uid in events
             if ss == s and tool in TAINT_ARG and g.labels_for(tool, inp, policy)]
    words = re.findall(r"[a-z0-9']+", g.URL_RX.sub(" ", " ".join(texts)).lower())
    if len(words) < 50:
        continue
    i = random.randrange(len(words) - 6)
    url = "https://collector.invalid/?q=" + "+".join(words[i:i + 6])
    c_tried += 1
    c_gate += g.decide("WebFetch", {"url": url}, s, policy)["rule"] == "tainted_flow"
    first = next((tool, inp) for tool, inp, d in keep[s] if d is None)
    fn = os.path.join(cdir, f"c{c_tried}.appa")
    open(fn, "w").write(step(*first, ARGS[first[0]]) + "\n" + step("WebFetch", {"url": url}, ["url"]))
    dec, _ = appa_decisions(fn)
    c_appa += "deny" in [v for (f, ln), v in dec.items() if ln > 3]

res = {"days": DAYS, "sessions_compared": len(keep), "sessions_tainted": len(tainted),
       "outbound_calls": sum(grid.values()), "grid": dict(grid), "unparsed": unparsed,
       "canaries": {"planted": c_tried, "egress_gate_caught": c_gate, "openappa_caught": c_appa},
       "disagreement_examples": examples}
print(json.dumps(res, indent=1))
json.dump(res, open(os.path.join(OUT, "result.json"), "w"), indent=1)
