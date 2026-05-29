# civiclaw FOI intake prompt polished

**Date:** 2026-05-29
**Author:** Alfred + Bob
**Category:** fix

civiclaw's FOI intake prompt had a line that said "Is there a clarification needed?" The model interpreted that as an invitation to chat. Today's polish removes that default, anchors the output as workable-as-written, and forces six fixed headings. Output on Qwen2.5:7b dropped from ~60 lines / 1m41s to ~30 lines / 45s and stayed on-topic.

## What we did

Two structural changes to `INTAKE_SYSTEM` in `skills/foi/skill.py`. First, an OUTPUT RULES block at the top: "Do NOT ask the requester clarifying questions. Default position: assume the request is workable. Only flag s.1(3) clarification when a specific named gap exists." Second, the open-ended "applicant handling" section became a single binary decision: "No, workable as written" by default, or one concrete sentence naming the gap. Six fixed headings, no preamble, no closing summary.

## Why it was worth doing

Information Governance Officers want a triage note, not a Socratic dialogue. The 20-working-day FOIA clock has already started by the time intake runs. Clarification is a last resort, not a default. The previous prompt's habit of suggesting follow-up questions added latency and made the output feel uncertain. The new prompt halves generation time and reads like a one-page handover.

## What's still off

The model still occasionally hallucinates statutory references on Qwen2.5:7b (the smoke test cited a non-existent FOIA section). That's a model-class issue. Frontier tier (Qwen2:72b or Claude Sonnet) keeps this under control. Worth revisiting once we wire instructor over Ollama tool-use, which would let us pin the exemption list to a Pydantic enum.
