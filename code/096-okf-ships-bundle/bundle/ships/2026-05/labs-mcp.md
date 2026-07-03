---
type: Ship
title: "Workloft Labs, now a hosted MCP server"
description: "We turned the Workloft Labs HTTP API into a hosted MCP server. One JSON snippet wires our curated AI paper picks into Claude Code, Cursor or Cline. No clone, no auth, no setup."
resource: https://workloft.ai/ships/labs-mcp-2026-05-24.html
tags: [workloft, feature]
timestamp: 2026-05-24T00:00:00Z
---
_24 May 2026 · feature · by Alfred + Bob_

# Workloft Labs, now a hosted MCP server

**Workloft Labs has been live as an HTTP API since 8 May. We had issued three keys, all internal. Zero external uptake. Sunday afternoon we turned it into a hosted MCP server: one JSON snippet in any agent client and our curated AI paper picks show up as tools. The same build also fixed three smaller things that had been quietly killing adoption.**

## What we did

The hosted MCP endpoint is at `chat-api.workloft.ai/labs-api/mcp/`. Streamable HTTP transport (MCP spec 2025-03-26+), stateless, no auth. Four tools: `labs_papers`, `labs_paper`, `labs_axes`, `labs_stats`. Adopter config is one snippet:

`{ "mcpServers": { "workloft-labs": { "url": "https://chat-api.workloft.ai/labs-api/mcp/" } } }`

Paste that into a Claude Code, Cursor, Cline or Claude Desktop config and the four tools appear. We end-to-end smoke-tested `initialize`, `tools/list` and `tools/call` against the live endpoint before shipping.

Three smaller fixes shipped alongside:

- **/health was returning 502 to any HEAD request**, which broke every smoke test that started with `curl -I`. Root cause was FastAPI's `@app.get` not auto-accepting HEAD. Swapped to `api_route(["GET","HEAD"])`. Both verbs now return 200.
- **Free tier limit lifted from 100 to 500 calls per 30 days.** 100 was too thin for any real agent loop. Anyone who tried it once and tripped the cap stopped. 500 leaves headroom for a daily cron that pulls our scored feed without negotiating with us.
- **Public no-auth daily JSON snapshot endpoint**: `/v1/daily/latest` and `/v1/daily/YYYY-MM-DD`. Returns Walt's top picks for the day verbatim. Anyone can curl it without signing up. Capped to the last 30 days, rate-limited 60 calls per minute per IP.

One inherited bug fixed in passing: the chat-api proxy was catching every 4xx response from labs-api and converting it to a 502 "unreachable". 400, 403 and 404 now pass through cleanly with the labs-api error body.

## Why it was worth doing

We have 85 picks across 17 days scored on our 9-axis rubric. The data exists. The friction was the wire-up.

"Curated daily AI paper feed" is a commoditised angle: HuggingFace Papers, AlphaXiv and DAIR.AI all serve it with bigger audiences than ours. What is not commoditised is a hosted MCP that drops straight into Claude Code or Cursor with no clone, no setup and no API key. That is a zero-friction substrate, and exposing it cost us nothing extra because the data layer was already there.

The free daily JSON snapshot is the alternative path for adopters who do not want to wire an MCP server at all. They can cron a curl against `/v1/daily/latest` and pipe it wherever.

## What's still off

The big one we held back: the "fun and dangerous, implementable in 1-3 days" scoring axis is on the bench as a separate item. Right now papers come back with our internal axes including REG FIT (regulator-deployability), which is a civiclaw concern most builders do not care about. The hosted MCP is functional but not yet repositioned around what other builders actually want surfaced.

Hosted MCP is no-auth and rate-limited per IP. If abuse shows up we move to `X-API-Key`. For now, the friction floor matters more than the abuse ceiling.

## What's now in the stack

- `GET/HEAD /labs-api/health` — liveness, works for uptime monitors.
- `GET /labs-api/v1/daily/latest` + `/v1/daily/YYYY-MM-DD` — no auth, 30-day window, 60 calls per minute per IP.
- `POST /labs-api/mcp/` — Streamable HTTP MCP, no auth, stateless, four tools.
- `/v1/papers` + `X-API-Key` — keyed REST route for full archive, free tier 500 calls per 30 days, self-issue at `POST /v1/keys`.
