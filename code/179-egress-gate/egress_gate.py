#!/usr/bin/env python3
"""egress-gate: deterministic pre-run check on outbound web calls.

Pattern borrowed from OpenAPPA (Agentic Permissions Policy Algebra): track what
a session has read, label it, and check every outbound call against those
labels BEFORE it runs. No second model judges anything; the same log and the
same policy always give the same answer.

Two hook entry points, one file:
  egress_gate.py taint   PostToolUse on Read|Grep|Glob|Bash
                         -> records labels for this session when it touches a
                            taint source (policy.toml [[taint_sources]])
  egress_gate.py check   PreToolUse on WebFetch|WebSearch|mcp__exa__.*
                         -> rule 1 secret_in_payload: a known secret value or
                            secret-shaped string in the URL/query. ALWAYS blocks.
                         -> rule 2 tainted_flow: the URL/query carries a
                            fingerprint of content this session read from a
                            taint source (4-word phrases, emails, long IDs) and
                            the host is not in allow_hosts. monitor mode logs
                            would_block; enforce mode blocks.
                         -> a tainted session calling an unlisted host with
                            none of that content is allowed and logged as
                            "tainted_clean". Labels alone do not block: v1 did
                            that and flagged 48% of real calls.
                         -> everything else: allow, logged.

Override: `egress-ok <host> [minutes]` writes a time-boxed allow. Every
override and every decision lands in egress.jsonl, so the weekly line to
Alfred can count them. A human sees the overrides, not just the agent.

Fails OPEN on any internal error (exit 0): over-blocking our own work is worse
than a missed log line, and the secret scan is the only hard stop.
"""
import fnmatch
import hashlib
import json
import os
import re
import sys
import time
import tomllib
import urllib.parse

HOME = os.path.expanduser("~")
BASE = os.path.dirname(os.path.abspath(__file__))
POLICY = os.environ.get("EGRESS_POLICY", os.path.join(BASE, "policy.toml"))
STATE = os.environ.get("EGRESS_STATE", os.path.join(HOME, ".claude", "egress"))
LOG = os.path.join(STATE, "egress.jsonl")
TAINT_DIR = os.path.join(STATE, "taint")
OVERRIDES = os.path.join(STATE, "overrides.json")

OUTBOUND = re.compile(r"^(WebFetch|WebSearch|mcp__exa__.*)$")

# Secret-shaped strings, independent of what is in any .env file.
SECRET_SHAPES = [
    (re.compile(r"\bsk-(ant-|proj-)?[A-Za-z0-9_-]{20,}"), "API key (sk-)"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"), "GitHub token"),
    (re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}"), "GitLab token"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS access key"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"), "JWT"),
    (re.compile(r"\bxox[abpr]-[A-Za-z0-9-]{20,}"), "Slack token"),
    (re.compile(r"\b\d{8,10}:AA[A-Za-z0-9_-]{30,}"), "Telegram bot token"),
]


def load_policy():
    with open(POLICY, "rb") as f:
        return tomllib.load(f)


def log(event):
    os.makedirs(STATE, exist_ok=True)
    event["ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(LOG, "a") as f:
        f.write(json.dumps(event) + "\n")


# ------------------------------------------------------------------ taint ---

def _candidates(tool, inp):
    """Strings from a tool input that might name a taint source."""
    if tool == "Bash":
        return [inp.get("command", "")]
    return [str(inp.get(k, "")) for k in ("file_path", "path", "pattern") if inp.get(k)]


def labels_for(tool, inp, policy):
    found = {}
    for src in policy.get("taint_sources", []):
        for text in _candidates(tool, inp):
            text = text.replace("~", HOME)
            for pat in src["patterns"]:
                pat_abs = pat.replace("~", HOME)
                if tool == "Bash":
                    # match the glob's distinctive tail anywhere in the command
                    core = pat_abs.replace("**/", "").replace("*", "")
                    if core and core in text:
                        found[src["label"]] = pat
                elif fnmatch.fnmatch(text, pat_abs) or fnmatch.fnmatch(text, "*/" + pat_abs.lstrip("*/")):
                    found[src["label"]] = pat
    return found


STOP = set("""a an and are as at be but by for from has have in is it its of on or that the
this to was were will with you your we our not no can do does how what when where which who why
into than then them they their there these those also more most about after before over""".split())
DISTINCT = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+|\b\d{7,}\b|\b(?=[A-Za-z0-9_-]*\d)(?=[A-Za-z0-9_-]*[A-Za-z])[A-Za-z0-9_-]{12,}\b")
MAX_FP = 2_000_000


def _h(x):
    return hashlib.blake2b(x.encode(), digest_size=8).hexdigest()


def fingerprints(text):
    """Hashed 4-word phrases (not all stopwords) plus distinctive tokens."""
    text = text[:2_000_000]
    fps = {_h("t:" + m.group(0).lower()) for m in DISTINCT.finditer(text)}
    words = re.findall(r"[a-z0-9']+", text.lower())
    for i in range(len(words) - 3):
        w = words[i:i + 4]
        if sum(x not in STOP for x in w) >= 3:
            fps.add(_h("p:" + " ".join(w)))
    return fps


def response_text(resp):
    if isinstance(resp, str):
        return resp
    try:
        return json.dumps(resp, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(resp)


def fp_path(session):
    return taint_path(session)[:-5] + ".fp"


URL_RX = re.compile(r"https?://\S+")


def record_content(session, text):
    # A link written inside a private file is not private: fetching it only
    # tells the site its own address. Drop URLs before fingerprinting.
    fps = fingerprints(URL_RX.sub(" ", text))
    if not fps:
        return
    os.makedirs(TAINT_DIR, exist_ok=True)
    with open(fp_path(session), "a") as f:
        f.write("\n".join(sorted(fps)) + "\n")


def read_fps(session):
    try:
        with open(fp_path(session)) as f:
            return set(f.read().split()[-MAX_FP:])
    except OSError:
        return set()


def taint_path(session):
    return os.path.join(TAINT_DIR, re.sub(r"[^A-Za-z0-9_-]", "_", session or "nosession") + ".json")


def read_taint(session):
    try:
        with open(taint_path(session)) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def record_taint(session, found, tool):
    cur = read_taint(session)
    new = {k: v for k, v in found.items() if k not in cur}
    if not new:
        return
    for label, pat in new.items():
        cur[label] = {"via": tool, "pattern": pat, "ts": int(time.time())}
    os.makedirs(TAINT_DIR, exist_ok=True)
    with open(taint_path(session), "w") as f:
        json.dump(cur, f)
    log({"event": "taint", "session": session, "labels": sorted(new), "via": tool})


# ------------------------------------------------------------------ check ---

def payload_of(tool, inp):
    """(destination host, outbound text) for an outbound tool call."""
    url = inp.get("url") or ""
    urls = inp.get("urls") or []
    if isinstance(urls, list) and urls and not url:
        url = urls[0]
    # Only what the destination actually receives. WebFetch's `prompt` goes to
    # the model that reads the page, not to the site, so it is not payload.
    if tool == "WebFetch":
        text = url
    else:
        text = " ".join(str(v) for k, v in inp.items() if k != "prompt" and isinstance(v, (str, list)))
    if url:
        host = (urllib.parse.urlparse(url).hostname or "").lower()
    elif tool == "WebSearch":
        host = "search:anthropic"
    elif tool.startswith("mcp__exa__"):
        host = "search:exa"
    else:
        host = "unknown"
    return host, text


_SECRET_CACHE = None


def secret_values(policy):
    global _SECRET_CACHE
    if _SECRET_CACHE is not None:
        return _SECRET_CACHE
    vals = {}
    for p in policy.get("secret_env_files", []):
        try:
            with open(os.path.expanduser(p)) as f:
                for ln in f:
                    m = re.match(r"\s*(?:export\s+)?([A-Z0-9_]+)\s*=\s*['\"]?([^'\"\s#]+)", ln)
                    if m and len(m.group(2)) >= 16 and not m.group(2).startswith("http"):
                        vals[m.group(2)] = m.group(1)
        except OSError:
            continue
    _SECRET_CACHE = vals
    return vals


def find_secret(text, policy):
    for val, name in secret_values(policy).items():
        if val in text or urllib.parse.quote(val, safe="") in text:
            return f"the value of {name}"
    for rx, what in SECRET_SHAPES:
        if rx.search(text):
            return f"a {what}"
    return None


def host_allowed(host, policy):
    if host.startswith("search:"):
        return False
    for h in policy.get("allow_hosts", []):
        if host == h or host.endswith("." + h):
            return True
    return host in active_overrides()


def active_overrides():
    try:
        with open(OVERRIDES) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return set()
    now = time.time()
    return {h for h, exp in data.items() if exp > now}


def decide(tool, inp, session, policy):
    """Pure decision. Returns dict(decision, rule, reason, remedy, host, labels)."""
    host, text = payload_of(tool, inp)
    labels = sorted(read_taint(session))
    base = {"tool": tool, "host": host, "labels": labels, "session": session}

    secret = find_secret(text, policy)
    if secret:
        return {**base, "decision": "block", "rule": "secret_in_payload",
                "reason": f"the outbound {tool} call carries {secret}",
                "remedy": "remove the secret from the URL/query; secrets never leave the box in a web call"}

    if labels and not host_allowed(host, policy):
        hits = len(fingerprints(text) & read_fps(session))
        if hits:
            enforce = policy.get("mode") == "enforce"
            return {**base, "decision": "block" if enforce else "would_block", "rule": "tainted_flow",
                    "reason": f"the outbound text repeats {hits} fingerprint(s) of {', '.join(labels)} content this session read, and {host} is not on the allow list",
                    "remedy": f"rewrite the URL/query without that content; if it is genuinely public: egress-ok {host} 60  (logged, counted in the weekly line to Alfred)"}
        return {**base, "decision": "allow", "rule": "tainted_clean", "reason": None, "remedy": None}

    return {**base, "decision": "allow", "rule": None, "reason": None, "remedy": None}


# ------------------------------------------------------------------ main ----

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"
    try:
        evt = json.load(sys.stdin)
        tool = evt.get("tool_name", "")
        inp = evt.get("tool_input") or {}
        session = evt.get("session_id", "")
        policy = load_policy()
    except Exception:
        return 0

    try:
        if mode == "taint":
            if tool in ("Read", "Grep", "Glob", "Bash"):
                found = labels_for(tool, inp, policy)
                if found:
                    record_taint(session, found, tool)
                    record_content(session, response_text(evt.get("tool_response", "")))
            return 0

        if not OUTBOUND.match(tool):
            return 0
        d = decide(tool, inp, session, policy)
        log({"event": "check", **{k: v for k, v in d.items() if k != "remedy"}})
        if d["decision"] == "block":
            print(f"egress-gate: blocked ({d['rule']}): {d['reason']}.\n"
                  f"remedy: {d['remedy']}", file=sys.stderr)
            return 2
        return 0
    except Exception:
        return 0


if __name__ == "__main__":
    sys.exit(main())
