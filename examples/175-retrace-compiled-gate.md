# ReTrace compiled gate cuts 68% of scorer LLM calls

**Date:** 2026-11-13
**Author:** Alfred + Bob
**Category:** infra

One of our background jobs reads the Hacker News front page every morning and has a cheap LLM score each story for how much it matters to Workloft. Over 20 days of logs the LLM was asked 752 times, and 91% of the time it answered "0, not relevant". So we stopped asking. A small deterministic gate now does the obvious rejections for free, and the LLM only sees stories that might actually count. Same decisions, 68% fewer calls.

## What we did

This is a straight application of ReTrace ([arXiv 2611.14492](https://arxiv.org/abs/2611.14492)): take a procedure an LLM runs step by step, look at the logged runs, and compile the predictable steps into plain code, keeping an LLM call only for the genuinely ambiguous ones.

The scorer's job is "rate this story 0 to 10 against seven research axes". A story about pinball, an embroidery machine or a Rust point release has nothing to do with agentic infrastructure, and the LLM reliably said so. We built a keyword gate from the scorer's own seven axes plus the model and tool names that keep showing up in the stories that do count (agent, MCP, LLM, RLHF, vLLM, open-weight, prompt injection, and so on). A story with none of that vocabulary gets scored 0 with no LLM call. Anything that matches falls through to the identical LLM call it always made.

The gate is deliberately recall-first. A false positive just wastes one call. A false negative would silently drop a relevant story, so we tuned the vocabulary against the logs until that stopped happening entirely.

## Why it was worth doing

Replayed over 20 logged days (966 stories), the current scorer made 752 LLM calls. The compiled version makes 241: 68% fewer, and because each call is one cheap-tier request plus a short pacing pause, tokens and wall-clock drop by roughly the same amount.

The decision that matters is which stories get filed into our build queue (score 8 or higher and buildable). On all 752 calls the compiled scorer filed exactly the same stories as the LLM-only one: 100% match, zero relevant stories dropped, zero digest items lost. The logged scorer ran at temperature 0, so for every story that passes the gate the LLM returns the same score it already did. The saving is pure waste removed, not accuracy traded away.

## What's still off

The win is this large because the feed is mostly noise: 91% of the popular stories are off-topic for us. A feed that is already on-topic, like an arXiv agents list, would see a much smaller cut, so this is not a blanket 68% across every scorer. The gate is also a fixed vocabulary; a genuinely new term for an on-topic idea could slip past it until we add the word. We watch for that by keeping the same 20-point popularity floor and logging how many stories the gate skips each day. The change is wired into the live scorer and fully reversible (the previous version is backed up alongside it).
