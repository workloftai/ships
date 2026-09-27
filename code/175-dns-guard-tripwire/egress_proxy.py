#!/usr/bin/env python3
"""
egress_proxy: phase two of egress_guard. A hostname-allowlisting forward proxy
for agent loops, with layered policy and an NDJSON audit trail.

Phase one gave us an evidence-derived allowlist and an unarmed nftables ruleset.
Its honest limit: a layer-three firewall allowlists by resolved IP, and CDN IPs
drift and are shared between unrelated sites. The fix is to filter by NAME, at a
proxy, which is the design Forge (github.com/initializ/forge) uses for its
agents. This borrows three ideas from it, not the runtime:

  1. Egress allowlist by hostname, enforced at a proxy the agent is pointed at.
  2. Layered policy. The platform allowlist (allowlist.py) is the outer bound.
     A loop's own policy file can only NARROW it. A loop that asks for a host
     the platform does not allow is refused, and the attempt is logged.
  3. Structured NDJSON audit with a correlation id on every connection, so you
     can answer "what did last night's run of loop X reach?" with one grep.

Plus one check of our own: for HTTPS, the proxy reads the TLS ClientHello and
refuses the tunnel if the server name inside it differs from the host in the
CONNECT line. That closes the cheapest bypass (CONNECT an allowed host, then
speak TLS to a different one).

Opt-in and reversible by design. Nothing box-wide changes. A loop opts in by
setting HTTPS_PROXY / HTTP_PROXY, and names itself in the proxy credentials:

    HTTPS_PROXY=http://<loop>:<run-id>@127.0.0.1:8899

Modes:
  monitor  allow everything, log what enforce WOULD have blocked (default).
  enforce  refuse anything off policy with a 403.

Commands:
  serve    run the proxy
  report   summarise the audit log: per loop, what was reached, what was
           (or would have been) blocked

Stdlib only.
"""

import argparse
import asyncio
import base64
import json
import os
import sys
import time
import uuid
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import allowlist as AL  # noqa: E402

POLICY_DIR = os.path.join(HERE, "policies")
DEFAULT_LOG = os.path.join(HERE, "logs", "egress-audit.ndjson")
ALLOWED_PORTS = {80, 443}


# ---------------------------------------------------------------- policy ---

def _match(host, base):
    return host == base or host.endswith("." + base)


def load_loop_policy(loop):
    """Return (categories, domains) the loop asked for, or None for no file."""
    if not loop:
        return None
    safe = "".join(c for c in loop if c.isalnum() or c in "-_")
    path = os.path.join(POLICY_DIR, safe + ".json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        p = json.load(f)
    return set(p.get("categories", [])), [d.lower() for d in p.get("domains", [])]


def decide(host, port, loop):
    """Layered decision. Returns (allowed: bool, reason: str)."""
    host = (host or "").strip().lower().rstrip(".")
    if port not in ALLOWED_PORTS:
        return False, f"port {port} not allowed"
    for base, why in AL.DENYLIST_NOTES.items():
        if _match(host, base):
            return False, f"denylisted: {why}"
    platform_cat = next((cat for cat, entries in AL.ALLOWLIST.items()
                         if any(_match(host, d) for d, _ in entries)), None)
    if platform_cat is None:
        return False, "not on platform allowlist"
    pol = load_loop_policy(loop)
    if pol is None:
        return True, f"platform:{platform_cat}"
    cats, domains = pol
    if platform_cat in cats:
        return True, f"loop:{platform_cat}"
    if any(_match(host, d) for d in domains):
        return True, "loop:domain"
    return False, f"outside loop policy (platform allows via {platform_cat})"


def lint_policies():
    """A loop policy may only narrow the platform. Flag anything that widens."""
    problems = []
    if not os.path.isdir(POLICY_DIR):
        return problems
    for fn in sorted(os.listdir(POLICY_DIR)):
        if not fn.endswith(".json"):
            continue
        with open(os.path.join(POLICY_DIR, fn)) as f:
            p = json.load(f)
        for c in p.get("categories", []):
            if c not in AL.ALLOWLIST:
                problems.append(f"{fn}: unknown category '{c}'")
        for d in p.get("domains", []):
            if not AL.is_allowed(d):
                problems.append(f"{fn}: '{d}' widens past the platform allowlist")
    return problems


# ---------------------------------------------------------------- TLS SNI ---

def parse_sni(data):
    """Pull the server_name out of a TLS ClientHello. None if absent/unparseable."""
    try:
        if len(data) < 5 or data[0] != 0x16:
            return None
        p = 5
        if data[p] != 0x01:  # handshake type: ClientHello
            return None
        p += 4 + 2 + 32  # hs header, client_version, random
        p += 1 + data[p]  # session id
        p += 2 + int.from_bytes(data[p:p + 2], "big")  # cipher suites
        p += 1 + data[p]  # compression methods
        end = p + 2 + int.from_bytes(data[p:p + 2], "big")
        p += 2
        while p + 4 <= end:
            etype = int.from_bytes(data[p:p + 2], "big")
            elen = int.from_bytes(data[p + 2:p + 4], "big")
            p += 4
            if etype == 0:  # server_name
                q = p + 2
                if data[q] == 0:
                    nlen = int.from_bytes(data[q + 1:q + 3], "big")
                    return data[q + 3:q + 3 + nlen].decode("ascii").lower()
            p += elen
    except Exception:
        return None
    return None


# ---------------------------------------------------------------- proxy ----

class Proxy:
    def __init__(self, mode, log_path):
        self.mode = mode
        self.log_path = log_path
        os.makedirs(os.path.dirname(log_path), exist_ok=True)

    def audit(self, **ev):
        ev = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "mode": self.mode, **ev}
        with open(self.log_path, "a") as f:
            f.write(json.dumps(ev) + "\n")

    @staticmethod
    def identity(headers):
        """loop + run id from Proxy-Authorization: Basic base64(loop:run)."""
        auth = headers.get("proxy-authorization", "")
        if auth.lower().startswith("basic "):
            try:
                user, _, run = base64.b64decode(auth[6:]).decode().partition(":")
                return user or None, run or None
            except Exception:
                pass
        return None, None

    async def handle(self, reader, writer):
        conn_id = uuid.uuid4().hex[:12]
        started = time.time()
        try:
            head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 15)
        except Exception:
            writer.close()
            return
        lines = head.decode("latin-1").split("\r\n")
        method, target, _ver = (lines[0].split(" ") + ["", "", ""])[:3]
        headers = {}
        for ln in lines[1:]:
            if ":" in ln:
                k, v = ln.split(":", 1)
                headers[k.strip().lower()] = v.strip()
        loop, run = self.identity(headers)
        corr = run or conn_id

        if method.upper() == "CONNECT":
            host, _, port = target.rpartition(":")
            port = int(port or 443)
        else:  # plain HTTP with an absolute URI
            rest = target.split("://", 1)[-1]
            hostport = rest.split("/", 1)[0]
            host, _, p = hostport.partition(":")
            port = int(p or 80)
        host = host.strip("[]").lower()

        allowed, reason = decide(host, port, loop)
        base = dict(corr=corr, conn=conn_id, loop=loop or "unnamed", method=method.upper(),
                    host=host, port=port, reason=reason)

        if not allowed and self.mode == "enforce":
            self.audit(decision="block", **base)
            writer.write(b"HTTP/1.1 403 Forbidden\r\nX-Egress-Reason: " +
                         reason.encode("latin-1", "replace") +
                         b"\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
            await writer.drain()
            writer.close()
            return
        decision = "allow" if allowed else "would_block"

        try:
            up_r, up_w = await asyncio.wait_for(asyncio.open_connection(host, port), 15)
        except Exception as e:
            self.audit(decision="upstream_error", error=str(e)[:200], **base)
            writer.write(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n")
            await writer.drain()
            writer.close()
            return

        sni = None
        if method.upper() == "CONNECT":
            writer.write(b"HTTP/1.1 200 Connection established\r\n\r\n")
            await writer.drain()
            try:
                first = await asyncio.wait_for(reader.read(16384), 15)
            except Exception:
                first = b""
            sni = parse_sni(first)
            if sni and sni != host and not _match(sni, host):
                base["reason"] = f"SNI '{sni}' != CONNECT host '{host}'"
                if self.mode == "enforce":
                    self.audit(decision="block", sni=sni, **base)
                    up_w.close()
                    writer.close()
                    return
                decision = "would_block"
            up_w.write(first)
        else:
            # re-send the request with an origin-form target, drop proxy auth
            path = "/" + target.split("://", 1)[-1].partition("/")[2]
            fwd = [f"{method} {path} {_ver}"] + [ln for ln in lines[1:]
                                                 if ln and not ln.lower().startswith("proxy-")]
            up_w.write(("\r\n".join(fwd) + "\r\n\r\n").encode("latin-1"))

        counts = {"up": 0, "down": 0}

        async def pipe(src, dst, key):
            try:
                while True:
                    buf = await src.read(65536)
                    if not buf:
                        break
                    counts[key] += len(buf)
                    dst.write(buf)
                    await dst.drain()
            except Exception:
                pass
            finally:
                try:
                    dst.close()
                except Exception:
                    pass

        await asyncio.gather(pipe(reader, up_w, "up"), pipe(up_r, writer, "down"))
        self.audit(decision=decision, sni=sni, bytes_up=counts["up"], bytes_down=counts["down"],
                   secs=round(time.time() - started, 2), **base)


async def serve(host, port, mode, log_path):
    proxy = Proxy(mode, log_path)
    server = await asyncio.start_server(proxy.handle, host, port)
    print(f"egress_proxy {mode} on {host}:{port}, audit -> {log_path}", flush=True)
    async with server:
        await server.serve_forever()


# ---------------------------------------------------------------- report ---

def report(log_path, since=None):
    per = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    total = 0
    with open(log_path) as f:
        for ln in f:
            ev = json.loads(ln)
            if since and ev["ts"] < since:
                continue
            total += 1
            per[ev["loop"]][ev["decision"]][ev["host"]] += 1
    print(f"egress report: {total} connections in {log_path}\n")
    blocked_any = False
    for loop in sorted(per):
        d = per[loop]
        n = sum(sum(h.values()) for h in d.values())
        print(f"[{loop}] {n} connections")
        for dec in ("allow", "would_block", "block", "upstream_error"):
            if dec in d:
                hosts = ", ".join(f"{h} x{c}" for h, c in sorted(d[dec].items()))
                print(f"  {dec:14} {hosts}")
                blocked_any |= dec in ("would_block", "block")
        print()
    print("verdict:", "something was (or would have been) blocked, review above"
          if blocked_any else "every connection was on policy")
    return 1 if blocked_any else 0


def main():
    ap = argparse.ArgumentParser(prog="egress_proxy")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8899)
    s.add_argument("--mode", choices=["monitor", "enforce"], default="monitor")
    s.add_argument("--log", default=DEFAULT_LOG)
    r = sub.add_parser("report")
    r.add_argument("--log", default=DEFAULT_LOG)
    r.add_argument("--since", default=None, help="ISO timestamp lower bound")
    sub.add_parser("lint")
    a = ap.parse_args()
    if a.cmd == "serve":
        if a.host not in ("127.0.0.1", "::1", "localhost"):
            sys.exit("refusing to bind a non-loopback address: this is not an open proxy")
        problems = lint_policies()
        if problems:
            sys.exit("policy lint failed:\n  " + "\n  ".join(problems))
        asyncio.run(serve(a.host, a.port, a.mode, a.log))
    elif a.cmd == "report":
        sys.exit(report(a.log, a.since))
    elif a.cmd == "lint":
        problems = lint_policies()
        print("\n".join(problems) or "policies OK: every loop policy narrows the platform")
        sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
