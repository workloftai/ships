#!/usr/bin/env python3
"""
End-to-end tests for dns_guard: start real guards (enforce + monitor) on
loopback, send real DNS queries, assert on the answers AND on the audit log.
Needs a working upstream resolver (127.0.0.53). Run: python3 tests/test_dns_guard.py
"""

import json
import os
import random
import socket
import struct
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import dns_guard as DG  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + (f"  ({detail})" if detail and not cond else ""))


def free_udp_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def start(mode, log):
    port = free_udp_port()
    proc = subprocess.Popen([sys.executable, os.path.join(ROOT, "dns_guard.py"), "--mode", mode,
                             "--port", str(port), "--log", log],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    proc.stdout.readline()  # wait for the banner
    return proc, port


def build_query(name, qtype):
    txid = random.randint(0, 0xFFFF)
    q = b"".join(bytes([len(p)]) + p.encode() for p in name.split(".")) + b"\0"
    return txid, struct.pack(">HHHHHH", txid, 0x0100, 1, 0, 0, 0) + q + struct.pack(">HH", qtype, 1)


def ask(port, name, qtype=1):
    """Returns (rcode, answer_count) or 'timeout'."""
    txid, pkt = build_query(name, qtype)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(6)
    try:
        s.sendto(pkt, ("127.0.0.1", port))
        reply, _ = s.recvfrom(4096)
    except socket.timeout:
        return "timeout"
    finally:
        s.close()
    rid, flags, _qd, an = struct.unpack(">HHHH", reply[:8])
    if rid != txid:
        return "bad-id"
    return flags & 0xF, an


def events(log):
    with open(log) as f:
        return [json.loads(ln) for ln in f]


def main():
    tmp = tempfile.mkdtemp()
    payload = "mzxw6ytboi2dsnrtgq3donzygm4tambrgeztanbvgy3tqojqgezdg"  # base32 of a 'secret'

    # --- unit -----------------------------------------------------------------
    _, pkt = build_query("api.anthropic.com", 1)
    q = DG.parse_query(pkt)
    check("parser reads name and type", q and q[1] == "api.anthropic.com" and q[2] == 1, q)
    check("allowlisted name, A record: allowed", DG.decide("api.anthropic.com", 1)[0])
    check("off-list name: refused", not DG.decide("example.com", 1)[0])
    check("TXT refused even for an allowed name", not DG.decide("api.anthropic.com", 16)[0])
    check("suffix-safe (evilanthropic.com refused)", not DG.decide("evilanthropic.com", 1)[0])
    check("ordinary hostname has no tunnel signature",
          DG.tunnel_signature("generativelanguage.googleapis.com") is None)
    check("base32 payload label has a tunnel signature",
          DG.tunnel_signature(payload + ".x.example") is not None)

    # --- e2e: enforce ---------------------------------------------------------
    log = os.path.join(tmp, "enforce.ndjson")
    proc, port = start("enforce", log)
    try:
        r = ask(port, "api.anthropic.com")
        check("enforce: allowlisted name resolves", r != "timeout" and r[0] == 0 and r[1] > 0, r)
        r = ask(port, "example.com")
        check("enforce: off-list name gets NXDOMAIN", r != "timeout" and r[0] == 3, r)
        r = ask(port, "api.anthropic.com", 16)
        check("enforce: TXT for an allowed name gets NXDOMAIN", r != "timeout" and r[0] == 3, r)
        r = ask(port, payload + ".tunnel.example")
        check("enforce: tunnel-shaped query gets NXDOMAIN", r != "timeout" and r[0] == 3, r)
        r = ask(port, payload + ".supabase.co")
        check("enforce: payload under an allowed base still answered (policy is by name)",
              r != "timeout", r)
        time.sleep(0.3)
    finally:
        proc.terminate()
        proc.wait()
    ev = events(log)
    blocks = [e for e in ev if e["decision"] == "block"]
    check("audit: 3 blocks recorded", len(blocks) == 3, [e["host"] for e in blocks])
    check("audit: the TXT block names the record type",
          any(e["qtype"] == "TXT" and "record type" in e["reason"] for e in blocks))
    sigs = [e for e in ev if e.get("tunnel_signature")]
    check("audit: both payload queries flagged with a tunnel signature, allowed base or not",
          len(sigs) == 2, [(e["host"][-20:], e["decision"]) for e in sigs])

    # --- e2e: monitor ---------------------------------------------------------
    log = os.path.join(tmp, "monitor.ndjson")
    proc, port = start("monitor", log)
    try:
        r = ask(port, "example.com")
        check("monitor: off-list name still resolves", r != "timeout" and r[0] == 0 and r[1] > 0, r)
        time.sleep(0.3)
    finally:
        proc.terminate()
        proc.wait()
    ev = events(log)
    check("monitor: logged as would_block",
          any(e["host"] == "example.com" and e["decision"] == "would_block" for e in ev))

    # --- safety ---------------------------------------------------------------
    r = subprocess.run([sys.executable, os.path.join(ROOT, "dns_guard.py"), "--host", "0.0.0.0"],
                       capture_output=True, text=True, timeout=10)
    check("refuses to bind non-loopback (never an open resolver)",
          r.returncode != 0 and "refusing" in (r.stderr + r.stdout))

    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
