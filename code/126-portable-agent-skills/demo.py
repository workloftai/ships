#!/usr/bin/env python3
"""End-to-end demo. No network. Run: python3 demo.py

Builds the two sample skills (+ an MCP server) into a real Agent Plugins 1.0.0
package, validates it, then shows the validator rejecting a broken package.
"""
import sys
from pathlib import Path

import skills_to_plugin as s2p

HERE = Path(__file__).parent


def main() -> int:
    print("1) Build sample-skills/ into an Agent Plugins 1.0.0 package")
    print("-" * 68)
    rc = s2p.main([
        "build",
        "--skills", str(HERE / "sample-skills"),
        "--mcp", str(HERE / "sample-skills" / "mcp.json"),
        "--name", "workloft-sample",
        "--out", str(HERE / "dist"),
        "--version", "1.0.0",
        "--description", "Two portable skills plus one MCP server, packaged once.",
        "--author-name", "Workloft",
        "--homepage", "https://workloft.ai",
        "--repository", "https://github.com/workloftai/ships",
        "--license", "MIT",
        "--keywords", "agent-skills, mcp, portable",
    ])
    if rc != 0:
        return rc

    print("\n2) The built package (this is the whole plugin, a plain directory)")
    print("-" * 68)
    for p in sorted((HERE / "dist").rglob("*")):
        if p.is_file():
            print("   ", p.relative_to(HERE / "dist"))

    print("\n3) Validator catches a broken plugin (bad name, wrong transport)")
    print("-" * 68)
    import json, tempfile
    with tempfile.TemporaryDirectory() as td:
        bad = Path(td) / "bad-plugin"
        (bad / "skills" / "x").mkdir(parents=True)
        (bad / "skills" / "x" / "SKILL.md").write_text("---\nname: x\n---\n")  # no description
        (bad / "plugin.json").write_text(json.dumps(
            {"$schema": s2p.PLUGIN_SCHEMA, "name": "Bad--Name", "oops": True}))
        (bad / "mcp.json").write_text(json.dumps(
            {"$schema": s2p.MCP_SCHEMA,
             "mcpServers": {"p": {"type": "carrier-pigeon", "url": "http://evil.example.com"}}}))
        for prob in s2p.validate(bad):
            print("    rejected:", prob)

    print("\nDone. Point --skills at your own Claude Code skills folder to package it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
