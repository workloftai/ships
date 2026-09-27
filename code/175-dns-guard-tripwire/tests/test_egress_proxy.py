#!/usr/bin/env python3
"""
End-to-end tests for egress_proxy: start real proxies (monitor + enforce) on
loopback, drive real traffic through them, then assert on responses AND on the
audit log. Needs outbound network. Run: python3 tests/test_egress_proxy.py
"""

import json
import os
import socket
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import egress_proxy as EP  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + (f"  ({detail})" if detail and not cond else ""))


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def start(mode, log):
    port = free_port()
    proc = subprocess.Popen([sys.executable, os.path.join(ROOT, "egress_proxy.py"), "serve",
                             "--mode", mode, "--port", str(port), "--log", log],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    for _ in range(50):
        try:
            socket.create_connection(("127.0.0.1", port), 0.2).close()
            return proc, port
        except OSError:
            time.sleep(0.1)
    raise RuntimeError("proxy did not start")


def fetch(port, url, loop="test", run="run1"):
    """GET url through the proxy. Returns HTTP status, or 'refused:<code>'."""
    proxy = f"http://{loop}:{run}@127.0.0.1:{port}"
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    try:
        return opener.open(url, timeout=20).status
    except urllib.error.HTTPError as e:
        return e.code
    except urllib.error.URLError as e:
        msg = str(e.reason)
        return "refused:403" if "403" in msg else f"error:{msg[:80]}"


def sni_mismatch(port, connect_host, sni_host):
    """CONNECT an allowed host, then offer TLS for a different one."""
    s = socket.create_connection(("127.0.0.1", port), 10)
    auth = __import__("base64").b64encode(b"test:sni").decode()
    s.sendall(f"CONNECT {connect_host}:443 HTTP/1.1\r\nHost: {connect_host}:443\r\n"
              f"Proxy-Authorization: Basic {auth}\r\n\r\n".encode())
    s.recv(4096)
    ctx = ssl.create_default_context()
    try:
        t = ctx.wrap_socket(s, server_hostname=sni_host)
        t.close()
        return "handshake_ok"
    except Exception as e:
        return f"killed:{type(e).__name__}"


def events(log):
    with open(log) as f:
        return [json.loads(ln) for ln in f]


def main():
    tmp = tempfile.mkdtemp()

    # --- unit: layered policy -------------------------------------------------
    check("platform allows anthropic", EP.decide("api.anthropic.com", 443, None)[0])
    check("platform refuses example.com", not EP.decide("example.com", 443, None)[0])
    check("port 22 refused even for allowed host", not EP.decide("github.com", 22, None)[0])
    check("denylist beats everything", not EP.decide("bit.ly", 443, None)[0])
    check("loop policy narrows: digest may reach telegram",
          EP.decide("api.telegram.org", 443, "research-digest")[0])
    check("loop policy narrows: digest may NOT reach github",
          not EP.decide("github.com", 443, "research-digest")[0])
    check("subdomain matching is suffix-safe (evilanthropic.com refused)",
          not EP.decide("evilanthropic.com", 443, None)[0])
    check("policy lint passes on shipped policies", EP.lint_policies() == [])

    # --- e2e: enforce ---------------------------------------------------------
    log = os.path.join(tmp, "enforce.ndjson")
    proc, port = start("enforce", log)
    try:
        st = fetch(port, "https://api.anthropic.com/")
        check("enforce: allowed host tunnels through", isinstance(st, int), st)
        st = fetch(port, "https://example.com/")
        check("enforce: off-list host gets 403", st in (403, "refused:403"), st)
        st = fetch(port, "https://github.com/", loop="research-digest", run="nightly-42")
        check("enforce: loop policy blocks platform-allowed host", st in (403, "refused:403"), st)
        st = fetch(port, "https://api.telegram.org/bot0/getMe", loop="research-digest", run="nightly-42")
        check("enforce: loop policy allows its own host", isinstance(st, int), st)
        res = sni_mismatch(port, "api.anthropic.com", "example.com")
        check("enforce: SNI != CONNECT host kills the tunnel", res.startswith("killed"), res)
        time.sleep(0.5)
    finally:
        proc.terminate()
        proc.wait()
    ev = events(log)
    blocks = [e for e in ev if e["decision"] == "block"]
    check("audit: 3 blocks recorded", len(blocks) == 3, [e["host"] for e in blocks])
    check("audit: correlation id carries the run id",
          any(e["corr"] == "nightly-42" and e["loop"] == "research-digest" for e in ev))
    check("audit: SNI mismatch logged with the real SNI",
          any(e.get("sni") == "example.com" and e["decision"] == "block" for e in ev))

    # --- e2e: monitor ---------------------------------------------------------
    log = os.path.join(tmp, "monitor.ndjson")
    proc, port = start("monitor", log)
    try:
        st = fetch(port, "https://example.com/")
        check("monitor: off-list host still works", st == 200, st)
        time.sleep(0.5)
    finally:
        proc.terminate()
        proc.wait()
    ev = events(log)
    check("monitor: logged as would_block",
          any(e["host"] == "example.com" and e["decision"] == "would_block" for e in ev))

    # --- safety ---------------------------------------------------------------
    r = subprocess.run([sys.executable, os.path.join(ROOT, "egress_proxy.py"), "serve",
                        "--host", "0.0.0.0"], capture_output=True, text=True, timeout=10)
    check("refuses to bind non-loopback (never an open proxy)",
          r.returncode != 0 and "refusing" in (r.stderr + r.stdout))

    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
