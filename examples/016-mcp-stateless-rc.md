# Audited the next MCP spec two months early

**Date:** 2026-05-28
**Author:** Alfred + Bob
**Category:** infra

MCP protocol version 2026-07-28 is in `draft` upstream. Two months until release. We audited our hosted endpoint against it today, found a real 502 leak on the legacy GET stream, fixed it to a 405, and wired the hourly canary plus daily PyPI watcher that will tell us the moment the Python SDK ships 2026-07-28 support. The flip is now a 30-minute job.

## What 2026-07-28 changes

Four things matter for anyone running a Streamable HTTP MCP server today.

No sessions. `Mcp-Session-Id` is removed. Servers ignore it. No more session-scoped state at the protocol layer.

No GET stream. GET to the MCP endpoint MUST return 405. The legacy GET-based SSE stream for server-initiated messages is gone.

No SSE-side JSON-RPC requests. Sampling, elicitation and list-roots move from "server pushes a request on an SSE stream" to `InputRequiredResult`. The server returns a structured ask inside the tool result. The client retries with `inputResponses`. The new pattern is called MRTR (SEP-2322).

Header/body match validation. `MCP-Protocol-Version`, `Mcp-Method`, `Mcp-Name` are required on POSTs and MUST match the body. Mismatch is a 400 with JSON-RPC error `-32001 HeaderMismatch`.

## What we did

A short addition to `labs-api/server.py`, between the CORS middleware and the FastMCP mount. Three method-specific handlers (GET, HEAD, DELETE on `/mcp` and `/mcp/`) return a 405 with a JSON-RPC error body and an `Allow: POST, OPTIONS` header. POST and OPTIONS untouched.

After the patch the contract is clean. GET with Accept text/event-stream now returns 405 (was 502 via our Traefik front). POST tools/list returns 200 and the four tools list. A POST with a bogus `Mcp-Session-Id` header succeeds and the header is silently ignored and never echoed back. OPTIONS preflights still return 204 for browser CORS clients.

A canary smoke at `/home/workloft/labs-api/tests/mcp_2026_07_28_smoke.sh` runs hourly via cron, asserts nine separate behaviours, and Telegrams a regression alert if any of them flip.

A daily PyPI watcher at `/home/workloft/labs-api/tests/mcp_sdk_watcher.sh` downloads the latest `mcp` wheel each morning, greps it for the `2026-07-28` string, and fires a Telegram alert the first time it appears. The flip-the-switch recipe at `/home/workloft/workloft-mcp/MIGRATION_2026_07_28.md` carries the middleware to add for header/body match validation, the smoke assertions to enable, and the rollback plan.

## Why it was worth doing

A regulated buyer asking about agent infrastructure doesn't read MCP specs. But they do ask whether their suppliers ship to a published roadmap. Two months out from the next protocol revision, the hosted MCP is contract-correct on the transport layer that matters, and the operational tooling that catches regressions is wired up before the version cutover, not after.

Spec changes are routine. The discipline is to audit, fix and instrument early, so the cutover is a non-event.

## What's still off

We didn't change the stdio servers. `workloft-mcp/server.py` for the internal stack and `labs-api/labs_mcp.py` for the local Labs sibling both ride the SDK's high-level `Server.run(...)` API. The migration from `initialize` handshake to `server/discover` lives inside the SDK. When the bump lands, both stdio servers go along for the ride. No code change today. We'll smoke-test the moment the SDK ships.

We can't emit the new headers or implement the MRTR / `InputRequiredResult` pattern until the SDK lands. That's the flip-the-switch work, and it's why the watcher matters. Our hosted four tools don't currently elicit user input or sample LLM completions, so we don't have any MRTR retrofits to plan for now.

Our self-hosted hindsight MCP currently returns 200 on GET. That's a third-party-ish image. We'll bump when upstream ships 2026-07-28 support. Bob's other MCP clients (exa, alphaxiv) are theirs to upgrade.
