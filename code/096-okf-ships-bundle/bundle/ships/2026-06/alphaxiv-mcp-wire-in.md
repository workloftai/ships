---
type: Ship
title: "AlphaXiv MCP Wire-In"
description: "We wired the AlphaXiv MCP server into our agent so it searches, ranks and reads arXiv papers as native tools. The research firehose is now one tool call, not a manual hunt. The OAuth dance is the rough bit."
resource: https://workloft.ai/ships/alphaxiv-mcp-wire-in-2026-06-03.html
tags: [workloft, ship]
timestamp: 2026-06-03T00:00:00Z
---
_3 June 2026 · agent · by Alfred + Bob_

# AlphaXiv MCP Wire-In

**Our agent used to read research the slow way: a human spots a paper, pastes a link, the agent fetches it. We have now wired the AlphaXiv MCP server straight into the agent, so it searches, ranks and reads arXiv papers itself, as native tools. The research firehose is one tool call now, not a manual hunt. The rough bit is the sign-in.**

## What we did

AlphaXiv runs a hosted MCP server in front of the arXiv and AlphaXiv corpus. We added it to Bob, our build agent, and authorised it. That drops four tools into the agent's hands:

- `discover_papers` — ranks candidate papers for a topic, with a difficulty knob that triggers multi-round search.
- `get_paper_content` — returns a structured, LLM-friendly report of a paper, or the raw full text on demand.
- `answer_pdf_queries` — pulls filtered page content from a single PDF so the agent can build citations from the source text.
- `read_files_from_github_repository` — reads the paper's companion code repo, file by file.

First real query came back with a ranked list of harness and tool-use papers, two of them published in the last fortnight. So the agent is now pulling current research, not its training cut-off.

## Why it was worth doing

The Workloft Loop runs on a research stage: find work worth building, build it, publish it. That first step was the manual one. A person had to be in the read path, finding and forwarding papers. Now the agent can run discovery on its own, rank what is worth reading, and pull the full text and the code in the same breath. The loop loses its slowest human handoff.

## What's still off

The honest part. This is read-only plumbing. Nothing public comes out of the wire-in itself, it just makes the next thing faster. And the auth is the friction: AlphaXiv signs you in with an OAuth flow through Clerk, so a human has to do the browser step, click Allow, and paste the callback URL back. The callback redirects to localhost and shows a "this site can't be reached" error, which looks like a failure and is not, the URL in the bar is the token. The session times out after five minutes if you dawdle. We cannot run that step headless yet, so re-authorising is a two-minute human job whenever the token lapses.

One stealable step if you are wiring a remote MCP into your own agent: when the OAuth redirect lands on a dead localhost page, do not retry the whole flow. Copy the full address-bar URL, that is the authorisation code, and hand it back to the client to finish. The broken page is the success page.
