#!/usr/bin/env python3
"""
reboot_ready: before you reboot a box that has been up for months, find out what
will not come back on its own.

A long-running server accumulates things that work only because nobody has
restarted it: a process started by hand in a terminal, a container with no
restart policy, a service that is running but was never enabled. Every one of
them is fine until the reboot, and then it is silently gone. This lists them.

Read-only. It changes nothing, restarts nothing, and never reboots.

Checks
  kernel      running kernel vs the newest installed one, reboot-required flag
  lifelines   ssh, tailscale, cron, docker enabled at boot (lose these and
              you cannot fix anything else remotely)
  services    every running system service: enabled (returns) or not
  containers  every running container: restart policy (none = gone)
  orphans     long-lived processes not owned by a service or container:
              started by hand in a login session, or launched by a cron job.
              They return only if a cron line (@reboot, or a periodic
              keepalive) names their script or working directory

Exit 0 if everything will come back, 1 if anything will not.
Usage: python3 reboot_ready.py [--min-age-hours 24] [--json]
"""

import argparse
import glob
import json
import os
import re
import subprocess
import sys

LIFELINES = ["ssh", "tailscaled", "cron", "docker"]


def sh(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception:
        return ""


def unit_enabled(unit):
    # 'enabled', 'static' (pulled in by something enabled), 'alias' and
    # 'enabled-runtime' come back; 'disabled' and friends do not.
    state = sh(["systemctl", "is-enabled", unit]) or "unknown"
    return state, state in ("enabled", "static", "alias", "indirect", "generated")


def check_kernel():
    running = os.uname().release
    installed = sorted(
        (os.path.basename(p)[len("vmlinuz-"):] for p in glob.glob("/boot/vmlinuz-*")),
        key=lambda v: [int(x) if x.isdigit() else x for x in re.split(r"[.-]", v)])
    newest = installed[-1] if installed else running
    pending = os.path.exists("/var/run/reboot-required")
    pkgs = []
    if os.path.exists("/var/run/reboot-required.pkgs"):
        pkgs = sorted(set(open("/var/run/reboot-required.pkgs").read().split()))
    return {"running": running, "newest_installed": newest,
            "behind": running != newest, "reboot_required": pending, "packages": pkgs}


def check_lifelines():
    out = []
    for name in LIFELINES:
        unit = name + ".service"
        ok, state = boot_path(unit)
        if state in ("", "unknown") or "No such file" in state:
            continue
        out.append({"unit": unit, "state": state, "returns": ok})
    return out


def boot_path(unit):
    """(returns, state) for a unit, allowing for socket activation and units
    that a systemd generator recreates at every boot (e.g. serial-getty)."""
    state, ok = unit_enabled(unit)
    if ok:
        return True, state
    sock = re.sub(r"(@[^.]*)?\.service$", ".socket", unit)
    if unit_enabled(sock)[1]:
        return True, f"{state}, but {sock} enabled (socket-activated)"
    if glob.glob(f"/run/systemd/generator*/*/{unit}"):
        return True, f"{state}, recreated at boot by a generator"
    return False, state


def check_services():
    raw = sh(["systemctl", "list-units", "--type=service", "--state=running",
              "--no-legend", "--plain"])
    out = []
    for ln in raw.splitlines():
        unit = ln.split()[0]
        ok, state = boot_path(unit)
        out.append({"unit": unit, "state": state, "returns": ok})
    return out


def check_containers():
    names = sh(["docker", "ps", "--format", "{{.Names}}"]).split()
    out = []
    for n in names:
        pol = sh(["docker", "inspect", "-f", "{{.HostConfig.RestartPolicy.Name}}", n]) or "unknown"
        out.append({"container": n, "restart_policy": pol,
                    "returns": pol in ("always", "unless-stopped", "on-failure")})
    return out


def cron_lines():
    """Every active cron line: @reboot starts a process at boot, and a periodic
    keepalive ('start it if it is not running') brings it back within minutes."""
    lines = [ln.strip() for ln in sh(["crontab", "-l"]).splitlines()
             if ln.strip() and not ln.strip().startswith("#")]
    for f in glob.glob("/etc/cron.d/*"):
        try:
            lines += [ln.strip() for ln in open(f) if ln.strip() and not ln.startswith("#")]
        except Exception:
            pass
    return lines


def classify_cgroup(cg):
    if "/docker-" in cg or "/docker/" in cg:
        return "container", None
    m = re.search(r"/session-[\w]+\.scope", cg)
    if m:
        return "session", None  # started by hand from a login shell
    m = re.search(r"user@\d+\.service/.*?([\w@.-]+\.service)", cg)
    if m:
        return "user-unit", m.group(1)
    if cg.endswith("/init.scope"):
        return "manager", None  # the systemd --user manager itself
    m = re.search(r"system\.slice/([\w@.\\-]+\.service)", cg)
    if m:
        if m.group(1) == "cron.service":
            return "cron", None  # launched by a cron job, not owned by a unit
        return "system-unit", m.group(1)
    m = re.search(r"([\w@.-]+\.scope)$", cg)
    return ("scope", m.group(1)) if m else ("other", None)


def check_orphans(min_age_s, cron):
    groups = {}
    hz = os.sysconf("SC_CLK_TCK")
    uptime = float(open("/proc/uptime").read().split()[0])
    for d in glob.glob("/proc/[0-9]*"):
        pid = int(os.path.basename(d))
        try:
            cg = open(f"{d}/cgroup").read().strip().split("::")[-1]
            stat = open(f"{d}/stat").read()
            cmd = open(f"{d}/cmdline", "rb").read().replace(b"\0", b" ").decode(errors="ignore").strip()
            uid = os.stat(d).st_uid
            cwd = os.readlink(f"{d}/cwd")
        except Exception:
            continue
        if not cmd or uid == 0:
            continue
        start_ticks = int(stat.rsplit(")", 1)[1].split()[19])
        age = uptime - start_ticks / hz
        if age < min_age_s:
            continue
        kind, unit = classify_cgroup(cg)
        if kind in ("system-unit", "container", "manager"):
            continue  # covered by the services / containers checks
        key = cg if kind != "cron" else f"{cg}:{cwd}:{cmd}"
        g = groups.setdefault(key, {"cgroup": cg, "kind": kind, "unit": unit, "cwd": cwd,
                                    "oldest_age_h": 0, "cmd": cmd, "pids": 0})
        g["pids"] += 1
        if age / 3600 > g["oldest_age_h"]:
            g["oldest_age_h"] = round(age / 3600, 1)
            g["cmd"] = cmd[:160]
    out = []
    for g in groups.values():
        if g["kind"] == "user-unit":
            state = sh(["systemctl", "--user", "is-enabled", g["unit"]])
            linger = os.path.exists(f"/var/lib/systemd/linger/{os.getenv('USER', '')}")
            g["returns"] = state == "enabled" and linger
            g["why"] = f"user unit {state or 'unknown'}, linger {'on' if linger else 'off'}"
        else:
            script = next((w for w in g["cmd"].split() if re.search(r"\.(py|sh|js|mjs)$", w)), "")
            needles = [n for n in (os.path.basename(script), g["cwd"]) if n and len(n) > 4
                       and n not in ("/", os.path.expanduser("~"))]
            hit = next((ln for ln in cron if any(n in ln for n in needles)), None)
            g["returns"] = bool(hit)
            if hit:
                g["why"] = ("started at boot by an @reboot cron line" if hit.startswith("@reboot")
                            else "kept alive by a periodic cron line")
            else:
                g["why"] = {"session": "started by hand in a login session",
                            "cron": "launched by a cron job that no longer starts it"}.get(
                                g["kind"], f"lives in a {g['kind']} scope") + ": will not return"
        out.append(g)
    return sorted(out, key=lambda g: (g["returns"], -g["oldest_age_h"]))


def main():
    ap = argparse.ArgumentParser(prog="reboot_ready")
    ap.add_argument("--min-age-hours", type=float, default=24)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    cron = cron_lines()
    r = {"kernel": check_kernel(), "lifelines": check_lifelines(),
         "services": check_services(), "containers": check_containers(),
         "orphans": check_orphans(a.min_age_hours * 3600, cron),
         "cron_reboot": [ln for ln in cron if ln.startswith("@reboot")]}
    bad = ([x for x in r["lifelines"] if not x["returns"]] +
           [x for x in r["services"] if not x["returns"]] +
           [x for x in r["containers"] if not x["returns"]] +
           [x for x in r["orphans"] if not x["returns"]])
    r["will_not_return"] = len(bad)
    if a.json:
        print(json.dumps(r, indent=1))
        return 1 if bad else 0

    k = r["kernel"]
    print(f"kernel      running {k['running']}, newest installed {k['newest_installed']}"
          f"{'  <- BEHIND' if k['behind'] else ''}; reboot-required: {k['reboot_required']}")
    print(f"lifelines   " + ", ".join(f"{x['unit']} {x['state']}" for x in r["lifelines"]))
    ok_s = sum(x["returns"] for x in r["services"])
    print(f"services    {ok_s}/{len(r['services'])} running services are enabled at boot")
    for x in r["services"]:
        if not x["returns"]:
            print(f"  WON'T RETURN  {x['unit']}  ({x['state']})")
    ok_c = sum(x["returns"] for x in r["containers"])
    print(f"containers  {ok_c}/{len(r['containers'])} running containers have a restart policy")
    for x in r["containers"]:
        if not x["returns"]:
            print(f"  WON'T RETURN  {x['container']}  (restart policy: {x['restart_policy']})")
    print(f"orphans     {len(r['orphans'])} long-lived process groups outside system services/containers")
    for g in r["orphans"]:
        tag = "returns      " if g["returns"] else "WON'T RETURN "
        print(f"  {tag} up {g['oldest_age_h']:>6}h  {g['cmd'][:90]}")
        print(f"                {g['why']}")
    print(f"\nverdict: {'SAFE, everything comes back' if not bad else f'{len(bad)} thing(s) will not come back after a reboot'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
