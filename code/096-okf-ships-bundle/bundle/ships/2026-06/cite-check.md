---
type: Ship
title: "The agent passed along five papers it never opened · Workloft Ships"
description: "Our agent handed over five arXiv IDs and admitted it had not checked them. A rule told it to verify; nothing enforced the rule. So we built the gate: cite-check fetches every link and arXiv ID and fails the publish if one is not real."
resource: https://workloft.ai/ships/cite-check-2026-06-26.html
tags: [workloft, tooling]
timestamp: 2026-06-26T00:00:00Z
---
_26 June 2026 · tooling · by Alfred + Bob_

# The agent passed along five papers it never opened.

**This morning the agent handed over five research papers worth a look, then added a line to its own message: it had not actually checked the IDs were real. Honest, and exactly the wrong place to be. A draft should not reach a human carrying citations nobody has opened. We had a rule against it. We did not have a guard. So we built the guard, and here it is.**

## The slip

A research feed surfaced five arXiv papers, each tagged with an identifier like 2606.21959. An arXiv ID is the catalogue number for a paper; it either points at a real paper or it does not. Language models are good at producing ones that look right and point at nothing. The agent relayed all five, and to its credit flagged that it had not resolved them. But "I have not checked" is not a state you ship from. It is a to-do you handed to the reader.

We already had rules for this: verify every URL, never invent an identifier. The trouble with a rule is that it lives in a prompt and leans on the agent to remember it under load. A rule a human, or an agent, has to remember is not a control. It is a wish. The fix is to make the check something the copy cannot get past, not something anyone has to recall.

## What we built

cite-check reads a draft, pulls out every link and every arXiv ID, and fetches each one to confirm it is real. Links get a lightweight request, falling back to a fuller fetch when a server refuses the quick one, which plenty do. A status under 400 passes; a dead page fails. arXiv IDs are a special case: the page for a made-up ID can still return a normal "all fine" response, so checking the page is not enough. cite-check asks the arXiv catalogue directly instead, and a fabricated ID comes back with no matching entry. That fails.

The whole thing is a small command line tool with one job and a clear verdict. It exits clean when every citation resolves and errors when any do not, so it drops straight into a publish step as a gate: if a citation is not real, the publish stops. No model call, no judgement, no latency to speak of. Either the source exists or it does not.

## What it found

We pointed it at the exact five IDs from the morning. All five resolved. Real papers, every one. Which is the point, not against it: the agent had no way to know that when it relayed them, and neither did we. The guard turned "I have not checked" into a definite yes in about two seconds. Then we fed it a control, an ID we made up, and it failed it cleanly: no such paper. Real links pass, dead links fail, invented papers fail. That is the whole contract, and it holds.

## What it does not do yet

Resolving a citation is the easy half. The harder half is misattribution: a real paper cited for something it never says. That sails straight past a resolve check, because the link is fine. So we built the second half too, the same day.

The support check decomposes a draft into single, self-contained claims, fetches the actual text of each cited source, and asks whether the source backs the claim. The verdict is one of four: supported, partly supported, not supported, or could-not-tell when the source is paywalled or dead. Only a clean "supported" passes on its own; everything else gets a human. We proved it on one real paper cited two ways: the accurate claim passed, and "the same paper shows this is a text-to-image model" was flagged as unsupported, on a source that resolves perfectly. The resolve check waved both through. The support check caught the lie.

One honest note on how it is built. The obvious engine was a 7B fact-checking model the research pointed at, and it was accurate. It was also unusable: on our CPU-only box it took over three minutes per single check. We swapped it for a far smaller entailment model that does the same job in about a sixth of a second, a thousandfold faster, with the same verdicts on our tests. The right tool is the one your hardware can actually run on the publish path, not the one with the best benchmark.

## What it still does not do

It reads a source in chunks, so a claim that only holds when you stitch two distant parts of a paper together lands in "partly" for a human to judge, rather than passing. And a fully paywalled source it cannot read comes back as could-not-tell, not a pass. Both are deliberate: when the machine is not sure, it asks a person, it does not wave the citation through.

## The lesson worth keeping

If your agent writes anything outward facing, it will eventually cite something that is not there. The defence is not a smarter model or a sterner prompt. It is a dumb, certain check that the copy cannot route around, sitting on the publish path, failing the send when a source does not resolve. Move the discipline out of the agent's memory and into the plumbing. A rule you have to remember is one you will eventually forget at the worst moment. A gate does not forget.
