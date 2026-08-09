#!/usr/bin/env python3
"""
skills_to_plugin — package a folder of Agent Skills into an Agent Plugins 1.0.0
plugin, and validate any plugin against the 1.0.0 schemas.

Agent Plugins 1.0.0 (agent-plugins.org, published 6 Aug 2026) is a vendor-neutral
format for shipping one plugin across agent clients (Copilot, VS Code, Cursor,
Codex, Kiro and anything else that implements it). A plugin is just a directory:

    my-plugin/
    |- plugin.json          # $schema + name (+ optional metadata)
    |- skills/              # one sub-dir per skill, each with a SKILL.md
    |- mcp.json             # optional: stdio / streamable-http / sse servers

Skills follow the Agent Skills spec (SKILL.md with `name` + `description`
frontmatter) — the same format Claude Code skills already use, which is the whole
point: the skills you already wrote are portable, you just have to package them.

No third-party dependencies. Pure standard library, so it runs anywhere Python 3
does. The validator implements the 1.0.0 rules directly rather than pulling a
JSON-Schema engine, so what it checks is auditable in one file.

Usage:
    python3 skills_to_plugin.py build  --skills DIR --name NAME --out DIR [opts]
    python3 skills_to_plugin.py validate PACKAGE_DIR
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

# --- Agent Plugins 1.0.0 constants (from the published schemas) ---------------

PLUGIN_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
MCP_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"

# name: 1-64 chars, lowercase alnum/./-, no leading/trailing sep, no -- or ..
NAME_RE = re.compile(r"^(?!.*(?:--|\.\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")

# the only permitted top-level keys in plugin.json (additionalProperties: false)
PLUGIN_KEYS = {
    "$schema", "name", "version", "description", "author",
    "homepage", "repository", "license", "keywords", "extensions",
}
AUTHOR_KEYS = {"name", "email", "url"}

# mcp.json transports and their required fields
MCP_TRANSPORTS = {
    "stdio": {"command"},
    "streamable-http": {"url"},
    "sse": {"url"},
}


# --- tiny frontmatter reader (no PyYAML dependency) ---------------------------

def read_frontmatter(skill_md: Path) -> dict:
    """Parse the leading --- fenced block of a SKILL.md into a flat dict.

    Handles the simple `key: value` lines Agent Skills use. Values may be quoted.
    Deliberately minimal: enough to lint name/description, not a full YAML parser.
    """
    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    body = text[3:end]
    out: dict[str, str] = {}
    for line in body.splitlines():
        line = line.rstrip()
        if not line or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        out[key] = val
    return out


# --- validation ---------------------------------------------------------------

def _load_json(path: Path, problems: list) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as e:
        problems.append(f"{path.name}: not valid JSON ({e})")
        return None


def validate_plugin_json(root: Path, problems: list) -> None:
    path = root / "plugin.json"
    data = _load_json(path, problems)
    if data is None:
        if not path.exists():
            problems.append("plugin.json: missing (required)")
        return
    if not isinstance(data, dict):
        problems.append("plugin.json: must be a JSON object")
        return

    extra = set(data) - PLUGIN_KEYS
    if extra:
        problems.append(f"plugin.json: unknown top-level keys {sorted(extra)}")

    if data.get("$schema") != PLUGIN_SCHEMA:
        problems.append(f"plugin.json: $schema must be '{PLUGIN_SCHEMA}'")

    name = data.get("name")
    if not isinstance(name, str) or not name:
        problems.append("plugin.json: 'name' is required and must be a string")
    else:
        if len(name) > 64:
            problems.append("plugin.json: 'name' exceeds 64 characters")
        if not NAME_RE.match(name):
            problems.append(
                f"plugin.json: 'name' {name!r} must be lowercase alphanumeric "
                "with . or - separators, no leading/trailing separator, no -- or .."
            )

    author = data.get("author")
    if author is not None:
        if not isinstance(author, dict):
            problems.append("plugin.json: 'author' must be an object")
        else:
            bad = set(author) - AUTHOR_KEYS
            if bad:
                problems.append(f"plugin.json: author has unknown keys {sorted(bad)}")

    for field in ("version", "description", "homepage", "repository", "license"):
        if field in data and not isinstance(data[field], str):
            problems.append(f"plugin.json: '{field}' must be a string")
    if "keywords" in data and not (
        isinstance(data["keywords"], list)
        and all(isinstance(k, str) for k in data["keywords"])
    ):
        problems.append("plugin.json: 'keywords' must be an array of strings")


def validate_skills(root: Path, problems: list) -> int:
    """Discover skills (immediate child dirs of skills/ with a SKILL.md) and
    lint each for the Agent Skills name/description frontmatter. Returns count."""
    skills_dir = root / "skills"
    if not skills_dir.is_dir():
        return 0
    count = 0
    for child in sorted(skills_dir.iterdir()):
        if not child.is_dir():
            continue
        skill_md = child / "SKILL.md"
        if not skill_md.is_file():
            problems.append(f"skills/{child.name}: no SKILL.md (not a valid skill)")
            continue
        count += 1
        fm = read_frontmatter(skill_md)
        if not fm.get("name"):
            problems.append(f"skills/{child.name}/SKILL.md: frontmatter missing 'name'")
        if not fm.get("description"):
            problems.append(
                f"skills/{child.name}/SKILL.md: frontmatter missing 'description'"
            )
    return count


def validate_mcp_json(root: Path, problems: list) -> None:
    path = root / "mcp.json"
    if not path.exists():
        return  # mcp.json is optional
    data = _load_json(path, problems)
    if data is None:
        return
    if data.get("$schema") != MCP_SCHEMA:
        problems.append(f"mcp.json: $schema must be '{MCP_SCHEMA}'")
    servers = data.get("mcpServers")
    if not isinstance(servers, dict):
        problems.append("mcp.json: 'mcpServers' must be an object")
        return
    for sid, cfg in servers.items():
        if not isinstance(cfg, dict):
            problems.append(f"mcp.json: server '{sid}' must be an object")
            continue
        ttype = cfg.get("type")
        if ttype not in MCP_TRANSPORTS:
            problems.append(
                f"mcp.json: server '{sid}' has invalid type {ttype!r} "
                f"(expected one of {sorted(MCP_TRANSPORTS)})"
            )
            continue
        for req in MCP_TRANSPORTS[ttype]:
            if not cfg.get(req):
                problems.append(f"mcp.json: server '{sid}' ({ttype}) requires '{req}'")
        url = cfg.get("url")
        if ttype in ("streamable-http", "sse") and isinstance(url, str):
            is_local = url.startswith("http://localhost") or url.startswith("http://127.")
            if not url.startswith("https://") and not is_local:
                problems.append(
                    f"mcp.json: server '{sid}' url must be https (http only for localhost)"
                )


def validate(root: Path) -> list:
    problems: list = []
    if not root.is_dir():
        return [f"{root}: not a directory"]
    validate_plugin_json(root, problems)
    n = validate_skills(root, problems)
    validate_mcp_json(root, problems)
    if n == 0 and not (root / "mcp.json").exists():
        problems.append("plugin has neither skills nor an mcp.json (nothing to load)")
    return problems


# --- build --------------------------------------------------------------------

def build(args) -> int:
    src = Path(args.skills)
    out = Path(args.out)
    if not src.is_dir():
        print(f"error: --skills {src} is not a directory", file=sys.stderr)
        return 2

    skills = [
        d for d in sorted(src.iterdir())
        if d.is_dir() and (d / "SKILL.md").is_file()
    ]
    if not skills and not args.mcp:
        print("error: no skills found and no --mcp given; nothing to package",
              file=sys.stderr)
        return 2

    out.mkdir(parents=True, exist_ok=True)
    # skills/
    dst_skills = out / "skills"
    if dst_skills.exists():
        shutil.rmtree(dst_skills)
    dst_skills.mkdir(parents=True)
    for d in skills:
        shutil.copytree(d, dst_skills / d.name)

    # plugin.json
    manifest: dict = {"$schema": PLUGIN_SCHEMA, "name": args.name}
    if args.version:
        manifest["version"] = args.version
    if args.description:
        manifest["description"] = args.description
    author = {}
    if args.author_name:
        author["name"] = args.author_name
    if args.author_email:
        author["email"] = args.author_email
    if args.author_url:
        author["url"] = args.author_url
    if author:
        manifest["author"] = author
    if args.homepage:
        manifest["homepage"] = args.homepage
    if args.repository:
        manifest["repository"] = args.repository
    if args.license:
        manifest["license"] = args.license
    if args.keywords:
        manifest["keywords"] = [k.strip() for k in args.keywords.split(",") if k.strip()]
    (out / "plugin.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    # mcp.json (optional): copy the caller's server config, stamp the schema
    if args.mcp:
        mcp_in = json.loads(Path(args.mcp).read_text(encoding="utf-8"))
        servers = mcp_in.get("mcpServers", mcp_in)  # accept bare {id: cfg} too
        (out / "mcp.json").write_text(
            json.dumps({"$schema": MCP_SCHEMA, "mcpServers": servers}, indent=2) + "\n",
            encoding="utf-8",
        )

    print(f"built plugin '{args.name}' -> {out}  ({len(skills)} skill(s)"
          f"{', mcp.json' if args.mcp else ''})")
    problems = validate(out)
    return _report(out, problems)


def _report(root: Path, problems: list) -> int:
    if problems:
        print(f"INVALID: {root} — {len(problems)} problem(s)")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"VALID: {root} conforms to Agent Plugins 1.0.0")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Agent Plugins 1.0.0 build + validate")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="package a skills folder into a plugin")
    b.add_argument("--skills", required=True, help="dir of skill sub-dirs (each with SKILL.md)")
    b.add_argument("--name", required=True, help="plugin name (lowercase, . or - separators)")
    b.add_argument("--out", required=True, help="output plugin directory")
    b.add_argument("--mcp", help="optional mcp.json to include")
    b.add_argument("--version")
    b.add_argument("--description")
    b.add_argument("--author-name", dest="author_name")
    b.add_argument("--author-email", dest="author_email")
    b.add_argument("--author-url", dest="author_url")
    b.add_argument("--homepage")
    b.add_argument("--repository")
    b.add_argument("--license")
    b.add_argument("--keywords", help="comma-separated")

    v = sub.add_parser("validate", help="check a plugin dir against 1.0.0")
    v.add_argument("package", help="plugin directory to validate")

    args = ap.parse_args(argv)
    if args.cmd == "build":
        return build(args)
    if args.cmd == "validate":
        return _report(Path(args.package), validate(Path(args.package)))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
