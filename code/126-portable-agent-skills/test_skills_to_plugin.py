#!/usr/bin/env python3
"""Tests for skills_to_plugin. Pure stdlib, no network. Run: python3 -m unittest -v"""
import json
import tempfile
import unittest
from pathlib import Path

import skills_to_plugin as s2p


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_skill(root: Path, name: str, fm_name="x", fm_desc="does x") -> None:
    fm = "---\n"
    if fm_name is not None:
        fm += f"name: {fm_name}\n"
    if fm_desc is not None:
        fm += f"description: {fm_desc}\n"
    fm += "---\n\n# body\n"
    write(root / name / "SKILL.md", fm)


class BuildTests(unittest.TestCase):
    def test_build_produces_valid_package(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            src, out = td / "src", td / "out"
            make_skill(src, "alpha")
            make_skill(src, "beta")
            rc = s2p.main([
                "build", "--skills", str(src), "--name", "my.plugin",
                "--out", str(out), "--version", "1.0.0",
                "--description", "test", "--author-name", "Workloft",
                "--license", "MIT", "--keywords", "a, b ,c",
            ])
            self.assertEqual(rc, 0)
            manifest = json.loads((out / "plugin.json").read_text())
            self.assertEqual(manifest["$schema"], s2p.PLUGIN_SCHEMA)
            self.assertEqual(manifest["name"], "my.plugin")
            self.assertEqual(manifest["keywords"], ["a", "b", "c"])
            self.assertTrue((out / "skills" / "alpha" / "SKILL.md").is_file())
            self.assertEqual(s2p.validate(out), [])

    def test_build_with_mcp_stamps_schema(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            src, out = td / "src", td / "out"
            make_skill(src, "alpha")
            mcp = td / "in-mcp.json"
            mcp.write_text(json.dumps({"mcpServers": {
                "api": {"type": "streamable-http", "url": "https://x.example.com/mcp"}
            }}))
            rc = s2p.main(["build", "--skills", str(src), "--name", "p",
                           "--out", str(out), "--mcp", str(mcp)])
            self.assertEqual(rc, 0)
            got = json.loads((out / "mcp.json").read_text())
            self.assertEqual(got["$schema"], s2p.MCP_SCHEMA)
            self.assertIn("api", got["mcpServers"])


class ValidateTests(unittest.TestCase):
    def _pkg(self, td, manifest, skills=("alpha",), mcp=None):
        root = Path(td) / "pkg"
        root.mkdir(parents=True, exist_ok=True)
        (root / "plugin.json").write_text(json.dumps(manifest))
        for sk in skills:
            make_skill(root / "skills", sk)
        if mcp is not None:
            (root / "mcp.json").write_text(json.dumps(mcp))
        return root

    def test_clean_package_passes(self):
        with tempfile.TemporaryDirectory() as td:
            root = self._pkg(td, {"$schema": s2p.PLUGIN_SCHEMA, "name": "ok-name"})
            self.assertEqual(s2p.validate(root), [])

    def test_bad_name_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = self._pkg(td, {"$schema": s2p.PLUGIN_SCHEMA, "name": "Bad--Name"})
            probs = s2p.validate(root)
            self.assertTrue(any("name" in p for p in probs))

    def test_wrong_schema_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = self._pkg(td, {"$schema": "https://wrong", "name": "ok"})
            self.assertTrue(any("$schema" in p for p in s2p.validate(root)))

    def test_unknown_top_level_key_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = self._pkg(td, {"$schema": s2p.PLUGIN_SCHEMA, "name": "ok", "extra": 1})
            self.assertTrue(any("unknown top-level" in p for p in s2p.validate(root)))

    def test_missing_frontmatter_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "pkg"
            (root / "skills").mkdir(parents=True)
            (root / "plugin.json").write_text(
                json.dumps({"$schema": s2p.PLUGIN_SCHEMA, "name": "ok"}))
            make_skill(root / "skills", "alpha", fm_desc=None)
            self.assertTrue(any("description" in p for p in s2p.validate(root)))

    def test_bad_mcp_transport_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = self._pkg(
                td, {"$schema": s2p.PLUGIN_SCHEMA, "name": "ok"},
                mcp={"$schema": s2p.MCP_SCHEMA,
                     "mcpServers": {"x": {"type": "carrier-pigeon", "url": "https://x"}}})
            self.assertTrue(any("invalid type" in p for p in s2p.validate(root)))

    def test_http_non_localhost_url_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = self._pkg(
                td, {"$schema": s2p.PLUGIN_SCHEMA, "name": "ok"},
                mcp={"$schema": s2p.MCP_SCHEMA,
                     "mcpServers": {"x": {"type": "streamable-http",
                                          "url": "http://evil.example.com/mcp"}}})
            self.assertTrue(any("https" in p for p in s2p.validate(root)))

    def test_stdio_requires_command(self):
        with tempfile.TemporaryDirectory() as td:
            root = self._pkg(
                td, {"$schema": s2p.PLUGIN_SCHEMA, "name": "ok"},
                mcp={"$schema": s2p.MCP_SCHEMA,
                     "mcpServers": {"x": {"type": "stdio"}}})
            self.assertTrue(any("requires 'command'" in p for p in s2p.validate(root)))

    def test_localhost_http_allowed(self):
        with tempfile.TemporaryDirectory() as td:
            root = self._pkg(
                td, {"$schema": s2p.PLUGIN_SCHEMA, "name": "ok"},
                mcp={"$schema": s2p.MCP_SCHEMA,
                     "mcpServers": {"x": {"type": "streamable-http",
                                          "url": "http://localhost:8000/mcp"}}})
            self.assertEqual(s2p.validate(root), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
