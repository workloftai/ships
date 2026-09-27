#!/usr/bin/env python3
"""
tripwire: the kill switch for an egress-guarded loop run.

    tripwire.py <loop> [--trip N] [--grace S] -- <command...>

Why. Detection without a stop is a log. In OpenAI's September 2026 sandbox
escape the monitoring flagged the agent within about a quarter of an hour, a
person acknowledged it three minutes later, and the automatic stop that should
have ended the run did not fire. It ran for another two and a half hours.

So this makes the stop the same process as the run:

  1. Refuses to start the command if the egress proxy is not listening. A run
     that cannot be watched does not run (fail closed, not open).
  2. Starts the command in its own process group, pointed at the proxy with a
     fresh run id, exactly like the old egress-run.
  3. Tails the proxy's audit log for events carrying THIS run id. When the
     count of `block` events reaches N (default 1), it sends SIGTERM to the
     whole process group, waits `--grace` seconds, then SIGKILL. Children,
     grandchildren and anything else in the group go too.
  4. Writes a `killed` event to the same audit log with the reason and the
     seconds from trip to dead, and runs $EGRESS_ALERT_CMD if set (the event
     JSON is on its stdin), so a human hears about it after, not instead.
  5. If the watcher itself dies, the run is killed. Same rule as 1.

Only `block` trips it, which only happens with the proxy in enforce mode. In
monitor mode nothing is ever killed: that mode exists to learn what a loop
really reaches before anyone turns enforcement on.

Stdlib only.
"""

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LOG = os.path.join(HERE, "logs", "egress-audit.ndjson")


def audit(log, **ev):
    ev = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **ev}
    with open(log, "a") as f:
        f.write(json.dumps(ev) + "\n")
    return ev


def kill_group(pgid, grace):
    """SIGTERM the group, then SIGKILL after grace. Returns the signal that ended it."""
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return "already_gone"
    deadline = time.time() + grace
    while time.time() < deadline:
        try:
            os.killpg(pgid, 0)
        except ProcessLookupError:
            return "SIGTERM"
        time.sleep(0.05)
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        return "SIGTERM"
    return "SIGKILL"


def main():
    argv = sys.argv[1:]
    if "--" not in argv:
        sys.exit("usage: tripwire.py <loop> [--trip N] [--grace S] -- <command...>")
    i = argv.index("--")
    ap = argparse.ArgumentParser(prog="tripwire")
    ap.add_argument("loop")
    ap.add_argument("--trip", type=int, default=1, help="blocks before the run is killed")
    ap.add_argument("--grace", type=float, default=5.0, help="seconds between SIGTERM and SIGKILL")
    ap.add_argument("--log", default=os.environ.get("EGRESS_LOG", DEFAULT_LOG))
    ap.add_argument("--port", type=int, default=int(os.environ.get("EGRESS_PROXY_PORT", 8899)))
    a = ap.parse_args(argv[:i])
    cmd = argv[i + 1:]
    if not cmd:
        sys.exit("tripwire: no command given")

    # 1. fail closed: no proxy, no run
    try:
        socket.create_connection(("127.0.0.1", a.port), 2).close()
    except OSError:
        sys.exit(f"tripwire: egress proxy not listening on 127.0.0.1:{a.port}; refusing to run unguarded")

    run = f"{a.loop}-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{os.getpid()}"
    proxy = f"http://{a.loop}:{run}@127.0.0.1:{a.port}"
    env = dict(os.environ, HTTPS_PROXY=proxy, HTTP_PROXY=proxy, https_proxy=proxy,
               http_proxy=proxy, NO_PROXY="localhost,127.0.0.1,::1",
               no_proxy="localhost,127.0.0.1,::1", EGRESS_RUN_ID=run)
    os.makedirs(os.path.dirname(a.log), exist_ok=True)
    open(a.log, "a").close()
    start_offset = os.path.getsize(a.log)
    print(f"tripwire: loop={a.loop} run={run} trip={a.trip}", file=sys.stderr, flush=True)

    # 2. own process group, so a kill reaches everything the run spawned
    child = subprocess.Popen(cmd, env=env, start_new_session=True)
    pgid = child.pid
    tripped = {}

    # 3. watch the audit log for this run's blocks
    def watch():
        blocks = []
        try:
            with open(a.log) as f:
                f.seek(start_offset)
                while child.poll() is None:
                    ln = f.readline()
                    if not ln:
                        time.sleep(0.05)
                        continue
                    try:
                        ev = json.loads(ln)
                    except ValueError:
                        continue
                    if ev.get("corr") == run and ev.get("decision") == "block":
                        blocks.append(f"{ev.get('host')}:{ev.get('port')} ({ev.get('reason')})")
                        if len(blocks) >= a.trip:
                            tripped["reason"] = f"{len(blocks)} blocked: " + "; ".join(blocks)
                            break
        except Exception as e:  # 5. a dead watcher means a dead run
            tripped["reason"] = f"watcher failed: {type(e).__name__}: {e}"
        if tripped and child.poll() is None:
            t0 = time.time()
            tripped["signal"] = kill_group(pgid, a.grace)
            tripped["secs_to_dead"] = round(time.time() - t0, 2)

    w = threading.Thread(target=watch, daemon=True)
    w.start()
    rc = child.wait()
    w.join(a.grace + 2)

    if tripped:
        # 4. record it where the rest of the evidence lives, then tell a human
        ev = audit(a.log, decision="killed", corr=run, loop=a.loop, reason=tripped["reason"],
                   signal=tripped.get("signal"), secs_to_dead=tripped.get("secs_to_dead"))
        print(f"tripwire: KILLED run {run}: {tripped['reason']}", file=sys.stderr, flush=True)
        alert = os.environ.get("EGRESS_ALERT_CMD")
        if alert:
            try:
                subprocess.run(alert, shell=True, input=json.dumps(ev), text=True, timeout=30)
            except Exception as e:
                print(f"tripwire: alert command failed: {e}", file=sys.stderr)
        sys.exit(137)
    sys.exit(rc)


if __name__ == "__main__":
    main()
