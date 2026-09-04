#!/usr/bin/env python3
"""
chain_check.py — make the AI-native SDLC artifact chain tamper-evident.

Anthropic's AI-native SDLC playbook builds the lifecycle around a chain of
committed artifacts: intent.md -> spec.md -> plan.md -> the diff. "Together,
the intent, the spec, the plan, the diff and the review findings are the audit
trail." The catch: nothing in the playbook checks that the trail is intact.
Nothing stops you editing intent.md after the spec is signed off. The record
then silently lies about what was actually approved.

This is a ~1 file fix. Each downstream artifact carries, in its front matter,
the SHA-256 of the body of its parent as it stood when the artifact was sealed
(signed off). chain_check.py recomputes those hashes and fails loudly if any
link no longer matches. Wire it as a blocking hook and an edit to an approved
upstream artifact snaps the chain before a PR can open.

No third-party dependencies. Python 3.8+.

Usage:
    chain_check.py            verify the chain in ./ (or --dir)
    chain_check.py --seal     stamp each artifact with its parent's current hash
                              (this is the sign-off action; a human runs it)
    chain_check.py --json     machine-readable result

Exit code: 0 if the chain is intact, 1 if any link is broken or missing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

# The chain, root first. Each artifact's parent is the one before it.
# Override with a .chain file (one filename per line) in the target dir.
DEFAULT_CHAIN = ["intent.md", "spec.md", "plan.md"]

FM_DELIM = "---"


def split_front_matter(text: str):
    """Return (front_matter_dict, body_str). Minimal key: value parser, no YAML dep."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != FM_DELIM:
        return {}, text
    fm = {}
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == FM_DELIM:
            end = i
            break
        raw = lines[i]
        if ":" in raw:
            key, _, val = raw.partition(":")
            fm[key.strip()] = val.strip()
    if end is None:
        # No closing delimiter: treat whole thing as body, no front matter.
        return {}, text
    body = "\n".join(lines[end + 1:])
    return fm, body


def body_sha256(text: str) -> str:
    """Hash the body only, so re-sealing (which edits front matter) is stable."""
    _, body = split_front_matter(text)
    # Normalise trailing whitespace so an editor adding a final newline is not
    # mistaken for tampering.
    normalised = body.strip("\n") + "\n"
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


def load_chain(dir_path: Path):
    chain_file = dir_path / ".chain"
    if chain_file.exists():
        names = [ln.strip() for ln in chain_file.read_text().splitlines()
                 if ln.strip() and not ln.strip().startswith("#")]
        return names or DEFAULT_CHAIN
    return DEFAULT_CHAIN


def check(dir_path: Path):
    """Return (ok: bool, results: list[dict])."""
    chain = load_chain(dir_path)
    results = []
    ok = True
    parent_name = None
    for name in chain:
        path = dir_path / name
        entry = {"artifact": name, "parent": parent_name, "status": "ok"}
        if not path.exists():
            # An absent later stage is not a failure: the chain may be mid-flight.
            # But an absent parent that a present child points at IS a failure,
            # caught below.
            entry["status"] = "absent"
            results.append(entry)
            parent_name = name
            continue
        if parent_name is None:
            # Root artifact: nothing upstream to verify.
            results.append(entry)
            parent_name = name
            continue

        fm, _ = split_front_matter(path.read_text())
        declared_parent = fm.get("parent")
        declared_hash = fm.get("parent_sha256")
        parent_path = dir_path / parent_name

        if declared_parent != parent_name:
            ok = False
            entry["status"] = "broken"
            entry["reason"] = (
                f"declares parent '{declared_parent}', expected '{parent_name}'")
        elif not declared_hash:
            ok = False
            entry["status"] = "broken"
            entry["reason"] = "no parent_sha256 (never sealed)"
        elif not parent_path.exists():
            ok = False
            entry["status"] = "broken"
            entry["reason"] = f"parent '{parent_name}' is missing"
        else:
            actual = body_sha256(parent_path.read_text())
            if actual != declared_hash:
                ok = False
                entry["status"] = "broken"
                entry["reason"] = (
                    f"parent '{parent_name}' changed since sign-off "
                    f"(sealed {declared_hash[:12]}, now {actual[:12]})")
        results.append(entry)
        parent_name = name
    return ok, results


def seal(dir_path: Path):
    """Stamp each present artifact with its parent's current body hash.

    This is the human sign-off action. You run it when you have reviewed the
    upstream artifact and accept its current state. After sealing, chain_check
    passes until someone edits an upstream artifact again.
    """
    chain = load_chain(dir_path)
    parent_name = None
    sealed = []
    for name in chain:
        path = dir_path / name
        if not path.exists():
            parent_name = name
            continue
        if parent_name is not None:
            parent_path = dir_path / parent_name
            if parent_path.exists():
                phash = body_sha256(parent_path.read_text())
                _stamp(path, parent_name, phash)
                sealed.append(name)
        parent_name = name
    return sealed


def _stamp(path: Path, parent_name: str, phash: str):
    text = path.read_text()
    fm, body = split_front_matter(text)
    fm["parent"] = parent_name
    fm["parent_sha256"] = phash
    # Preserve any other front-matter keys, write parent keys last for clarity.
    ordered = {k: v for k, v in fm.items() if k not in ("parent", "parent_sha256")}
    lines = [FM_DELIM]
    for k, v in ordered.items():
        lines.append(f"{k}: {v}")
    lines.append(f"parent: {parent_name}")
    lines.append(f"parent_sha256: {phash}")
    lines.append(FM_DELIM)
    lines.append(body.strip("\n"))
    path.write_text("\n".join(lines) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", default=".", help="directory holding the artifacts")
    ap.add_argument("--seal", action="store_true",
                    help="stamp each artifact with its parent's current hash (sign-off)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    dir_path = Path(args.dir)

    if args.seal:
        sealed = seal(dir_path)
        if args.json:
            print(json.dumps({"sealed": sealed}))
        else:
            for name in sealed:
                print(f"sealed  {name} -> parent hash stamped")
            if not sealed:
                print("nothing to seal")
        return 0

    ok, results = check(dir_path)
    if args.json:
        print(json.dumps({"ok": ok, "links": results}, indent=2))
    else:
        for r in results:
            mark = {"ok": "ok  ", "absent": "--  ", "broken": "SNAP"}[r["status"]]
            line = f"[{mark}] {r['artifact']}"
            if r.get("parent"):
                line += f"  (parent: {r['parent']})"
            if r.get("reason"):
                line += f"  <- {r['reason']}"
            print(line)
        print()
        print("chain intact" if ok else "CHAIN BROKEN: an approved artifact changed after sign-off")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
