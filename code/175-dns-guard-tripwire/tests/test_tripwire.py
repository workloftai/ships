#!/usr/bin/env python3
"""
Kill-switch tests: does the stop actually stop? Start a real proxy, run a
simulated runaway loop under egress-run, and assert it is dead, that its
children are dead, how long it took, and that the evidence landed in the audit
log. Needs outbound network for the allowed-host check.
Run: python3 tests/test_tripwire.py
"""

import json
import os
import socket
import subprocess
import sys
import tempfile
import textwrap
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RUN = os.path.join(ROOT, "egress-run")

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


def start_proxy(mode, log):
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


def script(tmp, name, body):
    path = os.path.join(tmp, name)
    with open(path, "w") as f:
        f.write(textwrap.dedent(body))
    return path


# A runaway: spawns a long-lived child (to prove the whole group dies), then
# hammers an off-list host forever, like an agent probing for a way out.
RUNAWAY = """
import os, subprocess, sys, time, urllib.request
child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(600)"])
open(sys.argv[1], "w").write(str(child.pid))
open(sys.argv[2], "w").write(str(time.time()))
while True:
    try:
        urllib.request.urlopen("https://example.com/", timeout=5)
    except Exception:
        pass
    time.sleep(0.2)
"""

# Same, but ignores SIGTERM, so only SIGKILL will do.
STUBBORN = """
import signal, sys, time, urllib.request
signal.signal(signal.SIGTERM, signal.SIG_IGN)
while True:
    try:
        urllib.request.urlopen("https://example.com/", timeout=5)
    except Exception:
        pass
    time.sleep(0.2)
"""

# Well behaved: two off-list hits, one allowed hit, then exits 0.
POLITE = """
import urllib.request
for u in ("https://example.com/", "https://example.org/", "https://api.anthropic.com/"):
    try:
        urllib.request.urlopen(u, timeout=10)
    except Exception:
        pass
"""


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    # a zombie still answers kill(0); treat it as dead
    try:
        with open(f"/proc/{pid}/stat") as f:
            return f.read().split()[2] != "Z"
    except FileNotFoundError:
        return False


def run(port, log, loop, args, timeout=60, extra_env=None):
    env = dict(os.environ, EGRESS_PROXY_PORT=str(port), EGRESS_LOG=log, **(extra_env or {}))
    t0 = time.time()
    r = subprocess.run([RUN, loop] + args, env=env, capture_output=True, text=True, timeout=timeout)
    return r, time.time() - t0


def events(log):
    with open(log) as f:
        return [json.loads(ln) for ln in f]


def main():
    tmp = tempfile.mkdtemp()
    runaway, stubborn, polite = (script(tmp, n, b) for n, b in
                                 (("runaway.py", RUNAWAY), ("stubborn.py", STUBBORN), ("polite.py", POLITE)))

    # --- fail closed ----------------------------------------------------------
    marker = os.path.join(tmp, "ran")
    r, _ = run(free_port(), os.path.join(tmp, "none.ndjson"), "t",
               ["--", "sh", "-c", f"touch {marker}"])
    check("fail closed: proxy down means the command never runs",
          r.returncode != 0 and not os.path.exists(marker) and "refusing" in r.stderr, r.stderr)

    log = os.path.join(tmp, "enforce.ndjson")
    proxy, port = start_proxy("enforce", log)
    try:
        # --- the runaway is stopped, with its children ------------------------
        pidf, t0f = os.path.join(tmp, "child.pid"), os.path.join(tmp, "t0")
        alert_out = os.path.join(tmp, "alert.json")
        r, secs = run(port, log, "runaway", ["--grace", "2", "--", sys.executable, runaway, pidf, t0f],
                      extra_env={"EGRESS_ALERT_CMD": f"cat > {alert_out}"})
        check("runaway: killed, exit 137", r.returncode == 137, (r.returncode, r.stderr[-300:]))
        check("runaway: dead within 5s of starting", secs < 5, f"{secs:.2f}s")
        time.sleep(0.3)
        child = int(open(pidf).read())
        check("runaway: its child process is dead too (whole group killed)", not alive(child))
        ev = events(log)
        killed = [e for e in ev if e["decision"] == "killed"]
        check("audit: one killed event with a reason", len(killed) == 1 and "example.com" in killed[0]["reason"],
              killed)
        corr = killed[0]["corr"] if killed else None
        check("audit: killed event shares the run id with the block that tripped it",
              any(e["decision"] == "block" and e["corr"] == corr for e in ev))
        check("audit: SIGTERM was enough for a well-behaved process",
              killed and killed[0]["signal"] == "SIGTERM", killed)
        check("alert command ran with the event on stdin",
              os.path.exists(alert_out) and json.load(open(alert_out)).get("decision") == "killed")

        # --- SIGTERM ignored: SIGKILL after grace -----------------------------
        r, secs = run(port, log, "stubborn", ["--grace", "1", "--", sys.executable, stubborn])
        killed = [e for e in events(log) if e["decision"] == "killed" and e["loop"] == "stubborn"]
        check("stubborn: escalates to SIGKILL after the grace period",
              r.returncode == 137 and killed and killed[0]["signal"] == "SIGKILL", killed)

        # --- threshold --------------------------------------------------------
        r, _ = run(port, log, "polite", ["--trip", "3", "--", sys.executable, polite])
        check("threshold: 2 blocks under --trip 3 does not kill", r.returncode == 0, (r.returncode, r.stderr))
        r, _ = run(port, log, "polite", ["--trip", "2", "--", sys.executable, polite])
        check("threshold: 2 blocks under --trip 2 does kill", r.returncode == 137, r.returncode)
    finally:
        proxy.terminate()
        proxy.wait()

    # --- monitor never kills --------------------------------------------------
    log = os.path.join(tmp, "monitor.ndjson")
    proxy, port = start_proxy("monitor", log)
    try:
        r, _ = run(port, log, "polite", ["--", sys.executable, polite])
        check("monitor: off-list traffic logged, run left alone", r.returncode == 0, r.returncode)
        check("monitor: no killed event", not any(e["decision"] == "killed" for e in events(log)))
    finally:
        proxy.terminate()
        proxy.wait()

    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
