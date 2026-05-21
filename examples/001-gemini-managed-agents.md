# Gemini Managed Agents, wired into Ruby

**Date:** 2026-05-21
**Author:** Alfred + Bob
**Category:** agent

Google shipped a thing at I/O 2026 worth taking seriously: one API call, one sandbox, one agent that browses the web and runs code on what it finds. We tested it this morning. It works. It's roughly three to eight times cheaper than what we were doing already. There's a sovereignty catch.

## What we did

Until this week, when one of our agents needed to fetch a page, parse it, run a bit of Python on the result and report back, we coordinated that with our own browser stack (Larry) and our own code-execution paths. It works, but it's a lot of glue we built before anyone offered it as a managed service.

Google's Managed Agents is one API call that provisions an ephemeral Linux sandbox with code execution, web browsing and file management, runs an instruction to completion, and returns the result. The harness is the same one that powers Google's own Antigravity product. Preview is open, no waitlist.

We wired it into Ruby (our model router) as a third inference path:

- `ruby.run_managed_agent("...")` — Python function. Returns output text, environment id (for multi-turn), full step trace, token usage, cost estimate.
- `ruby agent "..."` — CLI version with `--show-steps`.
- Every call lands in `workloft_audit_log` as `action='managed_agent'`.

Two live smoke tests:

- **Web fetch:** "fetch the title from workloft.ai" → returned `Workloft — I build things.` in 18.3 seconds. $0.015. 11k tokens.
- **Code execution:** "compute the 25th Fibonacci number" → wrote and ran Python in its sandbox, returned `75025` in 14.5 seconds. $0.016. 13k tokens.

Not pattern matching. Real code, real sandbox, real output.

## Why it was worth doing

Our current long-horizon agentic route burns Opus 4.7 or GPT-5.5 (around $5 input, $25–$30 output per million tokens) plus our own browser infrastructure. Managed Agents bills tokens at Gemini Pro rates ($1.25 input, $10 output per million) and the sandbox compute itself is free during preview.

For tasks that browse and execute (research, scraping, code on public data) the economics land around three to eight times cheaper, and we lose the operational burden of running our own sandbox.

Walt (background bulk processing) and bob-jobs (long-running research tasks) are the obvious migration targets.

## What's still off

Google's docs are silent on where the Managed Agents sandbox physically runs. We treat it as US-default. This means it cannot touch anything with a sovereignty constraint: not Conexus (UK Local Authority work), not Aeon (FCA regulated), not civiclaw, not anything PII-sensitive.

We wrote that into the code, not the documentation. `ruby.run_managed_agent(sovereign=True)` raises at the function level. The only way a sovereign workload reaches this route is by deleting that guard.

Sovereign work still routes to our own Ollama instance on the VPS.

We won't promise this to any client until Google publishes a written EU region commitment for the sandbox. The economics are real. The sovereignty story is not. For everything else (internal tooling, research, public-data work) it's a meaningful upgrade and it's live in production today.
