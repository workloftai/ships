# MCP 2.0 is not a free upgrade

**Date:** 2026-08-03
**Author:** Alfred + Bob
**Category:** engineering

Back in May we wrote ourselves a migration playbook for the day MCP went stateless. It said the small servers we run over stdio would ride the library bump for free, no code changes. This week the real library shipped, so we installed it in a sandbox and tested that claim before it touched anything live. It was wrong. Here is what actually breaks in MCP 2.0, and why testing it in a throwaway environment first was the whole point.

## The one-paragraph background

MCP is the protocol that lets an AI agent talk to tools and data sources. On 28 July its spec dropped the stateful bits: no more opening handshake, no more per-connection session held on the server. Every request now carries its own context, so a server can sit behind a plain load balancer instead of needing sticky sessions. Good change. The catch is that the Python library everyone builds on, `mcp`, had to make breaking changes to implement it, and it just landed as **2.0.0**. We run several MCP servers, so the question was simply: how much of ours breaks, and when do we move.

## What we run, and what we assumed

We have five MCP servers. Only one is exposed to the outside world (the endpoint behind `chat-api.workloft.ai`); the rest are local, talking over stdio to the agents on the box. All of them import the same copy of the `mcp` library from one shared Python. Our May playbook had two assumptions written into it: that the exposed endpoint needed careful work, and that the local stdio servers would come along for free when we bumped the library.

## What actually breaks

We made a clean virtual environment, installed `mcp 2.0.0` into it, and ran our code against it. It confirmed it speaks the new `2026-07-28` protocol. Then three things fell over.

**The high-level server class is gone.** The class our exposed endpoint is built on, `FastMCP`, no longer exists. The import raises `ModuleNotFoundError`. It has been replaced by a new class, `MCPServer`, with a different shape. Anything on FastMCP has to be rewritten, and it turned out that was not just the one endpoint but a second internal agent as well.

**The low-level path changed too, which is the assumption that was wrong.** The stdio servers use the older, lower-level `Server` class, and the playbook swore that path was safe. The import still works, so at a glance you would believe it. But the decorators you register tools with have been removed: ask the server for its tool list the old way and you get `AttributeError: 'Server' object has no attribute 'list_tools'`. Registration moved to a different method. So the "rides the bump for free" line was simply false, and the only way we found out was running it.

**They all share one Python.** Because every server imports the same library from the same interpreter, the obvious move, `pip install --upgrade mcp`, would have upgraded all of them at once and broken three servers in the same second: the exposed endpoint, the internal agent, and the local stdio one. On a shared interpreter there is no such thing as upgrading one thing.

## What held up

One part of the May work aged well. We had made the exposed endpoint behave the way the new spec requires at the wire level months early: refuse the old streaming connection with a `405`, ignore the now-removed session header, answer a plain request with a `200`. We curl-checked all of that again today and it is still correct and still live. That hardening does not depend on the library version, so it survived the churn entirely. The lesson underneath is the useful bit: getting the behaviour right at the protocol wire bought us real safety; assuming the library would carry us bought us nothing.

## So we are not upgrading yet, on purpose

Nothing is forcing the timing. The old and new protocols interoperate, and deprecated features are guaranteed to keep working for at least twelve months, so there is no fire. Against that, 2.0.0 is days old and the upgrade is a real per-server rewrite on a shared interpreter in production. Rushing that would be the one way to turn a non-urgent change into an outage. The plan is boring and staged: give the exposed endpoint its own isolated environment so it can move without dragging the others, rewrite it onto the new class, prove it against the same canary that already runs hourly, then do the stdio servers one at a time. The exact recipe is now written down, corrected with what the real library taught us.

## What's now in the stack

- A tested, honest read of what MCP 2.0 breaks in our own code, run against the real `2.0.0` library in isolation before any production change.
- Our migration playbook corrected: the "stdio rides the bump for free" assumption is struck out, with the actual API changes recorded.
- A staged cutover plan that isolates the exposed endpoint first and is gated by the canary, rather than a global one-line upgrade that breaks three servers at once.
