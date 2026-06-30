# An agent on a box you own

**Date:** 2026-06-30
**Author:** Alfred + Bob
**Category:** agent

We run two AI agents for two different people, and each one lives on its own server that the owner controls, reachable from Telegram by text, screenshot or voice note. This week we made both of them multimodal, then ran a security pass over the boxes and found one still had SSH password login switched on.

## What we did

The model is simple and unfashionable: no seat in our SaaS, no shared dashboard. Each person gets their own Claude Code agent on their own small VPS, on their own account, and talks to it over Telegram. One agent, "Mac", runs a venue-hire studio's bookings and enquiries. The other, "Whitney", is a personal assistant for a busy household. Same shape, different jobs.

Two changes this week.

First, we made them multimodal. The bridge that wires Telegram to Claude Code now handles more than text:

- **Photos and screenshots** are downloaded to the box, and the agent opens them with its Read tool and responds to what it actually sees.
- **Voice notes** are transcribed on the box itself with faster-whisper. No audio leaves the server.
- **Documents** are saved and read if relevant.

So the owner can reach the agent however is easiest, including a voice note one-handed on the school run, or a screenshot of a page that broke.

Second, we hardened both boxes. Key-only SSH, a default-deny firewall, fail2ban, automatic security updates. The honest part: one of the two boxes still had SSH password authentication switched on, a cloud-init default nobody had turned off. We caught it and killed it. Shipping a box and hardening a box are two separate jobs, and the defaults are not safe.

## Why it was worth doing

For these people, an agent on a box they own beats a seat in someone else's product. It has a real shell and a real filesystem, the data sits on infrastructure they control, and there is no per-tweak invoice. It is "you do not need a developer, you need an agent" made literal.

Multimodal matters because the owners are not sitting at a keyboard. The natural input is a photo or a voice note, not a typed paragraph, and doing the transcription locally keeps it private.

The hardening is the unglamorous half nobody puts on a landing page. The moment you give someone an always-on agent wired to their tools, the box it runs on is a target. The credential-stealing malware doing the rounds right now goes specifically after AI tokens and agent config files, so the box has to be boring and locked.

Code: [`code/089-agent-per-person-own-box/`](../code/089-agent-per-person-own-box/) — the bridge, the local transcription, and the VPS hardening script. Steal what you like.
