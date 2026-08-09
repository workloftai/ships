# skills-to-plugin

Package a folder of Agent Skills into an [Agent Plugins 1.0.0](https://agent-plugins.org)
plugin, and validate any plugin against the 1.0.0 schemas. One file, no
dependencies.

Agent Plugins 1.0.0 (published 6 August 2026, backed by OpenAI, AWS, Microsoft,
Vercel, Cursor and GitHub) is a vendor-neutral format for shipping one plugin
across agent clients. A plugin is a plain directory:

```
my-plugin/
|- plugin.json          # $schema + name (+ optional metadata)
|- skills/              # one sub-dir per skill, each with a SKILL.md
|- mcp.json             # optional: stdio / streamable-http / sse servers
```

Skills use the Agent Skills format (`SKILL.md` with `name` + `description`
frontmatter), which is the same format Claude Code skills already use. So the
skills you have written are already portable. You just have to package them, and
that is all this does.

## Run it

```bash
python3 demo.py                 # build the samples, validate, show a rejection
python3 -m unittest -v          # 11 tests, no network
```

## Build your own

```bash
python3 skills_to_plugin.py build \
  --skills ./my-skills \
  --name my-plugin \
  --out ./dist/my-plugin \
  --description "..." --author-name "..." --license MIT \
  --mcp ./my-skills/mcp.json      # optional
```

`build` copies every immediate sub-directory of `--skills` that contains a
`SKILL.md`, writes a spec-valid `plugin.json`, optionally stamps an `mcp.json`,
then validates the result.

## Validate an existing plugin

```bash
python3 skills_to_plugin.py validate ./dist/my-plugin
# VALID: ./dist/my-plugin conforms to Agent Plugins 1.0.0
```

The validator implements the 1.0.0 rules directly (manifest required fields and
`name` pattern, the closed set of top-level keys, skill discovery and Agent
Skills frontmatter, MCP transport rules and the https-except-localhost URL rule)
so what it checks is auditable in one file, not hidden behind a schema engine.

## The honest caveat

Only skills already in the `SKILL.md` directory form package directly. Older
flat single-file skills (`deploy.md` with no folder) do not qualify until you
move them into `deploy/SKILL.md`. The tool reports what it packaged so you can
see what was skipped. And Anthropic is not a launch backer of the standard, so
today this exports your skills everywhere except the client many of us author
them in.

MIT. Steal what you need.
