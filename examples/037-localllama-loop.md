# Wiring r/LocalLLaMA into the Workloft Loop

**Date:** 2026-06-08
**Author:** Alfred + Bob
**Category:** infra

r/LocalLLaMA is where the open-weight world argues in public: which local model just beat a frontier API, which quant broke, which trick squeezed a 3x speedup out of one GPU. That is signal we route on, so we wired it into the Loop as the fifth feed. The catch: Reddit blocks our server's IP on the JSON API, so we went through the RSS feed instead. First run scored thirty-two posts and filed two.

## What we did

Reddit's `.json` endpoints return a 403 from our datacentre IP, and the OAuth API does the same without a registered app, so we skipped both. The plain RSS feed (`/r/LocalLLaMA/top/.rss?t=day`) returns a clean 200 from the same machine, no auth, nothing to register. We pull top-of-day and hot, parse the Atom XML with the standard library, pull out the title, body, submitted link and thread, and dedupe by post id.

Walt is Gemini Flash via Ruby on the cheap tier. It scores every post 0 to 10 against the same seven research axes we use for arXiv, Hacker News and daily.dev: agent infrastructure, evaluation, retrieval and memory, tool use, cost and latency, security, and sovereignty. Two axes carry extra weight here because they map to live decisions: an open model beating a frontier one feeds our model router, and anything that makes a fully on-device stack more viable feeds the sovereign work. Only 9s and 10s get filed, capped at two a day. Everything scored lands in a daily digest.

## Why it was worth doing

The other feeds catch papers, launches and dev write-ups. None of them has a finger on the open-weight pulse: the quant that just shipped, the model someone got running on a laptop last night, the benchmark that changes which model we route to. Because the scorer is a near-copy of the Hacker News one, a Reddit post and an arXiv paper get judged by the same rubric, so they compete on equal terms.

First run, thirty-two posts in, the filter did its job. The rig-death posts, the hardware leaks and the memes all scored low and dropped. What rose to the top was exactly what we built it for: a quality regression in a specific Gemma quant, a small Qwen running usefully on a laptop, a 3.26x speculative-decoding speedup, and an open clinical-PII de-identification model. Two filed themselves into the Loop. A day's scoring costs a few pennies on Gemini Flash.

## What's still off

RSS does not carry upvote counts, so we lost the community-signal floor we use on Hacker News. For now Reddit's own top-of-day ranking plus the 9-10 bar do that job, but if quality slips we will need another way to weight it. r/LocalLLaMA is also the noisiest source we have, so the threshold is deliberately high and will need watching over a week. And the digest is internal for now: it feeds Gary, but it does not yet surface anywhere we read by default. Folding the top of it into the Monday round-up is the next move.
