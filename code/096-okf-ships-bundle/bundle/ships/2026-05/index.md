# Ships — 2026-05

* [We could see what the robots spent. Not what they earned.](cron-revenue-attribution.md) - Our audit log tracked every pound an always-on cron spent on tokens, but nothing about the revenue it brought in.
* [The rule was saved. The agent never saw it.](memory-index-guard.md) - Our agent kept breaking a saved rule because the memory index had outgrown its load budget and was being truncated before it reached contex…
* [The V4-Pro Reasoning-Token Mirage](v4-pro-reasoning-token-mirage.md) - DeepSeek V4-Pro's price fell 75%.
* [The Social Loop](the-social-loop.md) - We built the Typefully bridge: post drafts flow out for scheduling, and a 15-minute cron reconciles the published URLs back into our ledger.
* [Bob's actions now write Vera's tests](auto-rubrics.md) - Workloft's audit log already records every action our eight agents take.
* [civiclaw FOI intake prompt polished](civiclaw-foi-prompt-polish.md) - civiclaw's FOI intake prompt invited the model to ask clarifying questions back.
* [civiclaw GitHub mirror live](civiclaw-github-mirror.md) - civiclaw is now mirrored at github.com/workloftai/civiclaw, push-mirrored from the GitLab canonical via GitLab's remote_mirrors API.
* [civiclaw sovereign Ollama fallback wired end-to-end](civiclaw-sovereign-ollama-fallback.md) - civiclaw's sovereign on-prem path was scaffolded but not wired.
* [Walt's picks now grade themselves](walt-weight-loop.md) - The outer loop of two-level autoresearch wired into Walt.
* [Audited the next MCP spec two months early](mcp-stateless-rc.md) - We audited Workloft's hosted MCP endpoint against the 2026-07-28 draft spec.
* [SEAL evolve — failure-driven guardrails from the audit log](seal-evolve.md) - We read SEAL (arxiv 2605.26 paper) at 8am, picked the environment-side kernel, built it on our audit log by lunch.
* [Labs Carousel — PDF carousel generator for Workloft Labs Notes](labs-carousel.md) - A 1080x1350 LinkedIn-native PDF carousel for every Workloft Labs Note.
* [Agentic Oddities, the fortnightly weird-AI digest](agentic-oddities.md) - A 3-day-cadence scraper that pulls real-world AI-agent failure stories from HN and Google News, scores them with Walt, has Vera pick the he…
* [Workloft Labs, now a hosted MCP server](labs-mcp.md) - We turned the Workloft Labs HTTP API into a hosted MCP server.
* [A todo system Bob cannot cheat](watertight-todos.md) - A watertight todo system for our agent stack.
* [A ledger for every public post](workloft-posts.md) - A small Supabase ledger of every public post (LinkedIn, X, future channels).
* [The interop floor lifted. We swept our positioning to match.](a2a-positioning-sweep.md) - A2A v1.0 crossed 150 organisations and one year inside the Linux Foundation last month.
* [Your audit log is training data](audit-log-as-training-data.md) - We applied Agent Context Compilation to our own production audit log.
* [llms.txt for Workloft, shipping for real this time](llms-txt-for-workloft.md) - Our llms.txt existed in the repo for weeks and 404'd in production for weeks.
* [Every Note and Ship Now Has A Markdown Sibling](markdown-siblings.md) - Every labs/notes/*.html and ships/*.html on workloft.ai is now also published as a clean Markdown sibling at the same path.
* [The Selection Gate Now Sits On A Panel](poll-selection-gate.md) - We retired the single-LLM judge at the Workloft selection gate and replaced it with a three-juror panel across distinct model lineages.
* [Bob Picks Up the Phone](bob-picks-up-the-phone.md) - After several weeks of back-and-forth with Twilio support, the Workloft voice line is live.
* [Gemini Managed Agents, wired into Ruby](gemini-managed-agents.md) - Google shipped one-call managed agents at I/O 2026.
* [AgentPass V0.1 — the verification primitive AI agents don't yet have](agentpass-rfc.md) - On 3 May 2026 we published AgentPass V0.1 as an RFC.
