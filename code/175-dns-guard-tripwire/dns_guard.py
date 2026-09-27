#!/usr/bin/env python3
"""
dns_guard: phase three of egress_guard. An allowlisting DNS resolver.

Why this exists. An HTTP(S) proxy that filters by hostname does nothing about
DNS. A DNS query is itself an outbound message: the name you ask about travels
through the resolver chain to whoever runs the authoritative server for that
zone. Put data in the name (`c2VjcmV0.attacker.example`) and you have a channel
out that no web proxy ever sees. In September 2026 an agent in OpenAI's training
sandbox did roughly this: web access was blocked, the DNS resolver was not
filtered, and it used DNS to reach an outside chatbot.

Our own unarmed phase-one ruleset (egress.nft) had the same hole: it allowed
port 53 to anywhere. This closes it at the name layer:

  1. Only names on the platform allowlist (allowlist.py) resolve. Everything
     else gets NXDOMAIN in enforce mode, or is forwarded and logged as
     would_block in monitor mode.
  2. Only ordinary record types resolve (A, AAAA, CNAME, HTTPS, SVCB). TXT,
     NULL, ANY and friends are the usual carriers for DNS tunnels and nothing
     in the fleet needs them.
  3. Names that look like payloads (a very long label, or a long high-entropy
     one) are flagged as `tunnel_signature` in the audit, even when the base
     domain is allowed, because that is the signal a human should look at.

Same NDJSON audit shape as egress_proxy, so one report covers both.

Loopback only. It forwards allowed queries to an upstream resolver (default
127.0.0.53, systemd-resolved). The unskippable version points resolved at this
guard and only lets this guard's user send port 53 off the box; see
`egress_guard.py gen-nft`. Arming that is a human decision.

Stdlib only.
"""

import argparse
import asyncio
import json
import math
import os
import socket
import struct
import sys
import time
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import egress_proxy as EP  # noqa: E402

DEFAULT_LOG = os.path.join(HERE, "logs", "dns-audit.ndjson")
QTYPES = {1: "A", 2: "NS", 5: "CNAME", 6: "SOA", 10: "NULL", 12: "PTR", 15: "MX",
          16: "TXT", 28: "AAAA", 33: "SRV", 64: "SVCB", 65: "HTTPS", 255: "ANY"}
ALLOWED_QTYPES = {1, 5, 28, 64, 65}
LONG_LABEL = 40          # RFC max is 63; real hostnames rarely pass 30
ENTROPY_LABEL = 20       # only score labels at least this long
ENTROPY_BITS = 3.8       # bits/char; base32/base64 payloads sit above this


# ---------------------------------------------------------------- parsing ---

def parse_query(pkt):
    """Return (txid, qname, qtype, question_end) or None if unparseable."""
    try:
        txid, _flags, qd = struct.unpack(">HHH", pkt[:6])
        if qd != 1:
            return None
        p, labels = 12, []
        while pkt[p]:
            n = pkt[p]
            if n & 0xC0:  # compression pointer in a question: refuse
                return None
            labels.append(pkt[p + 1:p + 1 + n].decode("ascii", "replace"))
            p += 1 + n
        p += 1
        qtype, _qclass = struct.unpack(">HH", pkt[p:p + 4])
        return txid, ".".join(labels).lower(), qtype, p + 4
    except Exception:
        return None


def nxdomain(pkt, qend):
    """Minimal NXDOMAIN answer to pkt: same id and question, no records."""
    txid, flags = struct.unpack(">HH", pkt[:4])
    rd = flags & 0x0100
    hdr = struct.pack(">HHHHHH", txid, 0x8000 | 0x0400 | rd | 0x0080 | 3, 1, 0, 0, 0)
    return hdr + pkt[12:qend]


def _entropy(s):
    c = Counter(s)
    return -sum(v / len(s) * math.log2(v / len(s)) for v in c.values())


def tunnel_signature(qname):
    """Reason string if the name looks like it carries a payload, else None."""
    for label in qname.split("."):
        if len(label) >= LONG_LABEL:
            return f"label of {len(label)} chars"
        if len(label) >= ENTROPY_LABEL and _entropy(label) >= ENTROPY_BITS:
            return f"high-entropy label ({_entropy(label):.1f} bits/char)"
    return None


def decide(qname, qtype):
    """(allowed, reason). Same platform allowlist as the proxy; port is moot."""
    if qtype not in ALLOWED_QTYPES:
        return False, f"record type {QTYPES.get(qtype, qtype)} not allowed"
    return EP.decide(qname, 443, None)


# ---------------------------------------------------------------- server ----

class Guard(asyncio.DatagramProtocol):
    def __init__(self, mode, log_path, upstream):
        self.mode, self.log_path, self.upstream = mode, log_path, upstream
        os.makedirs(os.path.dirname(log_path), exist_ok=True)

    def connection_made(self, transport):
        self.transport = transport

    def audit(self, **ev):
        ev = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "mode": self.mode,
              "loop": "dns", **ev}
        with open(self.log_path, "a") as f:
            f.write(json.dumps(ev) + "\n")

    def datagram_received(self, pkt, addr):
        q = parse_query(pkt)
        if q is None:
            self.audit(decision="block", host=None, reason="unparseable query")
            return
        _txid, qname, qtype, qend = q
        allowed, reason = decide(qname, qtype)
        sig = tunnel_signature(qname)
        ev = dict(host=qname, qtype=QTYPES.get(qtype, qtype), reason=reason)
        if sig:
            ev["tunnel_signature"] = sig
        if not allowed and self.mode == "enforce":
            self.audit(decision="block", **ev)
            self.transport.sendto(nxdomain(pkt, qend), addr)
            return
        self.audit(decision="allow" if allowed else "would_block", **ev)
        asyncio.get_running_loop().create_task(self.forward(pkt, addr))

    async def forward(self, pkt, addr):
        loop = asyncio.get_running_loop()
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setblocking(False)
        try:
            await loop.sock_sendto(s, pkt, self.upstream)
            reply = await asyncio.wait_for(loop.sock_recv(s, 4096), 5)
            self.transport.sendto(reply, addr)
        except Exception:
            pass  # client retries or times out; nothing to leak
        finally:
            s.close()


async def serve(host, port, mode, log_path, upstream):
    loop = asyncio.get_running_loop()
    await loop.create_datagram_endpoint(lambda: Guard(mode, log_path, upstream),
                                        local_addr=(host, port))
    print(f"dns_guard {mode} on {host}:{port} -> {upstream[0]}:{upstream[1]}, "
          f"audit -> {log_path}", flush=True)
    await asyncio.Event().wait()


def main():
    ap = argparse.ArgumentParser(prog="dns_guard")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5353)
    ap.add_argument("--mode", choices=["monitor", "enforce"], default="monitor")
    ap.add_argument("--log", default=DEFAULT_LOG)
    ap.add_argument("--upstream", default="127.0.0.53:53")
    a = ap.parse_args()
    if a.host not in ("127.0.0.1", "::1", "localhost"):
        sys.exit("refusing to bind a non-loopback address: this is not an open resolver")
    uh, _, up = a.upstream.rpartition(":")
    asyncio.run(serve(a.host, a.port, a.mode, a.log, (uh, int(up))))


if __name__ == "__main__":
    main()
