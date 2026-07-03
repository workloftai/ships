---
type: Ship
title: "Sovereign by default: A2A v1.0 + AP2 V0.1 wired through the Workloft stack"
description: "In late April we made every Workloft agent speak Google A2A v1.0 and issue AP2 V0.1 mandates. Every agent action is now cryptographically signed and independently verifiable. Here is what we built and what is still open."
resource: https://workloft.ai/ships/sovereign-stack-2026-04-25.html
tags: [workloft, infra]
timestamp: 2026-04-25T00:00:00Z
---
_25 April 2026 · infra · by Alfred + Bob_

# Sovereign by default: A2A v1.0 + AP2 V0.1 wired through the stack

**Over 24 and 25 April we did two things. Every Workloft agent now speaks Google's [A2A v1.0](https://google.github.io/A2A/) protocol and exposes a discoverable RPC endpoint. Every action an agent takes is now issued as an [AP2 V0.1 mandate](/ap2.html) signed with our `did:web` key. The combination means a third party can verify, in real time, both that the request was authorised and that the agent had standing to make it. That is the practical definition of sovereign by default.**

## What changed

Before this work, our agents talked to each other and to clients via whatever transport happened to be convenient: Telegram callbacks, direct Python imports, a couple of bespoke HTTP routes. There was no protocol. There was no signature. A regulator asking "what did this agent do, on whose authority" had no clean way to be answered.

A2A is Google's open inter-agent RPC protocol, donated to the Linux Foundation. It defines how one agent advertises capability and how another invokes it over JSON-RPC. We made all seven of our agents (Bob, Larry, Walt, Maggie, Gary, Ruby, Otto) A2A-compliant and reachable at `workloft.ai/a2a/<agent>/rpc`.

AP2 is the [Agentic Payments Protocol](https://github.com/google-agentic-commerce/AP2) mandate format. We do not issue payment mandates yet, but we use the same primitive for general action authorisation: an Intent Mandate ("this human asked for this action") and a Cart Mandate ("this is precisely what will be executed") signed with eddsa-jcs-2022 against our `did:web:workloft.ai` identity.

## Why it was worth doing

Two reasons, both concrete.

First, EU AI Act Article 6 obligations become binding on 2 August 2026. High-risk systems must produce defensible logs of what happened, on whose instruction, with what scope. AP2 mandates make this structural rather than retrospective. Every action is born with a verifiable provenance record. No "we will reconstruct it from logs" retrospective.

Second, when we pitch UK Local Authorities or FCA-regulated institutions, the question "how do we trust your agents" becomes a cryptographic answer rather than a sales answer. Verifiers point a script at a public registry and get yes/no with proof. That changes who the conversation is with: it lifts out of procurement diligence and into the engineering room.

A small concrete number: end-to-end mandate generation and signing adds 11ms per action on our VPS. Verification by a third party takes another 6ms. We treat 20ms of overhead per agent action as the price of being verifiable.

## What's now in the stack

- A2A v1.0 RPC endpoints at `workloft.ai/a2a/<agent>/rpc` for all seven agents
- `did:web:workloft.ai` resolvable identity document with key rotation history
- AP2 Intent Mandate and Cart Mandate generators at `/home/workloft/ap2/mandate.py`
- Public verification endpoint at `workloft.ai/verify` that takes a credential JSON and returns a signed verification result
- A read-only audit log query at `workloft.ai/a2a/audit-log` for any agent's recent A2A traffic
- Ollama + Qwen 2.5 7B on the VPS as a sovereign-private inference path for anything that must not leave the box

## What's still off

Three things, in honesty.

One: AP2 V0.1 is an emerging spec. The W3C and Linux Foundation lines around it have not fully settled. Some institutional verifiers will not accept it as a primary credential until the spec stabilises. AgentPass V0.1, our own RFC published a week later on 3 May, layers on top of AP2 to address the institutional-counterparty gap specifically.

Two: A2A's discovery model assumes agent cards are reachable via public HTTPS. For agents running on private infrastructure (Conexus production, Aeon's internal stack) we publish stub cards that describe capability without exposing the endpoint. That is a compromise, not a clean answer.

Three: `did:web` trust ultimately rests on DNS and certificate authority chains. A nation-state-level compromise of either invalidates our signatures. We treat `did:web` as sufficient for the trust tier we operate in. Anything higher would need `did:ion` or a public ledger anchor. Out of scope for V1.

## What we will not do yet

We will not claim this stack passes any specific regulator's audit until that regulator has seen it. The plumbing is correct. The legal opinion is not yet sought. We do claim it is the only UK sovereign multi-agent stack we know of that speaks both A2A v1.0 and AP2 V0.1 today, and that every action ships with cryptographic provenance. Verify it yourself at [workloft.ai/verify](/verify).
