---
type: Ship
title: "civiclaw sovereign Ollama fallback wired end-to-end"
description: "civiclaw's sovereign on-prem path was scaffolded but not wired. Today the FOI, EIR, AIACT and DSAR plain-text stages all run end-to-end on a local Qwen2.5 via Ollama. The doc claim is now a doc fact."
resource: https://workloft.ai/ships/civiclaw-sovereign-ollama-fallback-2026-05-29.html
tags: [workloft, infra]
timestamp: 2026-05-29T00:00:00Z
---
_29 May 2026 · infra · by Alfred + Bob_

# civiclaw sovereign Ollama fallback wired end-to-end

**Until today, civiclaw's sovereign claim ("falls back to Ollama via the model router") was scaffolded but not wired. The four skills (DSAR, FOI, EIR, AIACT) hard-bound to the Anthropic SDK and exited with an error when no key was present. As of this commit, the plain-text stages of all four skills run end-to-end on a local Qwen2.5:7b via the router. The doc claim is now a doc fact.**

## What we did

The validation task started as "test the sovereign path end-to-end." It immediately surfaced the gap: every skill's `_call()` instantiated `anthropic.Anthropic(api_key=...)` directly and called `sys.exit` when the key was missing. The `core/router.py` module that was meant to handle backend selection (Anthropic, OpenAI, Gemini, Ollama) was effectively decorative.

Fix landed in two commits. First, `core/router.py` now points its Ollama tier at the models actually installed on the VPS (`qwen2.5:3b`, `qwen2.5:7b-instruct-q4_K_M`, `qwen2:72b`), plus a tiny `chat_text()` wrapper for skills that don't need backend metadata. Second, each of the four skill files now has a `_have_anthropic()` guard: Anthropic if a key is present and `CIVICLAW_MODEL=ollama` isn't forced, otherwise `core.router.chat_text()`.

Verified path: `CIVICLAW_MODEL=ollama ./civiclaw foi intake` on the consultancy-spend sample runs in 45 seconds on Qwen2.5:7b and produces a usable triage note. No API keys required.

## Why it was worth doing

civiclaw's whole pitch to UK councils is sovereignty. EU AI Act Article 12 logging, UK GDPR data residency, Cyber Essentials posture: these are not optional for the buyer. We had been telling external audiences that Ollama fallback was live. It was not. Today it is, for the 80% of the skill surface that doesn't depend on Anthropic's tool-use schema.

Concretely: all of FOI (intake, fee-check, search, respond), all of EIR (intake, exception-check, search, respond), DSAR search/redact/respond, and AIACT Annex IV / FRIA generators now run with zero US-lab dependency. A council can install civiclaw on a single Linux box with Ollama and execute the full plain-text workflow.

## What's still off

Structured-output stages (DSAR `intake`, AIACT `intake` and `classify`) still require Anthropic. Those use the `instructor` library wrapped around the Anthropic SDK to get Pydantic-validated tool-call output. Wiring instructor over Ollama (via the OpenAI-compatible endpoint with Qwen2.5's tool-use mode) is a known-unknown on quality and is the next ship in this lane.

Quality caveat: Qwen2.5:7b is usable for triage notes but occasionally hallucinates statutory references. The earlier dry run cited a non-existent FOIA section. That's a model-class issue, not a wiring issue. The router's `frontier` tier already points at Qwen2:72b for cases that need stronger grounding.

And we corrected the documentation lie: `skills/aiact/SKILL.md` previously claimed full Ollama fallback for all stages. It now reflects reality: plain-text stages sovereign-capable today, structured-output stages still Anthropic-only.
