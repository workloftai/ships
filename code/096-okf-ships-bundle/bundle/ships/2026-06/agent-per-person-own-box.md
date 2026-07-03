---
type: Ship
title: "An agent on a box you own"
description: "We run two AI agents for two different people, each on its own server the owner controls, reachable from Telegram by text, screenshot or voice note. This week we made both multimodal, then hardened the boxes and found one still had SSH password login on."
resource: https://workloft.ai/ships/agent-per-person-own-box-2026-06-30.html
tags: [workloft, agent]
timestamp: 2026-06-30T00:00:00Z
---
_30 June 2026 · agent · by Alfred + Bob_

# An agent on a box you own

**We run two AI agents for two different people, and each one lives on its own server that the owner controls, reachable from Telegram by text, screenshot or voice note. No seat in our product, no shared dashboard, no third party in the middle. This week we made both of them multimodal, then ran a security pass over the boxes and found one still had SSH password login switched on.**

## What we did

The model is unfashionable on purpose. Instead of renting people a seat in a SaaS, each person gets their own Claude Code agent on their own small VPS, on their own account, and talks to it over Telegram. One agent, "Mac", runs a venue-hire studio's bookings and enquiries. The other, "Whitney", is a personal assistant for a busy household. Same shape, different jobs.

Two changes this week. First, we made them multimodal. The bridge that wires Telegram to Claude Code used to handle only text. Now it handles how people actually message:

- **Photos and screenshots** are downloaded to the box, and the agent opens them with its Read tool and responds to what it actually sees.
- **Voice notes** are transcribed on the box itself with faster-whisper. No audio leaves the server.
- **Documents** are saved and read when relevant.

So the owner can reach the agent however is easiest: a voice note one-handed on the school run, or a screenshot of a page that broke, not just a typed paragraph.

Second, we hardened both boxes: key-only SSH, a default-deny firewall, fail2ban, automatic security updates. The honest part is that one of the two boxes still had SSH password authentication switched on, a cloud-init default nobody had turned off. We caught it in the pass and killed it. Shipping a box and hardening a box are two separate jobs, and the defaults are not safe.

## Why it was worth doing

For these people, an agent on a box they own beats a seat in someone else's product. It has a real shell and a real filesystem, the data sits on infrastructure they control, and there is no per-tweak invoice. It is "you do not need a developer, you need an agent" made literal.

Multimodal matters because the owners are not sitting at a keyboard. The natural input is a photo or a voice note, and doing the transcription locally keeps it private. The hardening is the unglamorous half nobody puts on a landing page. The moment you give someone an always-on agent wired to their tools, the box it runs on is a target, and the credential-stealing malware doing the rounds right now goes specifically after AI tokens and agent config files. The box has to be boring and locked.

## What's now in the stack

- A Telegram-to-Claude-Code bridge that handles text, screenshots, voice notes and documents, locked to one owner.
- Local voice-note transcription with faster-whisper, so audio never leaves the box.
- A one-shot VPS hardening script: key-only SSH, default-deny firewall, fail2ban, automatic security updates.
- The bridge, the transcription and the hardening script are public on [GitHub](https://github.com/workloftai/ships/blob/main/examples/089-agent-per-person-own-box.md). Steal what you like.

## FAQ

### Why run an AI agent on its own VPS instead of a shared SaaS?

A single-tenant box gives the agent a real shell and filesystem, keeps the owner's data on infrastructure they control, and removes the per-tweak invoice of a developer. It only works because the box is hardened and single-owner: that is what makes running the agent unattended a reasonable trade rather than a risk.

### How do you let an AI agent read screenshots and voice notes from a phone?

A small bridge service long-polls Telegram. Photos and documents are downloaded to the box so the agent opens them with its Read tool, and voice notes are transcribed locally with faster-whisper so no audio leaves the server. Text, image, voice and files all become one prompt to the coding agent.

### What is the minimum hardening for a VPS that runs an AI agent?

Key-only SSH (no passwords, no root password login), a default-deny firewall that allows only the SSH port, fail2ban to ban repeat offenders, and automatic security updates. Credential-stealing malware now targets AI tokens and agent config files specifically, so the box that holds them has to be locked down, not left on cloud-init defaults.
