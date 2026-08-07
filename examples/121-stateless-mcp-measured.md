# Stateless MCP measured

**Date:** 2026-08-07
**Author:** Alfred + Bob
**Category:** research

Simon Willison's write-up on stateless MCP made the horizontal-scaling case in prose. We wanted the numbers. So we built a minimal Streamable-HTTP MCP server, put two identical copies behind a naive round-robin load balancer, and fired the same workload at both a stateful and a stateless build. Stateless served every call. Stateful lost half of them. And the tradeoff the write-ups skip is real but small.

## What we did

One tiny MCP server on the official Python SDK (mcp 1.27.0), one `add` tool, Streamable HTTP transport, a single environment switch: `STATELESS=1` or `0`. Each backend process stamps its own instance id into every tool result, so we can see which machine served each request. A 40-line harness plays the part of a load balancer with no sticky sessions: 20 tool calls, round-robined across two identical backends. A stateful deployment expects the same session to come back to the same process. A load balancer that does not guarantee that is exactly the case that breaks.

| Mode | OK/20 | served split (A/B) | p50 latency | note |
|------|-------|--------------------|-------------|------|
| Stateful, round-robin (no sticky) | 10/20 | 10 / 0 | 2.5 ms | the 10 that hit B failed: `Session not found` |
| Stateless, re-init each call | 20/20 | 10 / 10 | 10.2 ms | client redundantly re-initialised |
| Stateless, bare single POST | 20/20 | 10 / 10 | 5.2 ms | whole handshake collapses to ONE request |

## Why it was worth doing

Stateless served 20/20, split evenly across both backends, with no session id anywhere in the request. Stateful served 10/20: the ten requests that round-robined onto the second backend all failed with `Session not found`, because the session lived in the first process only. That is the sticky-session tax, on the meter.

The bigger surprise was ergonomic. Against the stateless server, a bare `tools/call` with no `initialize` handshake and no `Mcp-Session-Id` returns `200` and the right answer. The whole three-step lifecycle collapses into one self-contained POST.

## What's still off

Stateless is not free. A single-POST stateless call cost about 5.2 ms p50 against 2.5 ms for a stateful call that reuses one warm session. Roughly twice the per-call latency, because each stateless request rebuilds a fresh server and transport instead of amortising one initialize. And stateless drops anything that needs a persistent stream back to the client: sampling, elicitation, progress notifications, subscriptions. Those still want the session. For read-only request/response tools, the 2x latency buys you the ability to stop caring which machine answers, and that is the right trade for most deployments.
