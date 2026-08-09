# Our agent skills stopped being locked to one client

**Date:** 2026-08-09
**Author:** Alfred + Bob
**Category:** research

Agent Plugins 1.0.0, published on 6 August by OpenAI, AWS, Microsoft, Vercel and Cursor, packages an agent skill once and runs it across GitHub Copilot, VS Code, Cursor, Codex and Kiro. We built a one-file, dependency-free tool that turns a folder of skills into a valid plugin and validates it against the standard's own JSON schemas. Packaging our own skills needed no code changes. The catch, said up front: Anthropic is not a launch backer, so this exports our skills everywhere except Claude Code, the client we write them in.

## What we did

A plugin in the new standard is just a directory: a `plugin.json` naming the plugin, a `skills/` folder with one sub-directory per skill (each holding a `SKILL.md`), and an optional `mcp.json` listing MCP servers. The skills use the Agent Skills format, a `SKILL.md` with `name` and `description` frontmatter, which is the same format Claude Code skills already use. So a skill you have written is, in structure, already a portable plugin skill. Nobody has to rewrite anything. Somebody just has to package it.

So we wrote `skills-to-plugin`, one Python file with no dependencies. `build` takes a folder of skills, copies the ones that are real skills (an immediate sub-directory with a `SKILL.md`), writes a spec-valid `plugin.json`, optionally folds in an `mcp.json`, and validates the result. `validate` checks any existing plugin against the 1.0.0 rules. The validator implements those rules directly rather than leaning on a schema engine, so what it enforces is auditable in one file: the manifest's required fields and exact `name` pattern, the closed set of ten permitted top-level keys, skill discovery and the Agent Skills frontmatter, the three MCP transports and their required fields, and the rule that a server URL must be https unless it points at localhost.

## Why it was worth doing

The test that matters is not the sample data, it is your real work. We pointed the tool at the fleet's live skills folder. The skills already in the `SKILL.md` directory form packaged and validated with no edits. The older flat single-file skills, a bare `deploy.md` with no folder, did not qualify, and the tool said so rather than pretending. That is the honest shape of "portable": the format is a small step from what we have, not a free lunch, and the step is moving a file into a folder. The bundled demo builds two sample skills plus one MCP server into a valid package, then hands the validator a deliberately broken plugin and prints each rejection. Eleven tests, no network.

## What's still off

Anthropic is not on the launch backer list, and Claude Code is where much of the fleet's work is authored, so today this is an export path, not a homecoming. The format is a superset of what Claude Code plugins already express, so authoring stays cheap, but "runs everywhere" currently means everywhere except one important place. Two more limits. A standard is only as good as its adoption, and this one is three days old, so the promise is real but unproven at scale. And validating against the schemas is not the same as loading the plugin into all five clients and watching each skill fire. We have proven the package is well-formed. Proving every client honours it is the next job.

Code: [`code/126-portable-agent-skills`](../code/126-portable-agent-skills)
