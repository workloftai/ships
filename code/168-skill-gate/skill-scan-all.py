#!/usr/bin/env python3
"""
skill-scan-all.py -- run NVIDIA SkillSpector (static, offline, no secrets) over
every skill, plugin and agent-config file the fleet loads.

Targets
  user      every entry in ~/.claude/skills (dirs and single .md skills,
            including the synced bucket)
  plugin    every installed plugin root (from installed_plugins.json), whole
            tree, so hooks and MCP server code are covered too
  catalog   every skill dir / command .md in the plugin marketplaces that is
            NOT installed (would-be installs)
  config    the 116-ish agent-config files agent-config-scan.py inventories
            (AGENTS.md, CLAUDE.md, .claude hooks/settings, .mcp.json, ...),
            staged per repo root into a temp dir and scanned as one unit each

Every scan goes through skillspector-run.sh (env -i, unshare -rn, --no-llm).

Reviewed false positives live in skill-scan-reviewed.json, keyed by
"<target>|<rule id>|<file>|<line>". A HIGH/CRITICAL finding not in that file
is "unreviewed"; any unreviewed HIGH/CRITICAL makes the exit code 1.

Usage
  skill-scan-all.py                 full scan, summary to stdout, exit 1 on new high/crit
  skill-scan-all.py --json          machine-readable summary
  skill-scan-all.py --only user,plugin
  skill-scan-all.py --extra DIR     also scan each subdir of DIR (used for plants)
"""
import argparse
import concurrent.futures as cf
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HOME = "/home/workloft"
SEC = os.path.join(HOME, "security")
RUN = os.path.join(SEC, "skillspector-run.sh")
REPORTS = os.path.join(SEC, "skillspector-reports")
REVIEWED = os.path.join(SEC, "skill-scan-reviewed.json")
SKILLS = os.path.join(HOME, ".claude", "skills")
PLUGINS = os.path.join(HOME, ".claude", "plugins")
SEVS = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]


def user_targets():
    out = []
    for name in sorted(os.listdir(SKILLS)):
        p = os.path.join(SKILLS, name)
        if name.startswith("."):
            continue
        if name == "synced" and os.path.isdir(p):
            for bucket in sorted(os.listdir(p)):
                bp = os.path.join(p, bucket)
                if os.path.isdir(bp):
                    for s in sorted(os.listdir(bp)):
                        sp = os.path.join(bp, s)
                        if os.path.isdir(sp):
                            out.append(("user", f"synced/{s}", sp))
            continue
        if os.path.isdir(p) or name.endswith(".md"):
            out.append(("user", name, p))
    return out


def installed_plugin_roots():
    with open(os.path.join(PLUGINS, "installed_plugins.json")) as f:
        d = json.load(f)
    roots = []
    for key, v in d.get("plugins", d).items():
        for inst in v if isinstance(v, list) else [v]:
            p = inst.get("installPath")
            if p and os.path.isdir(p):
                roots.append((key, os.path.realpath(p)))
    return roots


def plugin_targets():
    return [("plugin", k, p) for k, p in installed_plugin_roots()]


def catalog_targets():
    installed = [p for _, p in installed_plugin_roots()]
    seen, out = set(), []
    base = os.path.join(PLUGINS, "marketplaces")
    for dp, dns, fns in os.walk(base):
        dns[:] = [d for d in dns if d not in (".git", "node_modules")]
        rp = os.path.realpath(dp)
        if any(rp == r or rp.startswith(r + os.sep) for r in installed):
            continue
        if "SKILL.md" in fns:
            out.append(("catalog", os.path.relpath(dp, base), dp))
            seen.add(rp)
        if os.path.basename(dp) == "commands":
            for fn in sorted(fns):
                if fn.endswith(".md"):
                    fp = os.path.join(dp, fn)
                    out.append(("catalog", os.path.relpath(fp, base), fp))
    return out


def config_targets(stage_root):
    spec = importlib.util.spec_from_file_location(
        "acs", os.path.join(SEC, "agent-config-scan.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    roots = m.fleet_roots()
    files = list(m.walk_candidates(roots))
    by_root = {}
    for f in files:
        owner = max((r for r in roots if f.startswith(r.rstrip("/") + "/")),
                    key=len, default=HOME)
        by_root.setdefault(owner, []).append(f)
    out = []
    for i, (root, fs) in enumerate(sorted(by_root.items())):
        d = os.path.join(stage_root, f"cfg{i:03d}")
        for f in fs:
            dst = os.path.join(d, os.path.relpath(f, root))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            try:
                shutil.copy2(f, dst)
            except OSError:
                pass
        label = os.path.relpath(root, HOME) if root != HOME else "~"
        out.append(("config", f"{label} ({len(fs)} files)", d))
    return out, len(files)


def is_vendored(rule, f):
    """SC9 (concealed executable) fires on every installed npm dependency and
    binary lockfile a plugin ships. Bucket those separately: they are the
    plugin's vendored deps, not the skill's own content."""
    f = f or ""
    return rule == "SC9" and ("node_modules/" in f or f.endswith(
        ("bun.lockb", "package-lock.json", "bun.lock")))


def scan(target):
    kind, label, path = target
    t0 = time.time()
    p = subprocess.run([RUN, "scan", path, "--format", "json"],
                       capture_output=True, text=True, timeout=600, cwd="/tmp")
    dt = time.time() - t0
    try:
        rep = json.loads(p.stdout)
    except json.JSONDecodeError:
        return {"kind": kind, "label": label, "path": path, "rc": p.returncode,
                "error": (p.stderr or p.stdout)[-400:], "secs": dt, "issues": []}
    issues = []
    for it in rep.get("issues", []):
        loc = it.get("location") or {}
        issues.append({"id": it.get("id"), "category": it.get("category"),
                       "severity": (it.get("severity") or "").upper(),
                       "confidence": it.get("confidence"),
                       "file": loc.get("file"), "line": loc.get("start_line"),
                       "pattern": it.get("pattern"),
                       "finding": (it.get("finding") or "")[:160],
                       "snippet": (it.get("code_snippet") or "")[:400],
                       "vendored": is_vendored(it.get("id"), loc.get("file")),
                       "message": (it.get("explanation") or "")[:200]})
    return {"kind": kind, "label": label, "path": path, "rc": p.returncode,
            "risk": rep.get("risk_assessment"), "secs": dt, "issues": issues}


def key(r, i):
    return f"{r['label']}|{i['id']}|{i['file']}|{i['line']}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--only", default="user,plugin,catalog,config")
    ap.add_argument("--extra", help="dir whose subdirs are scanned as kind=extra")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    kinds = set(args.only.split(","))
    os.makedirs(REPORTS, exist_ok=True)
    stage = tempfile.mkdtemp(prefix="skillscan-cfg-")
    t0 = time.time()
    targets, n_cfg_files = [], 0
    try:
        if "user" in kinds:
            targets += user_targets()
        if "plugin" in kinds:
            targets += plugin_targets()
        if "catalog" in kinds:
            targets += catalog_targets()
        if "config" in kinds:
            ct, n_cfg_files = config_targets(stage)
            targets += ct
        if args.extra:
            for s in sorted(os.listdir(args.extra)):
                targets.append(("extra", s, os.path.join(args.extra, s)))
        with cf.ThreadPoolExecutor(args.workers) as ex:
            results = list(ex.map(scan, targets))
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    wall = time.time() - t0

    reviewed = {}
    if os.path.exists(REVIEWED):
        with open(REVIEWED) as f:
            reviewed = json.load(f)
    by_sev = {s: 0 for s in SEVS}
    vendored = 0
    unreviewed, errors = [], []
    for r in results:
        if r.get("error"):
            errors.append(r)
        for i in r["issues"]:
            if i["vendored"]:
                vendored += 1
                continue
            by_sev[i["severity"]] = by_sev.get(i["severity"], 0) + 1
            if i["severity"] in ("HIGH", "CRITICAL") and key(r, i) not in reviewed:
                unreviewed.append({"target": f"{r['kind']}:{r['label']}",
                                   "path": r["path"], **i})
    summary = {"scanned_units": len(results),
               "by_kind": {k: sum(1 for r in results if r["kind"] == k)
                           for k in sorted({r["kind"] for r in results})},
               "config_files": n_cfg_files, "wall_secs": round(wall, 1),
               "findings_by_severity": by_sev,
               "vendored_dep_sc9_bucketed": vendored,
               "units_do_not_install": sum(1 for r in results if (r.get("risk") or {}).get("recommendation") == "DO_NOT_INSTALL"),
               "unreviewed_high_critical": unreviewed,
               "errors": [{"target": e["label"], "err": e["error"]} for e in errors]}
    stamp = time.strftime("%Y-%m-%d")
    with open(os.path.join(REPORTS, f"full-{stamp}.json"), "w") as f:
        json.dump({"summary": summary, "results": results}, f, indent=1)
    os.chmod(os.path.join(REPORTS, f"full-{stamp}.json"), 0o600)

    if args.json:
        print(json.dumps(summary, indent=1))
    else:
        print(f"skillspector: {summary['scanned_units']} units {summary['by_kind']} "
              f"in {summary['wall_secs']}s; findings {by_sev} (+{vendored} vendored-dep SC9); "
              f"errors {len(errors)}")
        for u in unreviewed:
            print(f"  UNREVIEWED {u['severity']} {u['id']} {u['target']} "
                  f"{u['file']}:{u['line']} {u['message'][:100]}")
    return 1 if unreviewed else 0


if __name__ == "__main__":
    sys.exit(main())
