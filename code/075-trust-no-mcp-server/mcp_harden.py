#!/usr/bin/env python3
"""
mcp-harden — treat every MCP server as untrusted.

Three jobs, one small script, standard library only:

  scan   Read your MCP client config, list every server, classify each as
         LOCAL (you run it) or REMOTE (someone else does), and flag posture
         problems: a secret sitting in a URL, plaintext http to a remote host,
         a remote server with no pin.

  pin    Take a snapshot of every tool's name + description that a server
         advertises, hash each one, and write a lockfile. This is the baseline
         you trust.

  check  Re-read the advertised tools, diff them against the lockfile, and
         shout if any part of a tool's schema changed under you (a silent
         rug-pull). At the same time, scan the WHOLE schema for poisoning, not
         just the description: tool and parameter names, type strings, enum
         values, the required list and any non-standard field. Pass --outputs
         to also scan captured tool outputs for the run-time-only ATPA payloads
         that no schema scan can see. Exit non-zero on any alarm so it works as
         a gate in CI or a pre-session hook.

No LLM inside. Pattern matching only, so the scanner cannot itself be talked
out of doing its job. No network: you feed it the advertised tools as JSON,
captured however you like, which keeps the gate deterministic and offline.

Exit codes:  0 clean  ·  1 alarm (stop, get a human)  ·  2 usage error.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

LOCK_NAME = "mcp-harden.lock.json"

# ---------------------------------------------------------------------------
# Config discovery
# ---------------------------------------------------------------------------

# Default places a Claude Code style client keeps MCP server definitions.
DEFAULT_CONFIGS = [
    "~/.claude.json",
    "~/.claude/settings.json",
    "~/.claude/settings.local.json",
    "./.claude/settings.json",
    "./.mcp.json",
]

# Query keys that mean "this is a credential pasted into a URL".
SECRET_KEYS = ("token", "key", "apikey", "api_key", "secret", "password", "auth")


def load_servers(config_paths):
    """Return {server_name: definition} merged across the given config files.

    Only the top-level mcpServers block of each file is read. Per-project blocks
    inside .claude.json are ignored on purpose: we harden the servers the agent
    actually loads, not every scratch directory it has ever opened.
    """
    servers = {}
    seen = []
    for raw in config_paths:
        p = Path(raw).expanduser()
        if not p.is_file():
            continue
        seen.append(str(p))
        try:
            data = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        block = data.get("mcpServers")
        if isinstance(block, dict):
            for name, defn in block.items():
                if isinstance(defn, dict):
                    servers[name] = defn
    return servers, seen


# ---------------------------------------------------------------------------
# Posture scan
# ---------------------------------------------------------------------------

LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1", "0.0.0.0")


def classify(defn):
    """LOCAL if we run it (stdio command or a loopback URL), else REMOTE."""
    if defn.get("command"):
        return "LOCAL"
    url = defn.get("url", "")
    host = re.sub(r"^\w+://", "", url).split("/")[0].split(":")[0].lower()
    return "LOCAL" if host in LOCAL_HOSTS else "REMOTE"


def url_secrets(url):
    """Return the secret-bearing query keys found in a URL, if any."""
    found = []
    for key, _val in re.findall(r"[?&]([^=]+)=([^&]*)", url):
        if any(s in key.lower() for s in SECRET_KEYS):
            found.append(key)
    return found


def server_allows_sampling(defn):
    """True if this server is configured to use MCP 'sampling' — where the
    server asks OUR model to run inference for it. A malicious server uses that
    to pre-condition the model's reasoning before a tool call, slipping past any
    pre-call check. Legitimate third-party servers almost never need it."""
    if defn.get("sampling") in (True, "allow", "enabled", "on"):
        return True
    caps = defn.get("capabilities")
    if isinstance(caps, dict) and caps.get("sampling"):
        return True
    if isinstance(caps, (list, tuple)) and "sampling" in caps:
        return True
    return False


def scan_posture(servers):
    findings = []
    for name, defn in sorted(servers.items()):
        kind = classify(defn)
        url = defn.get("url", "")
        secrets = url_secrets(url)
        if secrets:
            findings.append(
                (name, "HIGH", f"secret in URL query ({', '.join(secrets)}) — leaks via logs, history, referer"))
        if kind == "REMOTE" and url.startswith("http://"):
            findings.append(
                (name, "HIGH", "remote server over plaintext http — exposed to tampering in transit"))
        if kind == "REMOTE" and server_allows_sampling(defn):
            findings.append(
                (name, "HIGH", "remote server granted sampling — it can drive your model; deny it for third-party servers"))
        if kind == "REMOTE":
            findings.append(
                (name, "INFO", "remote third-party server — treat as untrusted, pin its tools"))
    return findings


# ---------------------------------------------------------------------------
# Tool-description poisoning scan
# ---------------------------------------------------------------------------

# Phrases that have no business in a tool description. A description tells the
# model WHAT a tool does; it should never instruct the model on what to DO,
# what to hide, or what to read.
INJECTION_PATTERNS = [
    (r"ignore (the |all |any )?(previous|prior|above)", "override of prior instructions"),
    (r"disregard (the |all |any )?(previous|prior|above)", "override of prior instructions"),
    (r"do not (tell|inform|mention|reveal|notify)", "instruction to hide activity from the user"),
    (r"(don'?t|never) (tell|inform|mention|reveal)", "instruction to hide activity from the user"),
    (r"before (you )?(use|using|calling|invoking)", "preconditioned side-effect on tool use"),
    (r"you (must|should|need to|have to) (also |first |always )?(read|send|call|run|fetch)",
     "imperative steering of the agent"),
    (r"<\s*(system|important|instructions?)\s*>", "fake system/instruction tags"),
    (r"\bsystem\s*:", "inline system-role injection"),
    (r"as an ai|as a language model", "role-priming injection"),
]

# Things a tool description points the agent AT in order to exfiltrate.
EXFIL_PATTERNS = [
    (r"~?/\.ssh|id_rsa|id_ed25519|authorized_keys", "SSH key path"),
    (r"\.env\b|environment variable|getenv|os\.environ", "environment / secrets"),
    (r"\.aws|credentials file|\.netrc|\.npmrc", "credential file"),
    (r"api[_ -]?key|secret key|access token|bearer", "credential reference"),
    (r"(send|post|exfiltrat|upload|forward|leak) .{0,30}(http|url|server|endpoint|webhook)",
     "send-data-to-endpoint instruction"),
]

# Unicode that renders invisible or reorders text — classic schema smuggling.
ZERO_WIDTH = {0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF}
BIDI = set(range(0x202A, 0x202F)) | set(range(0x2066, 0x206A))


def hidden_unicode(text):
    notes = []
    for ch in text:
        cp = ord(ch)
        if cp in ZERO_WIDTH:
            notes.append(f"zero-width char U+{cp:04X}")
        elif cp in BIDI:
            notes.append(f"bidi control U+{cp:04X}")
        elif 0xE0000 <= cp <= 0xE007F:
            notes.append(f"unicode tag char U+{cp:05X}")
    return sorted(set(notes))


def _dedupe(findings):
    """Drop repeats, keep first-seen order."""
    seen, out = set(), []
    for f in findings:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def scan_text(text):
    """Return (severity, note) findings for one piece of attacker-influenced text.

    This is the core matcher. It does not care WHERE the text came from — a
    description, a parameter name, or a tool's output. Whoever controls the
    string controls what the model reads, so every string gets the same scrutiny.
    """
    if not text:
        return []
    findings = []
    low = text.lower()
    for pat, label in INJECTION_PATTERNS:
        if re.search(pat, low):
            findings.append(("HIGH", f"injected instruction: {label}"))
    for pat, label in EXFIL_PATTERNS:
        if re.search(pat, low):
            findings.append(("HIGH", f"exfiltration hint: {label}"))
    for note in hidden_unicode(text):
        findings.append(("HIGH", f"hidden character: {note}"))
    return _dedupe(findings)


def scan_description(name, desc):
    """Back-compat shim: scan a single description string."""
    return scan_text(desc)


# Standard MCP tool keys. Anything else a server bolts on is "extra" and is a
# favourite hiding place, so we scan those non-standard string fields too.
_KNOWN_TOOL_KEYS = {"name", "description", "inputSchema", "input_schema", "_server"}


def iter_schema_strings(tool):
    """Yield (field_label, text) for every place in a tool's schema where an
    attacker can hide words the model will read.

    CyberArk's Full-Schema Poisoning result is the reason this exists: the
    description is not the only injection surface. Function and parameter NAMES,
    type strings, enum values, the required[] list and any non-standard extra
    field are all read by the model and all manipulate its behaviour. A scanner
    that only reads `description` waves the rest straight through.
    """
    yield ("name", tool.get("name", ""))
    yield ("description", tool.get("description", ""))
    schema = tool.get("inputSchema") or tool.get("input_schema") or {}
    if isinstance(schema, dict):
        props = schema.get("properties") or {}
        if isinstance(props, dict):
            for pname, pdef in props.items():
                yield (f"param-name:{pname}", str(pname))
                if isinstance(pdef, dict):
                    yield (f"param:{pname}.description", pdef.get("description", "") or "")
                    t = pdef.get("type")
                    if isinstance(t, str):
                        yield (f"param:{pname}.type", t)
                    for ev in (pdef.get("enum") or []):
                        if isinstance(ev, str):
                            yield (f"param:{pname}.enum", ev)
        for r in (schema.get("required") or []):
            if isinstance(r, str):
                yield ("required", r)
    for k, v in tool.items():
        if k in _KNOWN_TOOL_KEYS:
            continue
        if isinstance(v, str):
            yield (f"extra:{k}", v)


def scan_tool(tool):
    """Scan the WHOLE advertised schema of one tool, not just its description."""
    findings = []
    for label, text in iter_schema_strings(tool):
        for sev, note in scan_text(text):
            findings.append((sev, f"{label} -> {note}"))
    return _dedupe(findings)


# An Advanced Tool Poisoning Attack (ATPA) hides the payload in the tool's
# OUTPUT, not its schema, so it passes every pre-execution scan and only fires
# in production. The observable tell is an output that, after returning, steers
# the agent into a second action it never asked for.
SECONDARY_CALL_PATTERNS = [
    (r"\bnow (call|invoke|run|use|fetch)\b", "output tells the agent to perform a follow-up action"),
    (r"(call|invoke|use|run) (the )?[\w\-]+ tool", "output names another tool to call"),
    (r"to (continue|proceed|complete|finish|fix).{0,40}(call|invoke|provide|send|read|fetch)",
     "output demands a follow-up call to proceed"),
    (r"error.{0,60}(read|send|provide|include|call|fetch)",
     "error message that asks the agent to do something (classic ATPA bait)"),
]


def scan_output(text):
    """Scan a tool's OUTPUT before it re-enters the agent's context window."""
    findings = list(scan_text(text))
    low = (text or "").lower()
    for pat, label in SECONDARY_CALL_PATTERNS:
        if re.search(pat, low):
            findings.append(("HIGH", f"ATPA signature: {label}"))
    return _dedupe(findings)


def load_outputs(path):
    """Read captured tool outputs to scan. Accepts:
       {"server::tool": "output text", ...}  or
       [{"_server": s, "name": n, "output": "..."}, ...]
    """
    data = json.loads(Path(path).expanduser().read_text())
    out = []
    if isinstance(data, dict):
        for ref, body in data.items():
            out.append((ref, body if isinstance(body, str) else json.dumps(body)))
    elif isinstance(data, list):
        for item in data:
            ref = f"{item.get('_server','?')}::{item.get('name','?')}"
            body = item.get("output", "")
            out.append((ref, body if isinstance(body, str) else json.dumps(body)))
    return out


# ---------------------------------------------------------------------------
# Pinning + drift
# ---------------------------------------------------------------------------

def normalise(text):
    """Strip invisibles before hashing so a pin is stable, but the poison scan
    still sees the raw text. NFKC folds look-alike unicode tricks together."""
    cleaned = "".join(c for c in text if ord(c) not in ZERO_WIDTH and ord(c) not in BIDI)
    return unicodedata.normalize("NFKC", cleaned).strip()


def digest(text):
    return hashlib.sha256(normalise(text).encode("utf-8")).hexdigest()[:16]


def canonical_tool(tool):
    """Stable serialisation of a tool's full advertised schema, minus our own
    internal bookkeeping key. Sorted keys + tight separators so the same schema
    always hashes the same, regardless of field order."""
    body = {k: v for k, v in tool.items() if k != "_server"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest_tool(tool):
    """Fingerprint the WHOLE schema, not just the description. This is what makes
    a rug-pull in a parameter name or enum value as visible as one in the text."""
    return hashlib.sha256(normalise(canonical_tool(tool)).encode("utf-8")).hexdigest()[:16]


def load_tools(path):
    """Read advertised tools. Accepts either {server: [tools]} or a flat list.

    Each tool is a dict with at least name + description (the MCP tool shape)."""
    data = json.loads(Path(path).expanduser().read_text())
    if isinstance(data, dict):
        flat = []
        for server, tools in data.items():
            for t in tools:
                flat.append({**t, "_server": server})
        return flat
    return [{**t, "_server": t.get("_server", "?")} for t in data]


def build_lock(tools):
    lock = {}
    for t in tools:
        ref = f"{t.get('_server','?')}::{t['name']}"
        lock[ref] = digest_tool(t)
    return lock


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_scan(args):
    servers, seen = load_servers(args.config or DEFAULT_CONFIGS)
    print(f"# mcp-harden scan  ·  {len(servers)} server(s) across {len(seen)} config file(s)")
    for f in seen:
        print(f"  config: {f}")
    print()
    if not servers:
        print("No MCP servers found. Nothing to harden (or wrong --config path).")
        return 0
    for name, defn in sorted(servers.items()):
        kind = classify(defn)
        target = defn.get("command") or defn.get("url", "")
        # Redact any secret before printing the URL.
        target = re.sub(r"([?&])([^=]*(?:token|key|secret|auth)[^=]*)=([^&]+)",
                        r"\1\2=<redacted>", target, flags=re.I)
        print(f"[{kind:6}] {name:12} {target}")
    print()
    findings = scan_posture(servers)
    highs = [f for f in findings if f[1] == "HIGH"]
    for name, sev, note in findings:
        mark = "!!" if sev == "HIGH" else "··"
        print(f"  {mark} [{sev:4}] {name}: {note}")
    print()
    if highs:
        print(f"RESULT: {len(highs)} posture issue(s) to fix. Rotate URL secrets into headers/env; pin remote tools.")
        return 1
    print("RESULT: posture clean.")
    return 0


def cmd_pin(args):
    tools = load_tools(args.tools)
    lock = build_lock(tools)
    Path(args.lock).expanduser().write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")
    print(f"Pinned {len(lock)} tool(s) to {args.lock}")
    # Even at pin time, refuse to bless an already-poisoned schema (any field).
    poisoned = 0
    for t in tools:
        for sev, note in scan_tool(t):
            poisoned += 1
            print(f"  !! WARNING pinning a flagged tool {t.get('_server','?')}::{t['name']}: {note}")
    if poisoned:
        print("Refusing to treat this as a clean baseline — investigate before trusting the lock.")
        return 1
    return 0


def cmd_check(args):
    tools = load_tools(args.tools)
    alarms = 0

    # 1. Poison scan across the WHOLE live schema (name, params, types, enums,
    #    required, extras), not just the description.
    for t in tools:
        ref = f"{t.get('_server','?')}::{t['name']}"
        for sev, note in scan_tool(t):
            alarms += 1
            print(f"  !! [POISON] {ref}: {note}")

    # 1b. Optionally scan captured tool OUTPUTS — the ATPA surface that no
    #     schema scan can see, because the payload only appears at run time.
    if getattr(args, "outputs", None):
        for ref, body in load_outputs(args.outputs):
            for sev, note in scan_output(body):
                alarms += 1
                print(f"  !! [OUTPUT] {ref}: {note}")

    # 2. Drift against the lockfile.
    lock_path = Path(args.lock).expanduser()
    if lock_path.is_file():
        lock = json.loads(lock_path.read_text())
        live = build_lock(tools)
        for ref, h in live.items():
            if ref not in lock:
                alarms += 1
                print(f"  !! [NEW]    {ref}: tool not in lockfile — appeared since last pin")
            elif lock[ref] != h:
                alarms += 1
                print(f"  !! [DRIFT]  {ref}: description changed under you (rug-pull) — re-pin only after review")
        for ref in lock:
            if ref not in live:
                print(f"  ·· [GONE]   {ref}: pinned tool no longer advertised")
    else:
        print(f"  ·· no lockfile at {args.lock} — run `pin` first to enable drift detection")

    print()
    if alarms:
        print(f"RESULT: {alarms} alarm(s). Do NOT load these servers until a human has looked.")
        return 1
    print("RESULT: tools match the pin and carry no poisoning. Safe to load.")
    return 0


def cmd_demo(args):
    here = Path(__file__).parent / "examples"
    clean = here / "tools-clean.json"
    poison = here / "tools-poisoned.json"
    out_clean = here / "outputs-clean.json"
    out_poison = here / "outputs-poisoned.json"
    lock = here / "demo.lock.json"
    print("=== 1. pin the clean tool set ===")
    cmd_pin(argparse.Namespace(tools=str(clean), lock=str(lock)))
    print("\n=== 2. check the SAME clean set + clean outputs (should pass) ===")
    rc_clean = cmd_check(argparse.Namespace(tools=str(clean), lock=str(lock),
                                            outputs=str(out_clean)))
    print("\n=== 3. server rug-pulls + poisons schema (incl. a parameter NAME), re-check (should FAIL) ===")
    rc_poison = cmd_check(argparse.Namespace(tools=str(poison), lock=str(lock),
                                             outputs=None))
    print("\n=== 4. schema looks clean but a tool OUTPUT carries an ATPA payload (should FAIL) ===")
    rc_atpa = cmd_check(argparse.Namespace(tools=str(clean), lock=str(lock),
                                           outputs=str(out_poison)))
    lock.unlink(missing_ok=True)
    print()
    ok = (rc_clean == 0 and rc_poison == 1 and rc_atpa == 1)
    print("DEMO PASS — gate passed the clean set and caught both a full-schema rug-pull and an output-only ATPA."
          if ok else "DEMO FAIL — gate did not behave as expected.")
    return 0 if ok else 1


def main(argv=None):
    p = argparse.ArgumentParser(prog="mcp-harden", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="audit MCP client config posture")
    s.add_argument("--config", action="append", help="config file (repeatable)")
    s.set_defaults(func=cmd_scan)

    s = sub.add_parser("pin", help="snapshot advertised tools to a lockfile")
    s.add_argument("tools", help="JSON of advertised tools")
    s.add_argument("--lock", default=LOCK_NAME)
    s.set_defaults(func=cmd_pin)

    s = sub.add_parser("check", help="diff tools vs lock + scan whole schema (and outputs) for poisoning")
    s.add_argument("tools", help="JSON of advertised tools")
    s.add_argument("--lock", default=LOCK_NAME)
    s.add_argument("--outputs", help="JSON of captured tool outputs to scan for ATPA")
    s.set_defaults(func=cmd_check)

    s = sub.add_parser("demo", help="self-contained clean-vs-poisoned walkthrough")
    s.set_defaults(func=cmd_demo)

    args = p.parse_args(argv)
    try:
        return args.func(args)
    except (OSError, json.JSONDecodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
