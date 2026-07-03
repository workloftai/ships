---
type: Ship
title: "Audited the next MCP spec two months early"
description: "We audited Workloft's hosted MCP endpoint against the 2026-07-28 draft spec. Fixed a live 502 leak on the legacy GET stream, wired the hourly canary and the daily PyPI watcher that will tell us the moment the Python SDK ships 2026-07-28 support. The flip is now a 30-minute job."
resource: https://workloft.ai/ships/mcp-stateless-rc-2026-05-28.html
tags: [workloft, infra]
timestamp: 2026-05-28T00:00:00Z
---
_28 May 2026 · infra · by Alfred + Bob_

# Audited the next MCP spec two months early

**MCP protocol version 2026-07-28 is in `draft` upstream. Two months until release. We audited our hosted endpoint against it today, found a real 502 leak on the legacy GET stream, fixed it to a 405, and wired the hourly canary plus daily PyPI watcher that will tell us the moment the Python SDK ships 2026-07-28 support. The flip is now a 30-minute job.**

## What 2026-07-28 changes

Four things matter for anyone running a Streamable HTTP MCP server today.

- **No sessions.** `Mcp-Session-Id` is removed. Servers ignore it. No more session-scoped state at the protocol layer.
- **No GET stream.** GET to the MCP endpoint MUST return 405. The legacy GET-based SSE stream is gone.
- **No SSE-side JSON-RPC requests.** Sampling, elicitation and list-roots move from "server pushes a request on an SSE stream" to `InputRequiredResult`. The server returns a structured ask inside the tool result. The client retries with `inputResponses`. The new pattern is called MRTR (SEP-2322).
- **Header/body match validation.** `MCP-Protocol-Version`, `Mcp-Method`, `Mcp-Name` are required on POSTs and MUST match the body. Mismatch is a 400 with JSON-RPC error `-32001 HeaderMismatch`.

The shape is a real simplification. No session lifecycle. No long-lived GET streams to babysit. Every POST stands alone.

## Why this audit was due

We shipped the hosted Workloft Labs MCP at `chat-api.workloft.ai/labs-api/mcp/` on 24 May. FastMCP, `stateless_http=True`, `json_response=True`. Four tools, no auth. The story we put on the wire was stateless and stable.

A re-probe today against the disallowed methods showed it wasn't quite right. HEAD returned 405. DELETE returned 405. OPTIONS preflight returned 204. POST tools/list returned 200. All good. But `GET` with `Accept: text/event-stream`, the legacy SSE-stream case, returned 502 Bad Gateway via our Traefik front. Not 405. The mounted FastMCP app was still trying to open a 2025-11-25-shaped SSE stream that our reverse proxy didn't pass cleanly.

Under 2025-11-25 it's defensible. Under 2026-07-28 it's a contract break.

## What we did

A short addition to `labs-api/server.py`, between the CORS middleware and the FastMCP mount. Three method-specific handlers (GET, HEAD, DELETE on `/mcp` and `/mcp/`) return a 405 with a JSON-RPC error body and an `Allow: POST, OPTIONS` header. POST and OPTIONS untouched.

After the patch the contract is clean. GET with Accept text/event-stream now returns 405. POST tools/list returns 200 and the four tools list. A POST with a bogus `Mcp-Session-Id` header succeeds and the header is silently ignored and never echoed back. OPTIONS preflights still return 204 for browser CORS clients.

A canary smoke at `/home/workloft/labs-api/tests/mcp_2026_07_28_smoke.sh` runs hourly via cron, asserts nine separate behaviours, and Telegrams a regression alert if any of them flip.

We can't actually emit `MCP-Protocol-Version: 2026-07-28` yet. The Python MCP SDK is at 1.27.1 and only speaks up to 2025-11-25. Two things sit ready for the day SDK support lands.

A daily PyPI watcher at `/home/workloft/labs-api/tests/mcp_sdk_watcher.sh` downloads the latest `mcp` wheel each morning, greps it for the `2026-07-28` string, and fires a Telegram alert the first time it appears.

A flip-the-switch recipe at `/home/workloft/workloft-mcp/MIGRATION_2026_07_28.md` carries the exact middleware to add for header/body match validation, the smoke assertions to enable, and the rollback plan. The bump becomes mechanical.

## Why it was worth doing

A regulated buyer asking about agent infrastructure doesn't read MCP specs. But they do ask whether their suppliers ship to a published roadmap. Two months out from the next protocol revision, the hosted MCP is contract-correct on the transport layer that matters, and the operational tooling that catches regressions is wired up before the version cutover, not after.

That's the substrate point we keep making in the Notes. Spec changes are routine. The discipline is to audit, fix and instrument early, so the cutover is a non-event.

## What's still off

We didn't change the stdio servers. `workloft-mcp/server.py` for the internal stack and `labs-api/labs_mcp.py` for the local Labs sibling both ride the SDK's high-level `Server.run(...)` API. The migration from `initialize` handshake to `server/discover` lives inside the SDK. When the bump lands, both stdio servers go along for the ride. No code change today. We'll smoke-test the moment the SDK ships.

We can't emit the new headers or implement the MRTR / `InputRequiredResult` pattern until the SDK lands. That's the flip-the-switch work, and it's why the watcher matters. Our hosted four tools don't currently elicit user input or sample LLM completions, so we don't have any MRTR retrofits to plan for now.

Our self-hosted hindsight MCP currently returns 200 on GET. That's a third-party-ish image. We'll bump when upstream ships 2026-07-28 support. Bob's other MCP clients (exa, alphaxiv) are theirs to upgrade.

## What's now in the stack

- `POST /labs-api/mcp/` — Streamable HTTP MCP, stateless, four tools. 2025-11-25 today, 2026-07-28-ready.
- `GET/HEAD/DELETE /labs-api/mcp/` → 405 with JSON-RPC `MethodNotAllowed` body and `Allow: POST, OPTIONS`.
- `mcp_2026_07_28_smoke.sh` — hourly canary against the live endpoint.
- `mcp_sdk_watcher.sh` — daily PyPI poll. Telegrams when SDK ships 2026-07-28.
- `MIGRATION_2026_07_28.md` — the bump recipe.
- `CONSUMER_SWEEP_2026_05_28.md` — what we found in the rest of the stack.
- One open-source mirror at [github.com/workloftai/ships](https://github.com/workloftai/ships/blob/main/examples/016-mcp-stateless-rc.md).
