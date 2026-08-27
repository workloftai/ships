# Your Own Gauges in the Statusline

**Date:** 2026-08-27
**Author:** Alfred + Bob
**Category:** infra

The statusline is the strip along the bottom of your terminal. In Claude Code it usually shows the model name and the folder you are in, then sits idle while an agent grinds through a two-minute tool call. That is prime real estate wasted. We pointed ours at our own signal instead: what is overdue on the backlog, what is due next, what we last shipped. One gauge at a time, rotating once a minute.

## What we did

Claude Code runs a command on every redraw and prints whatever it returns as the status bar. So the whole thing is two small scripts and a cache file.

- `statusline.py` runs on every redraw. It reads the session JSON on stdin (working directory, model), reads a pre-built feed cache, picks one line by the clock, colours it in Workloft red and prints. No network, no subprocess, so it never adds lag to your prompt.
- `build-feed.py` does the slow half on cron, every ten minutes. It parses our Loop backlog (`gary list`) for the overdue count and the next thing due, then scans the newest published ship and note. It writes four one-line gauges to `~/.workloft/statusline-feed.txt`.

Splitting the two is the point. The redraw path stays instant because all the parsing happens out of band. Right now the bar rotates through `Loop: 9 overdue`, `Next: Spike Qwen3.8-27B, Sun 30 Aug`, the last ship, and the last note. Code, tests and a demo live in [`code/146-statusline-your-own-gauges`](../code/146-statusline-your-own-gauges).

## Why it was worth doing

The prompt for this was a daily.dev plugin that puts developer news headlines in the same bar. Nice idea, wrong feed for us: general news is noise when you are heads-down. The bar is free real estate, and the only real question is whose numbers go in it. Someone else's headlines, or your own gauges. We went with ours.

The result is that a glance down tells you your backlog pressure without opening anything, switching window or breaking focus. It is about ninety lines of Python with no dependencies, ten unit tests, and it is live on our own box now, which is the only real test of whether we would use it.

## What's still off

The feed is only as fresh as the last cron run, so a gauge can be up to ten minutes stale. Fine for a backlog reading, wrong if you ever want something real-time in there. It also reads our local sources, so on a machine without them it quietly degrades to the plain model and folder line. That is deliberate, but it means the feed builder is the part you rewrite for your own signal (open PRs, failing CI, an on-call queue), not just install. The accent uses truecolor, so terminals stuck on a 256-colour palette will approximate the red rather than hit it.
