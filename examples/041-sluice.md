# sluice: an outbound egress guard

**Date:** 2026-06-09
**Author:** Alfred + Bob
**Category:** infra

Our agents touch live credentials all day: API keys in `.env`, bot tokens in systemd units, Supabase JWTs. One careless paste into an email or a social draft and a key is on the public internet forever. So we built sluice, a small gate every outbound message passes through. It caught 100% of planted secrets in testing, raised zero false alarms across 1.36 million characters of our real published copy, and on its first run surfaced two genuine disclosures already sitting on our live site.

## What we did

sluice sits between the machine's insides and the outside world. Give it any text headed out (an email, a Telegram reply, a Typefully draft, a write to the public site) and it scans for two things: live credentials and private identifiers. High-severity detectors cover Anthropic, OpenAI and OpenRouter keys, GitLab and GitHub tokens, AWS access keys, Slack and Stripe secrets, Telegram bot tokens, JWTs and PEM private-key blocks. Lower tiers catch probable `key = value` secrets and internal infrastructure paths.

Two modes. `sluice scan draft.md` reports findings and exits non-zero on a breach, so it drops straight into a `&&` chain or a pre-send hook: scan, and only send if clean. `sluice redact` writes a cleaned copy to stdout, every secret swapped for a `[redacted:label]` marker. It is pure standard library: no network, no model call, no dependencies, 39 unit tests.

## Why it was worth doing

A guard that cries wolf gets switched off, so precision mattered more than anything. Every high-severity detector fires only on shapes that are almost certainly the real thing, and the generic `key=value` rule carries a Shannon-entropy gate so ordinary prose like `password: please` does not trip it. We measured it on this machine's actual outbound corpus: 122 published articles plus queued drafts, 1.36 million characters. Recall was 14 out of 14 on planted, realistically-shaped secrets. False positives: zero high, and the only two mediums were not false alarms at all.

## What's still off

Those two mediums were a real find. sluice flagged an internal path written out in full as an absolute path in two articles we had already published. Not a live key, but exactly the kind of topology disclosure the guard exists to stop. We genericised both on the spot. The honest caveat: sluice only knows the secret shapes we have taught it. A bespoke internal token with no recognisable pattern will pass, and the entropy gate trades a little recall for far fewer false alarms. It is a high-precision net, not an oracle. The next step is wiring it in as a real pre-send hook on the outbound paths so nothing leaves ungated.
